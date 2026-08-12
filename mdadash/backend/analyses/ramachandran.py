"""
Ramachandran plot (Dihedral angles analysis)
"""

import logging
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display
from MDAnalysis.analysis.dihedrals import Ramachandran

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class RamachandranPlot(WidgetBase):
    """

    **Ramachandran Plot**

    This widget uses `MDAnalysis.analysis.dihedrals.Ramachandran`_ for dihedral angles
    analysis and creates a `Ramachandran plot`_.

    .. _MDAnalysis.analysis.dihedrals.Ramachandran: https://docs.mdanalysis.org/stable/
        documentation_pages/analysis/dihedrals.html#MDAnalysis.analysis.dihedrals.Ramachandran

    .. _Ramachandran plot: https://userguide.mdanalysis.org/stable/
        examples/analysis/structure/dihedrals.html#Ramachandran-analysis

    **Inputs**

    Selection
        MDAnalysis selection phrase
            Default: ``protein``

    Show reference
        Show allowed and marginally allowed regions
            Default: ``True``

    Custom title
        Custom title for the plot
            Default: ''

    **Output**

    Here is an example output plot of this widget:

    .. figure:: /_static/images/ramachandran_output.jpg
        :alt: Ramachandran Plot output

    """

    name = "Ramachandran Plot"
    description = "Dihedral angles analysis using Ramachandran plot"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.ramachandran.html"
    )

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
        {
            "attribute": "custom_title",
            "name": "Custom title",
            "description": "Custom title for the plot",
            "type": "str",
        },
    ]

    def __init__(self):
        super().__init__()
        self.selection = "protein"
        self.ref = True
        self.rama = None
        self.title = "protein"
        self.custom_title = None
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        (self.plot,) = self.ax.plot([], [])

    def _update_selection(self):
        """Update atom groups when selection phrase changes"""
        self.rama = Ramachandran(self.u.select_atoms(self.selection))
        self.title = f"{self.selection}"

    def on_post_connect(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_connect` handler"""
        self._update_selection()

    def on_input_change(self, attribute, _old_value, new_value):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_input_change` handler"""
        if attribute == "selection":
            self._update_selection()

    def _do_nothing(self, *_args, **_kwargs):
        return None

    def run_every_frame(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.run_every_frame` handler"""
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
        self.ax.set_title(
            self.custom_title.replace("\\n", "\n") if self.custom_title else self.title
        )
        self.fig.canvas.draw()
        display(self.fig)
