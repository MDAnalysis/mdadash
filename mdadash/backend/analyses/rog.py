"""
Radii of Gyration
"""

from collections import deque

import matplotlib.pyplot as plt
import numpy as np
from joblib import delayed

from mdadash.backend.widgets.base import WidgetBase


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
        self.selection = "protein"
        self.periodic = True
        self.updating = False
        self.ag = None
        self.title = "Radii of Gyration"
        self.custom_title = None
        self.x_type = "step"
        self.x_values = self.steps
        self.x_label = "Step"

    def _update_selection(self):
        """Update atom groups when selection phrase changes"""
        self.ag = self.u.select_atoms(
            self.selection, periodic=self.periodic, updating=self.updating
        )
        self.title = f"ROG of {self.selection}"

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
        elif attribute == "selection":
            self._update_selection()
            reset_plot = True
        elif attribute in ("periodic", "updating"):
            self._update_selection()
        if reset_plot:
            self.steps = deque(maxlen=self.maxlen)
            self.times = deque(maxlen=self.maxlen)
            self.y_values = deque(maxlen=self.maxlen)
            self._set_x_values()

    def _compute_rog_per_frame(self):
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

    def _compute_rog_batch(self, batch_size):
        """Compute ROG values for current batch"""
        values = []
        for i in range(batch_size):
            _ = self.u.trajectory[i]
            values.append(self._compute_rog_per_frame())
        return values

    def _create_plot(self, values):
        """Append ROG values and create plot"""
        if isinstance(values, tuple):
            values = [values]
        # update plot points
        for value in values:
            (steps, times, rog) = value
            self.steps.append(steps)
            self.times.append(times)
            self.y_values.append(rog)
        # create plot
        data = np.array(self.y_values)
        labels = ["all", "x-axis", "y-axis", "z-axis"]
        for i, label in enumerate(labels):
            plt.plot(self.x_values, data[:, i], label=label)
        plt.legend(loc="upper left")
        plt.ylabel("Radii (Å)")
        plt.xlabel(self.x_label)
        plt.title(self.custom_title if self.custom_title else self.title)
        plt.grid(True)
        plt.show()

    def run_per_frame(self):
        """per-frame run handler"""
        self._create_plot(self._compute_rog_per_frame())

    def run_batch(self, batch_size):
        """batch run handler"""
        self._create_plot(self._compute_rog_batch(batch_size))

    def get_parallel_job(self, batch_size):
        """get parallel job handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_rog_batch)(batch_size)
        return delayed(self._compute_rog_per_frame)()

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        self._create_plot(values)
