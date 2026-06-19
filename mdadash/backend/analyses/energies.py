"""
Widgets for various simulation energies
"""

from collections import deque

import matplotlib.pyplot as plt

from mdadash.backend.widgets.base import WidgetBase


class EnergyWidgetBase:
    "Base class for Energy Widgets"

    name = ""
    data_key = ""
    y_label = "Energy ( kJ / mol )"

    _inputs = [
        {
            "attribute": "maxlen",
            "name": "Max values",
            "description": "Max values to show in plot",
            "type": "int",
        },
        {
            "attribute": "title",
            "name": "Title",
            "description": "Title for the plot",
            "type": "str",
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
        self.title = self.name
        self.maxlen = 100
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self.x_type = "step"
        self.x_values = self.steps
        self.x_label = "Step"

    def _set_x_values(self):
        """Set the values for the x-axis"""
        if self.x_type == "step":
            self.x_label = "Step"
            self.x_values = self.steps
        else:
            self.x_label = "Time (ps)"
            self.x_values = self.times

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "maxlen":
            self.steps = deque(maxlen=new_value)
            self.times = deque(maxlen=new_value)
            self.y_values = deque(maxlen=new_value)
            self._set_x_values()
        elif attribute == "x_type":
            self._set_x_values()

    def run(self):
        """run handler"""
        ts = getattr(self, "u").trajectory.ts
        if self.data_key not in ts.data:
            return  # pragma no cover
        self.steps.append(ts.data["step"])
        self.times.append(ts.data["time"])
        self.y_values.append(ts.data[self.data_key])
        # create plot
        plt.plot(self.x_values, self.y_values)
        plt.ylabel(self.y_label)
        plt.xlabel(self.x_label)
        plt.title(self.title, y=1.05)
        plt.grid(True)
        plt.show()


class AbsoluteTemperature(EnergyWidgetBase, WidgetBase):
    """Absolute Temperature"""

    name = "Absolute Temperature"
    description = "Plot of Absolute Temperature"
    data_key = "temperature"
    y_label = "Temperature ( K )"


class TotalEnergy(EnergyWidgetBase, WidgetBase):
    """Total Energy"""

    name = "Total Energy"
    description = "Plot of Total Energy"
    data_key = "total_energy"


class PotentialEnergy(EnergyWidgetBase, WidgetBase):
    """Potential energy"""

    name = "Potential energy"
    description = "Plot of Potential Energy"
    data_key = "potential_energy"


class VanDerWaalsEnergy(EnergyWidgetBase, WidgetBase):
    """Van Der Waals Energy"""

    name = "Van Der Waals Energy"
    description = "Plot of Van Der Waals Energy"
    data_key = "van_der_walls_energy"


class CoulombInteractionEnergy(EnergyWidgetBase, WidgetBase):
    """Coulomb Interaction Energy"""

    name = "Coulomb Interaction Energy"
    description = "Plot of Coulomb Interaction Energy"
    data_key = "coulomb_energy"


class BondsEnergy(EnergyWidgetBase, WidgetBase):
    """Bonds Energy"""

    name = "Bonds Energy"
    description = "Plot of Bonds Energy"
    data_key = "bonds_energy"


class AnglesEnergy(EnergyWidgetBase, WidgetBase):
    """Angles Energy"""

    name = "Angles Energy"
    description = "Plot of Angles Energy"
    data_key = "angles_energy"


class DihedralsEnergy(EnergyWidgetBase, WidgetBase):
    """Dihedrals Energy"""

    name = "Dihedrals Energy"
    description = "Plot of Dihedrals Energy"
    data_key = "dihedrals_energy"


class ImproperDihedralsEnergy(EnergyWidgetBase, WidgetBase):
    """Improper Dihedrals Energy"""

    name = "Improper Dihedrals Energy"
    description = "Plot of Improper Dihedrals Energy"
    data_key = "improper_dihedrals_energy"
