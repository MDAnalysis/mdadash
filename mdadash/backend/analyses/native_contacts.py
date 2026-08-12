"""
Native Contacts Analysis
"""

import logging
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display
from joblib import delayed
from MDAnalysis.analysis import contacts

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class NativeContacts(WidgetBase):
    """

    **Native Contacts Analysis**

    This widget uses `MDAnalysis.analysis.contacts.Contacts`_ to calculate `Fraction
    of native contacts`_ between two contacting groups.

    .. note:: The two contacting AtomGroups in their reference conformation are created
        when this widget instance is created or whenever the inputs for the above Class
        from below are updated.

    .. _MDAnalysis.analysis.contacts.Contacts: https://docs.mdanalysis.org/stable/
        documentation_pages/analysis/contacts.html#MDAnalysis.analysis.contacts.Contacts

    .. _Fraction of native contacts: https://userguide.mdanalysis.org/stable/
        examples/analysis/distances_and_contacts/contacts_native_fraction.html

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
            Default: ``protein and name CA``

    Contacting Group 2
        MDAnalysis selection phrase of second group
            Default: ``protein and name CA``

    Radius
        Radius within which contacts exist in refgroup
            Default: ``4.5``

    Method
        Method to use for cut off - `hard_cut`, `soft_cut` or `radius_cut`
            Default: ``hard_cut``

    PBC
        Uses periodic boundary conditions to calculate distances
            Default: ``True``

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

    .. figure:: /_static/images/native_contacts_output.jpg
        :alt: Native Contacts output

    .. tip::
        This widget supports batching and can run in parallel

    """

    name = "Native Contacts"
    description = "Native Contacts Analysis"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.native_contacts.html"
    )

    _notes = (
        "The two contacting AtomGroups in their reference conformation are created "
        "when this widget instance is created or whenever the inputs for the "
        "MDAnalysis.analysis.contacts.Contacts class from below are updated."
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
            "description": "Radius within which contacts exist in refgroup",
            "type": "float",
        },
        {
            "attribute": "method",
            "name": "Method",
            "description": "Method to use for cut off",
            "type": "select",
            "items": [
                "hard_cut",
                "soft_cut",
                "radius_cut",
            ],
        },
        {
            "attribute": "pbc",
            "name": "PBC",
            "description": "Uses periodic boundary conditions to calculate distances",
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
        self.selection1 = "protein and name CA"
        self.selection2 = "protein and name CA"
        self.radius = 4.5
        self.method = "hard_cut"
        self.pbc = True
        self.contacts = None
        self.refgroup_ag1 = None
        self.refgroup_ag2 = None
        self.title = "Native Contacts"
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
        self.ax.set_ylabel("Fraction of contacts")
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

    def _create_contacts(self):
        """Update atom groups when selection phrases change"""
        self.refgroup_ag1 = self.u.select_atoms(self.selection1)
        self.refgroup_ag2 = self.u.select_atoms(self.selection2)
        self.contacts = contacts.Contacts(
            self.u,
            select=(self.selection1, self.selection2),
            refgroup=(self.refgroup_ag1, self.refgroup_ag2),
            radius=self.radius,
            method=self.method,
            pbc=self.pbc,
        )
        self.title = (
            f"Native contacts between\n'{self.selection1}' and '{self.selection2}'"
        )
        self._set_title()
        self._update_plot(self._compute_current_frame())

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._reset_plot_values()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._create_contacts()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            self._reset_plot_values()
        elif attribute == "x_type":
            self._set_x_values()
        elif attribute == "custom_title":
            self._set_title()
        elif attribute in (
            "selection1",
            "selection2",
            "radius",
            "method",
            "pbc",
        ):
            self._reset_plot_values()
            self._create_contacts()

    def _compute_current_frame(self):
        """Compute values for current frame"""
        self.contacts.run(frames=[self.u.trajectory.frame])
        return (
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
            self.contacts.results.timeseries[0][1],
        )

    def _compute_batch(self):
        """Compute values for current batch"""
        self.contacts.run()
        values = []
        for i, (_, q) in enumerate(self.contacts.results.timeseries):
            _ = self.u.trajectory[i]
            values.append(
                (
                    self.u.trajectory.ts.data["step"],
                    self.u.trajectory.ts.data["time"],
                    q,
                )
            )
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
        """every-frame run handler"""
        self._update_plot(self._compute_current_frame())

    def run_batch(self):
        """batch run handler"""
        self._update_plot(self._compute_batch())

    def get_parallel_job(self):
        """get parallel job handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_batch)()
        return delayed(self._compute_current_frame)()

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        self._update_plot(values)
