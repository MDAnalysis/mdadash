"""
Helix Analysis
"""

import logging
import warnings
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
from IPython.display import display
from joblib import delayed
from MDAnalysis.analysis.helix_analysis import HELANAL

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class HelixAnalysis(WidgetBase):
    """

    **Helix Analysis**

    This widget uses `MDAnalysis.analysis.helix_analysis.HELANAL`_ to perform `Helix
    analysis`_ and plot different computed properties.

    Plots can be chosen for the following computed properties:

    * ``local_twists``
    * ``local_nres_per_turn``
    * ``local_bends``
    * ``local_heights``
    * ``local_screw_angles``

    .. _MDAnalysis.analysis.helix_analysis.HELANAL: https://docs.mdanalysis.org/
        stable/documentation_pages/analysis/helix_analysis.html
        #MDAnalysis.analysis.helix_analysis.HELANAL

    .. _Helix analysis: https://userguide.mdanalysis.org/stable/examples/
        analysis/structure/helanal.html

    **Inputs**

    Run frequency
        The frequency with which the widget is run - `every-frame` or `batch`
            Default: ``every-frame``

    Run mode
        The mode in which the widget is run - `serial` or `parallel`
            Default: ``serial``

    Selection
        MDAnalysis selection phrase
            Default: ``resid 1:10 and name CA``

        .. note::
            HELANAL is designed to work on the alpha-carbon atoms of protein residues
            and the selection must return at least 9 residues

    Property
        Computed property to plot
            Default: ``local_twists``

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

    .. figure:: /_static/images/helix_analysis_output.jpg
        :alt: Helix Analysis output

    .. tip::
        This widget supports batching and can run in parallel

    """

    name = "Helix Analysis"
    description = "Helix analysis using HELANAL"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.helix_analysis.html"
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
            "attribute": "selection",
            "name": "Selection",
            "description": "MDAnalysis selection phrase",
            "type": "str",
            "validations": ["required"],
        },
        {
            "attribute": "property",
            "name": "Property",
            "description": "Computed property to plot",
            "type": "select",
            "items": [
                "local_twists",
                "local_nres_per_turn",
                "local_bends",
                "local_heights",
                "local_screw_angles",
            ],
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
        self.selection = "resid 1:10 and name CA"
        self.property = "local_twists"
        self.ha = None
        self.title = "Helix Analysis"
        self.custom_title = None
        self.default_maxlen = 100
        self.maxlen = self.default_maxlen
        self.x_type = "time"
        self.x_values = None
        self.y_labels = {
            "local_twists": "Average local twist (degrees)",
            "local_nres_per_turn": "Average residues per turn",
            "local_bends": "Average local bends (degrees)",
            "local_heights": "Average rise of each local helix (Å)",
            "local_screw_angles": "Average local screw angle (degrees)",
        }
        self._setup_plot()
        self._reset_plot_values()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        (self.plot,) = self.ax.plot([], [])
        self.ax.grid(True)
        self._set_title()

    def _reset_plot_values(self):
        """Reset plot values"""
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self.ax.set_ylabel(self.y_labels[self.property])
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

    def _create_ha(self):
        """Update atom groups when selection phrases change"""
        self.ha = HELANAL(self.u, select=self.selection)
        self.title = f"Helix analysis of '{self.selection}'"
        self._set_title()

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._reset_plot_values()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._create_ha()

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
        elif attribute in ("selection", "property"):
            self._reset_plot_values()
            self._create_ha()

    def _compute_current_frame(self):
        """Compute values for current frame"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            self.ha.run(frames=[self.u.trajectory.frame])
        results = getattr(self.ha.results, self.property)
        mean_values = results.mean(axis=1)
        return (
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
            mean_values[0],
        )

    def _compute_batch(self):
        """Compute values for current batch"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            self.ha.run()
        results = getattr(self.ha.results, self.property)
        mean_values = results.mean(axis=1)
        values = []
        for i, v in enumerate(mean_values):
            _ = self.u.trajectory[i]
            values.append(
                (
                    self.u.trajectory.ts.data["step"],
                    self.u.trajectory.ts.data["time"],
                    v,
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
