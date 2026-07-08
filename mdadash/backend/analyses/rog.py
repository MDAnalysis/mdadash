"""
Radii of Gyration
"""

import logging
from collections import deque

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display
from joblib import delayed

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class ROG(WidgetBase):
    """ROG

    Radii of Gyration of a selection

    """

    name = "ROG"
    description = "Radii of Gyration of a selection"

    _inputs = [
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
            "attribute": "selection",
            "name": "Selection",
            "description": "MDAnalysis selection phrase",
            "type": "str",
            "validations": ["required"],
        },
        {
            "attribute": "periodic",
            "name": "Periodic",
            "description": "Select with periodic boundary conditions",
            "type": "bool",
        },
        {
            "attribute": "updating",
            "name": "Updating",
            "description": "Update selection during each timestep",
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
        self.periodic = True
        self.updating = False
        self.ag = None
        self.title = "Radii of Gyration"
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
        self.ax.set_ylabel("Radii (Å)")
        labels = ["all", "x-axis", "y-axis", "z-axis"]
        self.plots = [self.ax.plot([], [], label=label)[0] for label in labels]
        self.ax.legend(loc="upper left")
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
        self.ag = self.u.select_atoms(
            self.selection, periodic=self.periodic, updating=self.updating
        )
        self.title = f"ROG of {self.selection}"
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
        elif attribute == "selection":
            self._update_selection()
            reset_plot = True
        elif attribute in ("periodic", "updating"):
            self._update_selection()
        if reset_plot:
            self._reset_plot_values()

    def _compute_current_frame(self):
        """Compute ROG values for current frame"""
        masses = self.ag.masses
        total_mass = np.sum(masses)
        coordinates = self.ag.positions
        # get squared distance from center
        ri_sq = (coordinates - self.ag.center_of_mass()) ** 2
        # sum the unweighted positions
        sq = np.sum(ri_sq, axis=1)
        sq_x = np.sum(ri_sq[:, [1, 2]], axis=1)  # sum over y and z
        sq_y = np.sum(ri_sq[:, [0, 2]], axis=1)  # sum over x and z
        sq_z = np.sum(ri_sq[:, [0, 1]], axis=1)  # sum over x and y
        # make into array
        sq_rs = np.array([sq, sq_x, sq_y, sq_z])
        # weight positions
        rog_sq = np.sum(masses * sq_rs, axis=1) / total_mass
        # square root
        rog = np.sqrt(rog_sq)
        return (
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
            rog,
        )

    def _compute_batch(self, batch_size):
        """Compute ROG values for current batch"""
        values = []
        for i in range(batch_size):
            _ = self.u.trajectory[i]
            values.append(self._compute_current_frame())
        return values

    def _update_plot(self, values):
        """Append ROG values and update plot"""
        if isinstance(values, tuple):
            values = [values]
        # update plot points
        for value in values:
            (steps, times, rog) = value
            self.steps.append(steps)
            self.times.append(times)
            self.y_values.append(rog)
        # update plot
        data = np.array(self.y_values)
        for plot, y_value in zip(self.plots, data.T):
            plot.set_data(self.x_values, y_value)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)

    def run_every_frame(self):
        """every-frame run handler"""
        self._update_plot(self._compute_current_frame())

    def run_batch(self, batch_size):
        """batch run handler"""
        self._update_plot(self._compute_batch(batch_size))

    def get_parallel_job(self, batch_size):
        """get parallel job handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_batch)(batch_size)
        return delayed(self._compute_current_frame)()

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        self._update_plot(values)
