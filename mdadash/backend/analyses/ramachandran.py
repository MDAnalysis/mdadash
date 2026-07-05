"""
Ramachandran plot
"""

import logging

import matplotlib.pyplot as plt
from IPython.display import display
from MDAnalysis.analysis.dihedrals import Ramachandran

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class RamachandranPlot(WidgetBase):
    """Ramachandran Plot

    Dihedral angles analysis using Ramachandran plot

    """

    name = "Ramachandran Plot"
    description = "Dihedral angles analysis using Ramachandran plot"

    _inputs = [
        {
            "attribute": "selection",
            "name": "Selection",
            "description": "MDAnalysis selection phrase",
            "type": "str",
            "validations": ["required"],
        },
        {
            "attribute": "ref",
            "name": "Show reference",
            "description": "Show allowed and marginally allowed regions",
            "type": "bool",
        },
    ]

    def __init__(self):
        super().__init__()
        self.selection = "protein"
        self.ref = True
        self.rama = None
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        (self.plot,) = self.ax.plot([], [])
        self.ax.grid(True)

    def _update_selection(self):
        """Update atom groups when selection phrase changes"""
        self.rama = Ramachandran(self.u.select_atoms(self.selection))

    def on_post_connect(self):
        """on_post_connect handler"""
        self._update_selection()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "selection":
            self._update_selection()

    def _do_nothing(self, *_args, **_kwargs):
        return None

    def run_per_frame(self):
        """per-frame run handler"""
        self.rama.run(frames=[self.u.trajectory.frame])
        # update plot
        self.ax.clear()
        # Using `set_major_formatter` causes a memory leak everytime this
        # loop is run. Hence remove the degree formatting and mention
        # the units in the x and y axis labels instead
        self.ax.xaxis.set_major_formatter = self._do_nothing
        self.ax.yaxis.set_major_formatter = self._do_nothing
        self.rama.plot(ax=self.ax, color="black", marker=".", ref=self.ref)
        self.ax.set_xlabel(r"$\phi$ (degrees)")
        self.ax.set_ylabel(r"$\psi$ (degrees)")
        self.fig.canvas.draw()
        display(self.fig)
