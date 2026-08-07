"""
RMSD Analysis
"""

import logging
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display
from MDAnalysis.analysis import rms

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class RMSD(WidgetBase):
    """

    **RMSD Analysis**

    This widget uses `MDAnalysis.analysis.rms.rmsd`_ to calculate RMSD of a
    selection. The reference positions used by this widget are the initial
    positions of the selection when the widget instance is created or the
    initial positions whenever the selection is updated.

    .. _MDAnalysis.analysis.rms.rmsd: https://docs.mdanalysis.org/stable/
        documentation_pages/analysis/rms.html#MDAnalysis.analysis.rms.rmsd

    """

    name = "RMSD"
    description = "RMSD of a selection"

    _notes = (
        "If simulations are performed under periodic boundary conditions "
        "then you must make your molecules whole before performing RMSD "
        "calculations so that the centers of mass of the mobile and reference "
        "structure are properly superimposed. You can add custom transformations "
        "to the universe in the Universe Configuration section in the Settings page.\n\n"
        "Note: The reference positions used by this widget are the initial positions "
        "of the selection when the widget instance is created or the initial positions "
        "whenever the selection is updated."
    )

    _inputs: ClassVar = [
        {
            "attribute": "selection",
            "name": "Selection",
            "description": "MDAnalysis selection phrase",
            "type": "str",
            "validations": ["required"],
        },
        {
            "attribute": "center",
            "name": "Center",
            "description": "Subtract center of geometry before calculation",
            "type": "bool",
        },
        {
            "attribute": "superposition",
            "name": "Superposition",
            "description": (
                "Perform a rotational and translational superposition with the fast QCP algorithm"
            ),
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
        self.selection = "protein"
        self.center = False
        self.superposition = False
        self.ag = None
        self.reference_positions = None
        self.title = "RMSD"
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
        self.ax.set_ylabel("RMSD (Å)")
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
        self.ax.set_title(self.custom_title if self.custom_title else self.title)

    def _set_x_values(self):
        """Set the values for the x-axis"""
        if self.x_type == "step":
            x_label = "Step"
            self.x_values = self.steps
        else:
            x_label = "Time (ps)"
            self.x_values = self.times
        self.ax.set_xlabel(x_label)

    def _update_selection(self):
        """Update atom groups when selection phrase changes"""
        self.ag = self.u.select_atoms(self.selection)
        self.reference_positions = self.ag.positions.copy()
        self.title = f"RMSD of '{self.selection}'"
        self._set_title()

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._reset_plot_values()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._update_selection()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        reset_plot = False
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            reset_plot = True
        elif attribute == "x_type":
            self._set_x_values()
        elif attribute == "custom_title":
            self._set_title()
        elif attribute in ("selection", "center", "superposition"):
            self._update_selection()
            reset_plot = True
        if reset_plot:
            self._reset_plot_values()

    def run_every_frame(self):
        """every-frame run handler"""
        rmsd_value = rms.rmsd(
            self.ag.positions,
            self.reference_positions,
            center=self.center,
            superposition=self.superposition,
        )
        self.y_values.append(rmsd_value)
        self.steps.append(self.u.trajectory.ts.data["step"])
        self.times.append(self.u.trajectory.ts.data["time"])
        # update plot
        self.plot.set_data(self.x_values, self.y_values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)
