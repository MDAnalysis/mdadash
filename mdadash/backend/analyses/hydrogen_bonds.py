"""
Number of Hydrogen bonds
"""

import logging
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display
from joblib import delayed
from MDAnalysis.analysis.hydrogenbonds import HydrogenBondAnalysis

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class HydrogenBonds(WidgetBase):
    """

    **Number of Hydrogen bonds**

    This widget uses `MDAnalysis.analysis.hydrogenbonds.hbond_analysis.HydrogenBondAnalysis`_
    to calculate the number of `Hydrogen bonds`_ based on donor, hydrogens and acceptor
    selections. If donors selection is empty, the Universe topology must contain bonding
    information. If hydrogens selection or acceptors selection is empty, they are guessed
    and the Universe must contain charge information for this to work.

    .. note::
        It is highly recommended that a universe topology with bond information is used,
        as this is the only way that guarantees the correct identification of donor-hydrogen pairs.

    .. _MDAnalysis.analysis.hydrogenbonds.hbond_analysis.HydrogenBondAnalysis: https://
        docs.mdanalysis.org/stable/documentation_pages/analysis/hydrogenbonds.html
        #MDAnalysis.analysis.hydrogenbonds.hbond_analysis.HydrogenBondAnalysis

    .. _Hydrogen bonds: https://userguide.mdanalysis.org/stable/
        examples/analysis/hydrogen_bonds/hbonds.html

    **Inputs**

    Run frequency
        .. compound::
            The frequency with which the widget is run - `every-frame` or `batch`
                Default: ``every-frame``

    Run mode
        The mode in which the widget is run - `serial` or `parallel`
            Default: ``serial``

    Donor atoms
        MDAnalysis selection phrase of donor atoms
            Default: ``name O* N*``

    Hydrogen atoms
        MDAnalysis selection phrase of hydrogen atoms
            Default: ``name H*``

    Acceptor atoms
        MDAnalysis selection phrase of acceptor atoms
            Default: ``name O* N*``

    d_h_cutoff
        Distance cutoff used for finding donor-hydrogen pairs
            Default: ``1.2``

    d_a_cutoff
        Distance cutoff for hydrogen bonds
            Default: ``3.0``

    d_h_a_angle_cutoff
        D-H-A angle cutoff for hydrogen bonds, in degrees
            Default: ``150.0``

    Update selections
        Whether or not to update the selections every frame
            Default: ``True``

    Custom title
        Custom title for the plot
            Default: ''

    Max values
        Max values to show in plot
            Default: ``100``

    X-axis
        X-axis value - `time` or `step`
            Default: ``time``

    **Output**

    Here is an example output plot of this widget:

    .. figure:: /_static/images/hydrogen_bonds_output.jpg
        :alt: Hydrogen bonds output

    .. tip::
        This widget supports batching and can run in parallel

    """

    name = "Hydrogen bonds"
    description = "Number of Hydrogen bonds"

    _notes = (
        "It is highly recommended that a universe topology with bond information "
        "is used, as this is the only way that guarantees the correct identification "
        "of donor-hydrogen pairs."
    )

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
            "attribute": "donors_sel",
            "name": "Donor atoms",
            "description": "MDAnalysis selection phrase of donor atoms",
            "type": "str",
        },
        {
            "attribute": "hydrogens_sel",
            "name": "Hydrogen atoms",
            "description": "MDAnalysis selection phrase of hydrogen atoms",
            "type": "str",
        },
        {
            "attribute": "acceptors_sel",
            "name": "Acceptor atoms",
            "description": "MDAnalysis selection phrase of acceptor atoms",
            "type": "str",
        },
        {
            "attribute": "d_h_cutoff",
            "name": "d_h_cutoff",
            "description": "Distance cutoff used for finding donor-hydrogen pairs",
            "type": "float",
        },
        {
            "attribute": "d_a_cutoff",
            "name": "d_a_cutoff",
            "description": "Distance cutoff for hydrogen bonds",
            "type": "float",
        },
        {
            "attribute": "d_h_a_angle_cutoff",
            "name": "d_h_a_angle_cutoff",
            "description": "D-H-A angle cutoff for hydrogen bonds, in degrees",
            "type": "float",
        },
        {
            "attribute": "update_selections",
            "name": "Update selections",
            "description": "Whether or not to update the selections every frame",
            "type": "bool",
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
        self.donors_sel = "name O* N*"
        self.hydrogens_sel = "name H*"
        self.acceptors_sel = "name O* N*"
        self.d_h_cutoff = 1.2
        self.d_a_cutoff = 3.0
        self.d_h_a_angle_cutoff = 150.0
        self.update_selections = True
        self.hba = None
        self.title = "Hydrogen bonds"
        self.custom_title = None
        self.default_maxlen = 100
        self.maxlen = self.default_maxlen
        self.x_type = "time"
        self.x_values = None
        self._setup_plot()
        self._reset_plot_values()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        (self.plot,) = self.ax.plot([], [])
        self.ax.set_ylabel("Number of Hydrogen bonds")
        self.ax.grid(True)
        self._set_title()

    def _reset_plot_values(self):
        """Reset plot values"""
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self._set_x_values()

    def _set_title(self):
        """Set plot title"""
        self.ax.set_title(
            self.custom_title.replace("\\n", "\n") if self.custom_title else self.title
        )

    def _set_x_values(self):
        """Set the values for the x-axis"""
        if self.x_type == "step":
            x_label = "Step"
            self.x_values = self.steps
        else:
            x_label = "Time (ps)"
            self.x_values = self.times
        self.ax.set_xlabel(x_label)

    def _create_hba(self):
        """Update atom groups when selection phrases change"""
        self.hba = HydrogenBondAnalysis(
            universe=self.u,
            donors_sel=self.donors_sel if self.donors_sel else None,
            hydrogens_sel=self.hydrogens_sel if self.hydrogens_sel else None,
            acceptors_sel=self.acceptors_sel if self.acceptors_sel else None,
            d_h_cutoff=self.d_h_cutoff,
            d_a_cutoff=self.d_a_cutoff,
            d_h_a_angle_cutoff=self.d_h_a_angle_cutoff,
            update_selections=False,
        )
        self._update_plot(self._compute_current_frame())

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._reset_plot_values()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._create_hba()

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
        elif attribute in ("_run_mode", "_run_frequency"):
            pass
        else:
            self._reset_plot_values()
            self._create_hba()

    def _compute_current_frame(self):
        """Compute values for current frame"""
        self.hba.run(frames=[self.u.trajectory.frame])
        return (
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
            self.hba.results.hbonds.shape[0],
        )

    def _compute_batch(self):
        """Compute values for current batch"""
        self.hba.run()
        values = []
        indices = np.searchsorted(
            self.hba.frames, self.hba.results.hbonds[:, 0].astype(int)
        )
        counts = np.bincount(indices, minlength=len(self.hba.times))
        for i, count in enumerate(counts):
            _ = self.u.trajectory[i]
            values.append(
                (
                    self.u.trajectory.ts.data["step"],
                    self.u.trajectory.ts.data["time"],
                    count,
                )
            )
        return values

    def _update_plot(self, values):
        """Append values and update plot"""
        if isinstance(values, tuple):
            values = [values]
        # update plot points
        for value in values:
            (steps, times, v) = value
            self.steps.append(steps)
            self.times.append(times)
            self.y_values.append(v)
        # update plot
        self.plot.set_data(self.x_values, self.y_values)
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
