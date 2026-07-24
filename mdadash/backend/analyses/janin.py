"""
Janin plot
"""

import logging
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display
from MDAnalysis.analysis.dihedrals import Janin

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class JaninPlot(WidgetBase):
    """Janin Plot

    Dihedral angles analysis using Janin plot

    """

    name = "Janin Plot"
    description = "Dihedral angles analysis using Janin plot"

    _inputs: ClassVar = [
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
        self.janin = None
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        (self.plot,) = self.ax.plot([], [])
        self.ax.grid(True)

    def _update_selection(self):
        """Update atom groups when selection phrase changes"""
        self.janin = Janin(self.u.select_atoms(self.selection))

    def on_post_connect(self):
        """on_post_connect handler"""
        self._update_selection()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "selection":
            self._update_selection()

    def _do_nothing(self, *_args, **_kwargs):
        return None

    def run_every_frame(self):
        """every-frame run handler"""
        self.janin.run(frames=[self.u.trajectory.frame])
        # update plot
        self.ax.clear()
        # Using `set_major_formatter` causes a memory leak everytime this
        # loop is run. Hence remove the degree formatting and mention
        # the units in the x and y axis labels instead
        self.ax.xaxis.set_major_formatter = self._do_nothing
        self.ax.yaxis.set_major_formatter = self._do_nothing
        self.janin.plot(ax=self.ax, color="black", marker=".", ref=self.ref)
        self.ax.set_xlabel(r"$\chi_1$ (degrees)")
        self.ax.set_ylabel(r"$\chi_2$ (degrees)")
        self.fig.canvas.draw()
        display(self.fig)
