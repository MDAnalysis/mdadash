"""
Radii of Gyration
"""

from collections import deque

import matplotlib.pyplot as plt
import numpy as np

from mdadash.backend.widgets.base import WidgetBase


class ROG(WidgetBase):
    """ROG

    Radii of Gyration of a selection

    """

    name = "ROG"
    description = "Radii of Gyration of a selection"

    _inputs = [
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
            "type": "switch",
        },
        {
            "attribute": "updating",
            "name": "Updating",
            "description": "Update selection during each timestep",
            "type": "switch",
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
        self.maxlen = 100
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

    def post_connect(self):
        """post_connect handler"""
        self._update_selection()

    def on_input_change(self, attribute, _old_value, _new_value):
        """on_input_change handler"""
        reset_plot = False
        if attribute == "maxlen":
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

    # pylint: disable=too-many-locals
    def run(self):
        """run handler"""
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
        # update plot points
        self.y_values.append(rog)
        self.steps.append(self.u.trajectory.ts.data["step"])
        self.times.append(self.u.trajectory.ts.data["time"])
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
