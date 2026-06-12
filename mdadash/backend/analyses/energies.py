"""
Widgets for various simulation energies
"""

from collections import deque

import matplotlib.pyplot as plt
import MDAnalysis as mda

from mdadash.backend.widgets.base import WidgetBase


class EnergyWidgetBase:
    "Base class for Energy Widgets"

    name = ""
    data_key = ""
    y_label = "Energy ( kJ / mol )"

    def __init__(self):
        self._steps = deque(maxlen=100)
        self._values = deque(maxlen=100)

    def run(self, u: mda.Universe):
        ts = u.trajectory.ts
        if self.data_key not in ts.data:
            return  # pragma no cover
        self._values.append(ts.data[self.data_key])
        self._steps.append(ts.data["step"])
        # create plot
        plt.plot(self._steps, self._values)
        plt.ylabel(self.y_label)
        plt.xlabel("Step")
        plt.title(self.name, y=1.05)
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
