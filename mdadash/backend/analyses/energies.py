"""
Widgets for various simulation energies
"""

import logging
from collections import deque

import matplotlib.pyplot as plt
from IPython.display import display

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


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
                {"name": "Time", "value": "time"},
                {"name": "Step", "value": "step"},
            ],
        },
    ]

    def __init__(self):
        super().__init__()
        self.title = self.name
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
        self._set_title()
        self.ax.set_ylabel(self.y_label)
        self.ax.grid(True)

    def _reset_plot_values(self):
        """Reset plot values"""
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self._set_x_values()

    def _set_title(self):
        """Set plot title"""
        self.ax.set_title(self.title, y=1.05)

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

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            self._reset_plot_values()
        elif attribute == "title":
            self._set_title()
        elif attribute == "x_type":
            self._set_x_values()

    def run_every_frame(self):
        """every-frame run handler"""
        ts = getattr(self, "u").trajectory.ts
        if self.data_key not in ts.data:
            return  # pragma: no cover
        self.steps.append(ts.data["step"])
        self.times.append(ts.data["time"])
        self.y_values.append(ts.data[self.data_key])
        # update plot
        self.plot.set_data(self.x_values, self.y_values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)


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
