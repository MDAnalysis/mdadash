"""
Widgets for various simulation energies
"""

import logging
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class EnergyWidgetBase:
    """

    **Base class for Energy Widgets**

    This is the base class for all Energy widgets.

    Energy values are extracted from `MDAnalysis.coordinates.timestep.Timestep.data`_.

    The following keys are used for their respective plots:

    * ``temperature`` - Absolute Temperature
    * ``total_energy`` - Total Energy
    * ``potential_energy`` - Potential Energy
    * ``coulomb_energy`` - Coulomb Interaction Energy
    * ``bonds_energy`` - Bonds Energy
    * ``angles_energy`` - Angles Energy
    * ``dihedrals_energy`` - Dihedrals Energy
    * ``improper_dihedrals_energy`` - Improper Dihedrals Energy
    * ``van_der_walls_energy`` - Van Der Waals Energy

    .. note::
        Energies are only available in the timestep data for streaming trajectories.
        The simulation engine must also be explicitly configured to send them

    .. _MDAnalysis.coordinates.timestep.Timestep.data: https://docs.mdanalysis.org/stable/
        documentation_pages/coordinates/timestep.html#MDAnalysis.coordinates.timestep.Timestep.data

    **Inputs**

    Max values
        .. compound::
            Max values to show in plot
                Default: ``100``

    Title
        Title for the plot
            Default: ''

    X-axis
        X-axis value - `time` or `step`
            Default: ``time``

    **Outputs**

    Here is an example output plot of the **Absolute Temperature** widget:

    .. figure:: /_static/images/absolute_temperature_output.jpg
        :alt: Absolute Temperature output

    Here is an example output plot of the **Total Energy** widget:

    .. figure:: /_static/images/total_energy_output.jpg
        :alt: Total Energy output

    """

    name = ""
    data_key = ""
    y_label = "Energy ( kJ / mol )"

    _notes = (
        "Energies are only available for streaming trajectories and only if the "
        "simulation engine is configured to send them."
    )

    _inputs: ClassVar = [
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
        ts = self.u.trajectory.ts  # pylint: disable=no-member
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
    """Absolute Temperature

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Absolute Temperature"
    description = "Plot of Absolute Temperature"
    data_key = "temperature"
    y_label = "Temperature ( K )"


class TotalEnergy(EnergyWidgetBase, WidgetBase):
    """Total Energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Total Energy"
    description = "Plot of Total Energy"
    data_key = "total_energy"


class PotentialEnergy(EnergyWidgetBase, WidgetBase):
    """Potential energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Potential energy"
    description = "Plot of Potential Energy"
    data_key = "potential_energy"


class VanDerWaalsEnergy(EnergyWidgetBase, WidgetBase):
    """Van Der Waals Energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Van Der Waals Energy"
    description = "Plot of Van Der Waals Energy"
    data_key = "van_der_walls_energy"


class CoulombInteractionEnergy(EnergyWidgetBase, WidgetBase):
    """Coulomb Interaction Energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Coulomb Interaction Energy"
    description = "Plot of Coulomb Interaction Energy"
    data_key = "coulomb_energy"


class BondsEnergy(EnergyWidgetBase, WidgetBase):
    """Bonds Energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Bonds Energy"
    description = "Plot of Bonds Energy"
    data_key = "bonds_energy"


class AnglesEnergy(EnergyWidgetBase, WidgetBase):
    """Angles Energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Angles Energy"
    description = "Plot of Angles Energy"
    data_key = "angles_energy"


class DihedralsEnergy(EnergyWidgetBase, WidgetBase):
    """Dihedrals Energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Dihedrals Energy"
    description = "Plot of Dihedrals Energy"
    data_key = "dihedrals_energy"


class ImproperDihedralsEnergy(EnergyWidgetBase, WidgetBase):
    """Improper Dihedrals Energy

    See :class:`EnergyWidgetBase` for more details.

    """

    name = "Improper Dihedrals Energy"
    description = "Plot of Improper Dihedrals Energy"
    data_key = "improper_dihedrals_energy"
