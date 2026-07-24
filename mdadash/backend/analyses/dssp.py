import logging
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display
from joblib import delayed
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from MDAnalysis.analysis.dssp import DSSP

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class DSSPAnalysis(WidgetBase):
    name = "DSSP Analysis"
    description = "Secondary structure assignment of protein"

    _inputs: ClassVar = [
        {
            "attribute": "_run_frequency",
            "name": "Run frequency",
            "description": "The frequency with which the widget is run",
            "type": "select",
            "items": [
                "every-frame",
                "batch",
            ],
        },
        {
            "attribute": "_run_mode",
            "name": "Run mode",
            "description": "The mode in which the widget is run",
            "type": "select",
            "items": [
                "serial",
                "parallel",
            ],
        },
        {
            "attribute": "custom_title",
            "name": "Custom title",
            "description": "Custom title for the plot",
            "type": "str",
        },
        {
            "attribute": "maxlen",
            "name": "Max values",
            "description": "Max values to show in plot",
            "type": "int",
        },
        {
            "attribute": "x_type",
            "name": "X-axis",
            "type": "toggle",
            "options": [
                {"name": "Time", "value": "time"},
                {"name": "Step", "value": "step"},
            ],
        },
    ]

    def __init__(self):
        super().__init__()
        self.dssp = None
        self.n_residues = None
        self.ss_map = {"H": 1, "E": 2, "-": 3}
        self.default_maxlen = 100
        self.maxlen = self.default_maxlen
        self.custom_title = None
        self.x_type = "time"
        self.x_values = None
        self._setup_plot()
        self._reset_plot_values()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots(layout="constrained")
        self._set_title()
        self.ax.set_ylabel("Res ID")
        colors = ["#ff6666", "#66b2ff", "#d9d9d9"]
        self.ax.legend(
            [Patch(facecolor=c) for c in colors],
            ["Helix (H)", "Sheet (E)", "Loop (-)"],
            loc="lower center",
            bbox_to_anchor=(0.5, 1.02),
            ncols=3,
        )
        self.im = self.ax.imshow(
            [[0]],
            cmap=ListedColormap(colors),
            aspect="auto",
            interpolation="nearest",
            vmin=0.5,
            vmax=3.5,
        )

    def _reset_plot_values(self):
        """Reset plot values"""
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self._set_x_values()

    def _set_title(self):
        """Set plot title"""
        self.ax.set_title(self.custom_title if self.custom_title else "", pad=40)

    def _set_x_values(self):
        """Set the values for the x-axis"""
        if self.x_type == "step":
            x_label = "Step"
            self.x_values = self.steps
        else:
            x_label = "Time (ps)"
            self.x_values = self.times
        self.ax.set_xlabel(x_label)

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._reset_plot_values()

    def on_post_connect(self):
        """on_post_connect handler"""
        protein = self.u.select_atoms("protein")
        # Fix for ValueError: Universe contains unequal numbers of (N,CA,C,O) atoms
        n_res = self.u.select_atoms("protein and name N").resids
        ca_res = self.u.select_atoms("protein and name CA").resids
        c_res = self.u.select_atoms("protein and name C").resids
        o_res = self.u.select_atoms("protein and name O O1 OT1").resids
        valid_resids = set(n_res) & set(ca_res) & set(c_res) & set(o_res)
        protein = self.u.select_atoms(
            f"protein and resid {' '.join(map(str, valid_resids))} and (name N CA C O O1 OT1)"
        )
        res_ids = protein.residues.resids
        self.n_residues = len(protein.residues)
        self.dssp = DSSP(protein)
        # setup plot y-axis
        tick_spacing = max(1, self.n_residues // 10)
        self.ax.set_yticks(np.arange(0, self.n_residues, tick_spacing))
        self.ax.set_yticklabels(res_ids[::tick_spacing])

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            self._reset_plot_values()
        elif attribute == "x_type":
            self._set_x_values()
        elif attribute == "custom_title":
            self._set_title()

    def _compute_current_frame(self):
        """Compute values for current frame"""
        self.dssp.run(frames=[self.u.trajectory.frame])
        return (
            [self.ss_map[s] for s in self.dssp.results.dssp[0]],
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
        )

    def _compute_batch(self):
        """Compute values for current batch"""
        self.dssp.run()
        # `run()` can also be invoked with a non-serial backend
        # self.dssp.run(backend="multiprocessing", n_workers=2)
        values = []
        for i, ss in enumerate(self.dssp.results.dssp):
            _ = self.u.trajectory[i]
            values.append(
                (
                    [self.ss_map[res] for res in ss],
                    self.u.trajectory.ts.data["step"],
                    self.u.trajectory.ts.data["time"],
                )
            )
        # `_get_aggregator` of DSSP only specifies the aggregation for
        # `dssp_ndarray` key. `_conclude` creates two new keys `dssp` and
        # `resids` in results. For this reason, subsequent `run()`'s will
        # throw a ValueError for these keys when a non-serial backend is
        # used. Hence remove these attributes to enable subsequent runs.
        # Note: only needed for the case when multiple results need merge
        delattr(self.dssp.results, "dssp")
        delattr(self.dssp.results, "resids")
        return values

    def _update_plot(self, values):
        """Append values and update plot"""
        if isinstance(values, tuple):
            values = [values]
        # update plot points
        for value in values:
            (nv, step, time) = value
            self.y_values.append(nv)
            self.steps.append(step)
            self.times.append(time)
        # update plot
        matrix_to_plot = np.array(self.y_values).T
        min_x = self.x_values[0]
        max_x = self.x_values[-1]
        if min_x == max_x:
            max_x = min_x + 1
        self.im.set_data(matrix_to_plot)
        self.im.set_extent([min_x, max_x, 0, self.n_residues])
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)

    def run_every_frame(self):
        """every-frame run handler"""
        self._update_plot(self._compute_current_frame())

    def run_batch(self):
        """batch run handler"""
        self._update_plot(self._compute_batch())

    def get_parallel_job(self):
        """get parallel job handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_batch)()
        return delayed(self._compute_current_frame)()

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        self._update_plot(values)
