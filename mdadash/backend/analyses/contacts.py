"""
Contacts within a cutoff
"""

import logging
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display
from joblib import delayed
from MDAnalysis.lib.distances import capped_distance

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class Contacts(WidgetBase):
    r"""

    **Contacts within a cutoff**

    This widget uses `MDAnalysis.lib.distances.capped_distance`_ to caclulate
    `number of contacts within a cutoff`_ between two contacting groups.

    .. _number of contacts within a cutoff: https://userguide.mdanalysis.org/
        stable/examples/analysis/distances_and_contacts/contacts_within_cutoff.html

    .. _MDAnalysis.lib.distances.capped_distance: https://docs.mdanalysis.org/stable/
        documentation_pages/lib/distances.html#MDAnalysis.lib.distances.capped_distance

    **Inputs**

    Run frequency
        .. compound::
            The frequency with which the widget is run - `every-frame` or `batch`
                Default: ``every-frame``

    Run mode
        The mode in which the widget is run - `serial` or `parallel`
            Default: ``serial``

    Contacting Group 1
        MDAnalysis selection phrase of first group
            Default: ``(resname ASP GLU) and (name OE* OD*)``

    Contacting Group 2
        MDAnalysis selection phrase of second group
            Default: ``(resname ARG LYS) and (name NH* NZ)``

    Radius
        Radius within which contacts exist
            Default: ``4.5``

    Custom title
        Custom title for the plot
            Default: ''

    Max values
        Max values to show in plot
            Default: ``100``

    X-axis
        X-axis value - `time` or `step`
            Default: ``time``

    **Output**

    Here is an example output plot of this widget:

    .. figure:: /_static/images/contacts_output.jpg
        :alt: Contacts output

    .. tip::
        This widget supports batching and can run in parallel

    """

    name = "Contacts"
    description = "Contacts within a cutoff"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.contacts.html"
    )

    _inputs: ClassVar = [
        {
            "attribute": "_run_frequency",
            "name": "Run frequency",
            "description": "The frequency with which the widget is run",
            "type": "select",
            "items": [
                "every-frame",
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
            "attribute": "selection1",
            "name": "Contacting Group 1",
            "description": "MDAnalysis selection phrase of first group",
            "type": "str",
            "validations": ["required"],
        },
        {
            "attribute": "selection2",
            "name": "Contacting Group 2",
            "description": "MDAnalysis selection phrase of second group",
            "type": "str",
            "validations": ["required"],
        },
        {
            "attribute": "radius",
            "name": "Radius",
            "description": "Radius within which contacts exist",
            "type": "float",
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
                {"name": "Time", "value": "time"},
                {"name": "Step", "value": "step"},
            ],
        },
    ]

    def __init__(self):
        super().__init__()
        self.selection1 = "(resname ASP GLU) and (name OE* OD*)"
        self.selection2 = "(resname ARG LYS) and (name NH* NZ)"
        self.radius = 4.5
        self.ag1 = None
        self.ag2 = None
        self.title = "Contacts within cutoff"
        self.custom_title = None
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
        self.ax.set_ylabel("Number of contacts")
        self.ax.grid(True)
        self._set_title()

    def _reset_plot_values(self):
        """Reset plot values"""
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self._set_x_values()

    def _set_title(self):
        """Set plot title"""
        self.ax.set_title(
            self.custom_title.replace("\\n", "\n") if self.custom_title else self.title
        )

    def _set_x_values(self):
        """Set the values for the x-axis"""
        if self.x_type == "step":
            x_label = "Step"
            self.x_values = self.steps
        else:
            x_label = "Time (ps)"
            self.x_values = self.times
        self.ax.set_xlabel(x_label)

    def _update_selections(self):
        """Update atom groups when selection phrases change"""
        self.ag1 = self.u.select_atoms(self.selection1)
        self.ag2 = self.u.select_atoms(self.selection2)
        self.title = f"Contacts between\n'{self.selection1}' and '{self.selection2}'"
        self._set_title()

    def on_post_create(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_create` handler"""
        self._set_title()
        self._reset_plot_values()

    def on_post_connect(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_connect` handler"""
        self._update_selections()

    def on_input_change(self, attribute, _old_value, new_value):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_input_change` handler"""
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            self._reset_plot_values()
        elif attribute == "x_type":
            self._set_x_values()
        elif attribute == "custom_title":
            self._set_title()
        elif attribute in ("selection1", "selection2", "radius"):
            self._reset_plot_values()
            self._update_selections()

    def _compute_current_frame(self):
        """Compute values for current frame"""
        pairs = capped_distance(
            self.ag1.positions,
            self.ag2.positions,
            max_cutoff=self.radius,
            box=self.u.dimensions,
            return_distances=False,
        )
        return (
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
            len(pairs),
        )

    def _compute_batch(self):
        """Compute values for current batch"""
        values = []
        for i in range(self.u.trajectory.buffer_size):
            _ = self.u.trajectory[i]
            values.append(self._compute_current_frame())
        return values

    def _update_plot(self, values):
        """Append values and update plot"""
        if isinstance(values, tuple):
            values = [values]
        # update plot points
        for value in values:
            (steps, times, v) = value
            self.steps.append(steps)
            self.times.append(times)
            self.y_values.append(v)
        # update plot
        self.plot.set_data(self.x_values, self.y_values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)

    def run_every_frame(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.run_every_frame` handler"""
        self._update_plot(self._compute_current_frame())

    def run_batch(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.run_batch` handler"""
        self._update_plot(self._compute_batch())

    def get_parallel_job(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.get_parallel_job` handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_batch)()
        return delayed(self._compute_current_frame)()

    def apply_parallel_results(self, values):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.apply_parallel_results` handler"""
        self._update_plot(values)
