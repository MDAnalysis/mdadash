"""
Distance between two center-of-masses
"""

from collections import deque

import matplotlib.pyplot as plt
from MDAnalysis.exceptions import NoDataError
from MDAnalysis.lib.distances import calc_bonds

from mdadash.backend.widgets.base import WidgetBase


class COMDistance(WidgetBase):
    """COM Distance

    Distance between two center-of-masses (COMs)

    """

    name = "COMDistance"
    description = "Distance between two COMs"

    _inputs = [
        {
            "attribute": "selection1",
            "name": "Selection 1",
            "description": "First MDAnalysis selection phrase",
            "type": "str",
            "validations": ["required"],
        },
        {
            "attribute": "selection2",
            "name": "Selection 2",
            "description": "Second MDAnalysis selection phrase",
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
            "attribute": "max_distance",
            "name": "Max distance",
            "description": "Max distance for alert check",
            "type": "float",
        },
        {
            "attribute": "max_distance_alert",
            "name": "Alert if distance > 'Max distance'",
            "type": "bool",
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
        self.selection1 = "protein"
        self.selection2 = "resid 1"
        self.periodic = True
        self.updating = False
        self.ag1 = None
        self.ag2 = None
        self.title = "Distance between COMs"
        self.custom_title = None
        self.max_distance = 5.0
        self.max_distance_alert = False
        self.x_type = "step"
        self.x_values = self.steps
        self.x_label = "Step"

    def _update_selections(self, s1=False, s2=False):
        """Update atom groups when selection phrases change"""
        if s1:
            self.ag1 = self.u.select_atoms(
                self.selection1, periodic=self.periodic, updating=self.updating
            )
        if s2:
            self.ag2 = self.u.select_atoms(
                self.selection2, periodic=self.periodic, updating=self.updating
            )
        self.title = f"{self.selection1} <-> {self.selection2}"

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
        self._update_selections(s1=True, s2=True)

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        reset_plot = False
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            reset_plot = True
        elif attribute == "x_type":
            self._set_x_values()
        elif attribute == "selection1":
            self._update_selections(s1=True)
            reset_plot = True
        elif attribute == "selection2":
            self._update_selections(s2=True)
            reset_plot = True
        elif attribute in ("periodic", "updating"):
            self._update_selections(s1=True, s2=True)
        if reset_plot:
            self.steps = deque(maxlen=self.maxlen)
            self.times = deque(maxlen=self.maxlen)
            self.y_values = deque(maxlen=self.maxlen)
            self._set_x_values()

    def run_per_frame(self):
        """per-frame run handler"""
        try:
            com1 = self.ag1.center_of_mass(unwrap=True)
            com2 = self.ag2.center_of_mass(unwrap=True)
        except NoDataError:  # pragma: no cover
            # unwrap can fail if there is no bonds info
            com1 = self.ag1.center_of_mass()
            com2 = self.ag2.center_of_mass()
        self.y_values.append(calc_bonds(com1, com2, box=self.u.dimensions))
        self.steps.append(self.u.trajectory.ts.data["step"])
        self.times.append(self.u.trajectory.ts.data["time"])
        plt.plot(self.x_values, self.y_values)
        plt.ylabel("Distance (Å)")
        plt.xlabel(self.x_label)
        plt.title(self.custom_title if self.custom_title else self.title)
        plt.grid(True)
        plt.show()
