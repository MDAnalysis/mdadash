"""
Autocorrelation Function (ACF)
"""

import logging
import sys
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np
from joblib import delayed
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection

from mdadash.backend.widgets.base import WidgetBase

from .common import SlidingWindowACF

logger = logging.getLogger(__name__)


class ACFAnalysis(WidgetBase):
    """

    **Autocorrelation Function**

    This widget calculates time-lag autocorrelation for different physical properties.

    The following physical properties are supported:

    * position
    * velocity
    * force

    A custom :class:`~mdadash.backend.analyses.common.SlidingWindowACF` is used to calculate
    autocorrelation of chosen physical property for each new frame against the time-lag
    buffer / window of past frames.

    .. important::
        To correctly compute positional ACF using this widget, you must supply
        coordinates in the unwrapped convention, also known as no-jump. That is,
        when atoms pass the periodic boundary, they must not be wrapped back into
        the primary simulation cell. You can enable NoJump for the universe in the
        Universe Configuration section in the Settings page of the dashboard.

    **Inputs**

    Run mode
        The mode in which the widget is run - `serial` or `parallel`
            Default: ``serial``

    Physical property
        The physical property to analyze - `position`, `velocity` or `force`
            Default: ``position``

    Selection
        The MDAnalysis selection phrase to run this analysis on
            Default: ``all``

    Dimension type
        The desired dimensions to include in the ACF -
        `xyz`, `xy`, `yz`, `xz`, `x`, `y` or `z`

            Default: ``xyz``

    Weights:
        Weights to multiply the physical property with.

        One of ``None``, ``masses``, ``charges``, ``Custom function``

            Default: ``None``

    Custom weights function:
        Name of the custom weights function to use to obtain weights. This is applicable
        only when the Weights input above is set to ``Custom function``.

        A custom function can be defined using the Notebook interface. The function should
        take one parameter (MDAnalysis ``AtomGroup``) as input and should return a 1D array
        of weights of the same length as the passed in selection ``AtomGroup``.

        Example:

            .. code-block:: python

                import numpy as np

                def acf_custom_weights_function(ag):
                    return np.sqrt(ag.masses)

            Default: ''

    Centered
        Use mean subtacted values to calculate ACF
            Default: ``False``

        .. caution::
            A running updated mean based on data processed so far is used.
            The number of data samples must be much greater than the lag-time
            window for this to be accurate

    Show running integral
        Show running integral of the ACF
            Default: ``False``

        .. tip::
            Using this option with the `velocity` physical property, i.e., (VACF)
            can be used to observe the diffusion coefficient value in the output plot

    Show particle ACFs
        Show ACFs for individual particles of the selection in the plot
            Default: ``False``

        .. caution::
            Enabling this option for large selections can slow down the
            analysis and generation of the plot data

    Normalize
        Normalize the computed ACF values
            Default: ``False``

    Custom title
        Custom title for the output plot
            Default: ''

    Plot refresh frequency
        The frequency with which the plot is refreshed (every n frames).
        This only applies when the run frequency is ``every-frame``

            Default: ``1``

    **Output**

    Here is an example output plot of this widget:

    .. figure:: /_static/images/acf_output.jpg
        :alt: ACF output

    .. tip::
        This widget can run in parallel

    """

    name = "ACF"
    description = "Autocorrelation Function"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.acf.html"
    )

    _notes = (
        "To correctly compute positional ACF using this widget, you must supply "
        "coordinates in the unwrapped convention, also known as no-jump. That is, "
        "when atoms pass the periodic boundary, they must not be wrapped back into "
        "the primary simulation cell. You can enable NoJump for the universe in the "
        "Universe Configuration section in the Settings page."
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
            "attribute": "physical_property",
            "name": "Physical property",
            "description": "Physical property to analyze",
            "type": "select",
            "items": [
                "position",
                "velocity",
                "force",
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
            "attribute": "dim_type",
            "name": "Dimension type",
            "description": "Desired dimensions to be included in the ACF",
            "type": "select",
            "items": [
                "xyz",
                "xy",
                "yz",
                "xz",
                "x",
                "y",
                "z",
            ],
        },
        {
            "attribute": "weights",
            "name": "Weights",
            "description": "Weights to multiply the physical property with",
            "type": "select",
            "items": [
                "None",
                "masses",
                "charges",
                "Custom function",
            ],
        },
        {
            "attribute": "weights_function",
            "name": "Custom weights function",
            "description": "Custom function to obtain weights",
            "type": "str",
        },
        {
            "attribute": "centered",
            "name": "Centered",
            "description": (
                "Use mean subtracted values to calculate ACF. "
                "A running updated mean based on data processed so far is used. "
                "The number of data samples must be much greater than the lag-time "
                "window for this to be accurate."
            ),
            "type": "bool",
        },
        {
            "attribute": "show_running_integral",
            "name": "Show running integral",
            "description": "Show running integral of the ACF",
            "type": "bool",
        },
        {
            "attribute": "show_particle_acfs",
            "name": "Show particle ACFs",
            "description": "Show ACFs for individual particles of the selection",
            "type": "bool",
        },
        {
            "attribute": "normalized",
            "name": "Normalize",
            "description": "Normalize ACF values",
            "type": "bool",
        },
        {
            "attribute": "custom_title",
            "name": "Custom title",
            "description": "Custom title for the plot",
            "type": "str",
        },
        {
            "attribute": "plot_refresh_frequency",
            "name": "Plot refresh frequency",
            "description": "The frequency with which the plot is refreshed (every n frames)",
            "type": "int",
            "validations": ["min:1"],
        },
    ]

    def __init__(self):
        super().__init__()
        self.acf = None
        self.physical_property = "position"
        self.selection = "all"
        self.dim_type = "xyz"
        self.weights = "None"
        self.weights_function = ""
        self.ag = None
        self.weights_array = None
        self.centered = False
        self.show_running_integral = False
        self.show_particle_acfs = False
        self.normalized = False
        self.custom_title = None
        self.plot_refresh_count = 1
        self.plot_refresh_frequency = 1
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasAgg(self.fig)
        (self.plot,) = self.ax.plot([], [], color="red", zorder=2)
        self.lc = LineCollection([], colors="gray", alpha=0.2, lw=0.5, zorder=1)
        self.ax.add_collection(self.lc)
        self.ax.set_xlabel(r"Time (ps)")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self._set_title()
        self._set_y_label()

    def _set_title(self):
        """Set plot title"""
        if self.show_running_integral:
            title = (
                f"Running integral of {self.physical_property.title()} "
                f"ACF of '{self.selection}'"
            )
        else:
            title = f"{self.physical_property.title()} ACF of '{self.selection}'"
        self.ax.set_title(
            self.custom_title.replace("\\n", "\n") if self.custom_title else title
        )

    def _set_y_label(self):
        """Set plot y label"""
        if self.show_running_integral:
            self.ax.set_ylabel(
                f"Running integral of {self.physical_property.title()} ACF"
            )
        else:
            self.ax.set_ylabel(
                f"{self.physical_property.title()} Autocorrelation Function"
            )

    def _get_weights(self):
        if self.weights in ("masses", "charges"):
            if not hasattr(self.ag, self.weights):  # pragma: no cover
                raise ValueError(f"{self.weights} not available")
            return getattr(self.ag, self.weights)
        if self.weights == "Custom function":
            weights = None
            main = sys.modules.get("__main__")
            func_name = self.weights_function.strip()
            if not hasattr(main, func_name):
                raise ValueError(f"Custom function '{func_name}' not defined")
            func = getattr(main, func_name)
            if not callable(func):
                raise ValueError(f"'{func_name}' is not a callable function")
            try:
                weights = func(self.ag)
            except Exception as e:  # pylint: disable=broad-exception-caught
                raise ValueError("Error invoking custom weights function") from e
            if np.shape(weights) != (len(self.ag),):
                raise ValueError(f"Weights is not a 1D array of size {len(self.ag)}")
            return weights
        return None

    def _create_acf(self):
        """Create acf instance"""
        self.ag = self.u.select_atoms(self.selection)
        self.weights_array = self._get_weights()
        self.acf = SlidingWindowACF(
            self.ag,
            physical_property=self.physical_property,
            dim_type=self.dim_type,
            weights=self.weights_array,
            centered=self.centered,
            show_running_integral=self.show_running_integral,
            show_particle_acfs=self.show_particle_acfs,
        )
        self._set_title()
        self._set_y_label()

    def on_post_create(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_create` handler"""
        self._set_title()
        self._set_y_label()

    def on_post_connect(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_connect` handler"""
        self._create_acf()
        self.plot_refresh_count = 1

    def on_input_change(self, attribute, _old_value, new_value):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_input_change` handler"""
        if attribute == "custom_title":
            self._set_title()
        elif attribute == "plot_refresh_frequency":
            self.plot_refresh_count = 1
        elif attribute in ("normalized", "_run_mode", "_run_frequency"):
            pass
        else:
            self._create_acf()

    def _compute_current_frame(self, normalized: bool = False, parallel: bool = False):
        """Run ACF for the current timesteps window"""
        return self.acf.run(normalized=normalized, parallel=parallel)

    def _compute_batch(self, normalized: bool = False, parallel: bool = False):
        """Compute values for current batch"""
        return self.acf.run(normalized=normalized, parallel=parallel, batch=True)

    def _update_plot(self, x, y1, y2):
        """Update plot with computed values"""
        if self._run_frequency == "batch" or (
            self.plot_refresh_count == 1
            or self.plot_refresh_count % self.plot_refresh_frequency == 0
        ):
            self.plot.set_data(x, y1)
            self.lc.set_segments(y2 if y2 is not None else [])
            self.ax.relim()
            self.ax.autoscale_view()
            self.display_canvas(self.canvas)
        self.plot_refresh_count += 1

    def run_every_frame(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.run_every_frame` handler"""
        x, y1, y2, _ = self._compute_current_frame(normalized=self.normalized)
        self._update_plot(x, y1, y2)

    def run_batch(self):
        """batch run handler"""
        x, y1, y2, _ = self._compute_batch(normalized=self.normalized)
        self._update_plot(x, y1, y2)

    def get_parallel_job(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.get_parallel_job` handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_batch)(
                normalized=self.normalized, parallel=True
            )
        return delayed(self._compute_current_frame)(
            normalized=self.normalized, parallel=True
        )

    def apply_parallel_results(self, values):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.apply_parallel_results` handler"""
        x, y1, y2, (v1, v2, v3, v4, v5, v6) = values
        self._update_plot(x, y1, y2)
        # update acf state
        self.acf.acf_sums = v1
        self.acf.acf_counts = v2
        self.acf.running_sum = v3
        self.acf.running_count = v4
        if v5 is not None:
            self.acf.particle_acf_sums = v5
            self.acf.particle_acf_counts = v6
