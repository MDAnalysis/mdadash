"""
Distance between two center-of-masses
"""

import logging
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display
from joblib import delayed
from MDAnalysis.exceptions import NoDataError
from MDAnalysis.lib.distances import calc_bonds

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class COMDistance(WidgetBase):
    """

    **COM Distance**

    This widget shows the distance between two center-of-masses (COMs).

    **Inputs**

    Run frequency
        .. compound::
            The frequency with which the widget is run - `every-frame` or `batch`
                Default: ``every-frame``

    Run mode
        The mode in which the widget is run - `serial` or `parallel`
            Default: ``serial``

    Selection 1
        First MDAnalysis selection phrase
            Default: ``protein``

    Selection 2
        Second MDAnalysis selection phrase
            Default: ``resid 1``

    Periodic
        Select with periodic boundary conditions
            Default: ``True``

    Updating
        Update selection during each timestep
            Default: ``False``

    Custom title
        Custom title for the plot
            Default: ''

    Max values
        Max values to show in plot
            Default: ``100``

    Max distance
        Max distance for alert check
            Default: ``50.0``

    Alert if distance > 'Max distance
        Create an alert if the above condition is met
            Default: ``False``

    Pause simulation if distance > 'Max distance'
        Pause the simulation if the above condition is met
            Default: ``False``

    X-axis
        X-axis value - `time` or `step`
            Default: ``time``

    **Output**

    Here is an example output plot of this widget:

    .. figure:: /_static/images/com_distance_output.jpg
        :alt: COM Distance output

    .. tip::
        This widget supports batching and can run in parallel

    """

    name = "COMDistance"
    description = "Distance between two COMs"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.com_distance.html"
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
            "attribute": "max_distance_pause",
            "name": "Pause simulation if distance > 'Max distance'",
            "type": "bool",
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
        self.selection1 = "protein"
        self.selection2 = "resid 1"
        self.periodic = True
        self.updating = False
        self.ag1 = None
        self.ag2 = None
        self.max_distance = 50.0
        self.max_distance_alert = False
        self.max_distance_pause = False
        self.title = "Distance between COMs"
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
        self.ax.set_ylabel("Distance (Å)")
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
        self.ag1 = self.u.select_atoms(
            self.selection1, periodic=self.periodic, updating=self.updating
        )
        self.ag2 = self.u.select_atoms(
            self.selection2, periodic=self.periodic, updating=self.updating
        )
        self.title = f"{self.selection1} <---> {self.selection2}"
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
        reset_plot = False
        if attribute == "maxlen":
            if new_value < 0:
                self.maxlen = self.default_maxlen
            reset_plot = True
        elif attribute == "x_type":
            self._set_x_values()
        elif attribute == "custom_title":
            self._set_title()
        elif attribute in ("selection1", "selection2"):
            self._update_selections()
            reset_plot = True
        elif attribute in ("periodic", "updating"):
            self._update_selections()
        if reset_plot:
            self._reset_plot_values()

    def _compute_current_frame(self):
        """Compute for current frame"""
        try:
            com1 = self.ag1.center_of_mass(unwrap=True)
            com2 = self.ag2.center_of_mass(unwrap=True)
        except (NoDataError, ValueError):  # pragma: no cover
            # unwrap can fail if there is no bonds info or box info
            com1 = self.ag1.center_of_mass()
            com2 = self.ag2.center_of_mass()
        return (
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
            calc_bonds(com1, com2, box=self.u.dimensions),
        )

    def _compute_batch(self):
        """Compute for current batch"""
        values = []
        for i in range(self.u.trajectory.buffer_size):
            _ = self.u.trajectory[i]
            values.append(self._compute_current_frame())
        return values

    def _update_plot(self, values):
        """Append values and update plot"""
        if isinstance(values, tuple):
            values = [values]
        alerted = False
        paused = False
        for value in values:
            (steps, times, dist) = value
            self.steps.append(steps)
            self.times.append(times)
            self.y_values.append(dist)
            if dist > self.max_distance:
                if self.max_distance_alert and not alerted:
                    self.alert(f"Distance between '{self.title}' > {self.max_distance}")
                    alerted = True
                if self.max_distance_pause and not paused:
                    self.pause_simulation()
                    paused = True
        # update plot points
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
