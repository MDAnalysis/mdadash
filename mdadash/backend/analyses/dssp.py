from collections import deque

import matplotlib.pyplot as plt
import numpy as np
from joblib import delayed
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from MDAnalysis.analysis.dssp import DSSP

from mdadash.backend.widgets.base import WidgetBase


class DSSPAnalysis(WidgetBase):
    name = "DSSP Analysis"
    description = "Secondary structure assignment of protein"

    _inputs = [
        {
            "attribute": "_run_frequency",
            "name": "Run frequency",
            "description": "The frequency with which the widget is run",
            "type": "select",
            "items": [
                "per-frame",
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
                {"name": "Step", "value": "step"},
                {"name": "Time", "value": "time"},
            ],
        },
    ]

    def __init__(self):
        super().__init__()
        self.default_maxlen = 100
        self.maxlen = self.default_maxlen
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self.custom_title = None
        self.x_type = "step"
        self.x_label = "Step"
        self.x_values = self.steps
        self.dssp = None
        self.res_ids = None
        self.n_residues = None
        self.ss_map = {"H": 1, "E": 2, "-": 3}
        self.labels = ["Helix (H)", "Sheet (E)", "Loop (-)"]
        self.colors = ["#ff6666", "#66b2ff", "#d9d9d9"]
        self.custom_cmap = ListedColormap(self.colors)

    def _set_x_values(self):
        """Set the values for the x-axis"""
        if self.x_type == "step":
            self.x_label = "Step"
            self.x_values = self.steps
        else:
            self.x_label = "Time (ps)"
            self.x_values = self.times

    def on_post_create(self):
        """on_post_create handler"""
        self._set_x_values()

    def on_post_connect(self):
        """on_post_connect handler"""
        protein = self.u.select_atoms("protein")
        self.res_ids = protein.residues.resids
        self.n_residues = len(protein.residues)
        self.dssp = DSSP(protein)

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        reset_plot = False
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            reset_plot = True
        elif attribute == "x_type":
            self._set_x_values()
        if reset_plot:
            self.steps = deque(maxlen=self.maxlen)
            self.times = deque(maxlen=self.maxlen)
            self.y_values = deque(maxlen=self.maxlen)
            self._set_x_values()

    def _compute_per_frame(self):
        """Compute values for current frame"""
        self.dssp.run(frames=[self.u.trajectory.frame])
        return (
            [self.ss_map[s] for s in self.dssp.results.dssp[0]],
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
        )

    def _compute_batch(self, _batch_size):
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

    def _create_plot(self, values):
        """Append values and create plot"""
        if isinstance(values, tuple):
            values = [values]
        # update plot points
        for value in values:
            (nv, step, time) = value
            self.y_values.append(nv)
            self.steps.append(step)
            self.times.append(time)
        # create plot
        _, ax = plt.subplots(layout="constrained")
        matrix_to_plot = np.array(self.y_values).T
        min_x = self.x_values[0]
        max_x = self.x_values[-1]
        if min_x == max_x:
            max_x = min_x + 1
        _ = ax.imshow(
            matrix_to_plot,
            cmap=self.custom_cmap,
            aspect="auto",
            interpolation="nearest",
            vmin=0.5,
            vmax=3.5,
            extent=[min_x, max_x, 0, self.n_residues],
        )
        if self.custom_title:
            ax.set_title(self.custom_title, pad=40)
        ax.set_xlabel(self.x_label)
        ax.set_ylabel("Res ID")
        tick_spacing = max(1, self.n_residues // 10)
        ax.set_yticks(np.arange(0, self.n_residues, tick_spacing))
        ax.set_yticklabels(self.res_ids[::tick_spacing])
        ax.legend(
            [Patch(facecolor=c) for c in self.colors],
            self.labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 1.02),
            ncols=3,
        )
        plt.show()

    def run_per_frame(self):
        """per-frame run handler"""
        self._create_plot(self._compute_per_frame())

    def run_batch(self, batch_size):
        """batch run handler"""
        self._create_plot(self._compute_batch(batch_size))

    def get_parallel_job(self, batch_size):
        """get parallel job handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_batch)(batch_size)
        return delayed(self._compute_per_frame)()

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        self._create_plot(values)
