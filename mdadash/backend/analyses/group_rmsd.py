"""
Group RMSD Analysis
"""

import logging
import sys
from collections import deque
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np
from joblib import delayed
from matplotlib.backends.backend_agg import FigureCanvasAgg
from MDAnalysis.analysis import rms

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class GroupRMSD(WidgetBase):
    """

    **Group RMSD Analysis**

    This widget uses `MDAnalysis.analysis.rms.RMSD`_ to calculate `RMSD`_ of a
    group of selections. The reference positions used by this widget are the initial
    positions of the selection available for the trajectory from the reference
    timestep (:attr:`~mdadash.backend.kernel.core.BufferedTrajectory.ref_u`).

    .. note:: If you use trajectory data from simulations performed under periodic boundary
        conditions then you must make your molecules whole before performing RMSD calculations so
        that the centers of mass of the mobile and reference structure are properly superimposed.

        You can add custom transformations to the universe in the Universe Configuration section
        in the Settings page of the dasboard.

    .. _MDAnalysis.analysis.rms.RMSD: https://docs.mdanalysis.org/stable/
        documentation_pages/analysis/rms.html#MDAnalysis.analysis.rms.RMSD

    .. _RMSD: https://userguide.mdanalysis.org/stable/
        examples/analysis/alignment_and_rms/rmsd.html

    **Inputs**

    Run frequency
        .. compound::
            The frequency with which the widget is run - `every-frame` or `batch`
                Default: ``every-frame``

    Run mode
        The mode in which the widget is run - `serial` or `parallel`
            Default: ``serial``

    Selection
        MDAnalysis selection phrase
            Default: ``protein``

    Group selections
        Comma separated group selection phrases

    Labels:
        Comma separated labels to use in legend
            Default: ''

    Weights:
        Weights to use to compute weighted average.

        One of ``None``, ``masses``, ``Custom function``

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

                def rmsd_custom_weights_function(ag):
                    return np.sqrt(ag.masses)

            Default: ''

    Custom title
        Custom title for the plot
            Default: ''

    Max values
        Max values to show in plot
            Default: ``100``

    Plot refresh frequency
        The frequency with which the plot is refreshed (every n frames).
        This only applies when the run frequency is ``every-frame``

            Default: ``1``

    Reset on connect
        Reset the plot on every connect
            Default: ``False``

    X-axis
        X-axis value - `time` or `step`
            Default: ``time``

    **Output**

    Here is an example output plot of this widget:

    .. figure:: /_static/images/group_rmsd_output.jpg
        :alt: Group RMSD output

    .. tip::
        This widget supports batching and can run in parallel

    """

    name = "Group RMSD"
    description = "Group RMSD of selections"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.group_rmsd.html"
    )

    _notes = (
        "If simulations are performed under periodic boundary conditions "
        "then you must make your molecules whole before performing RMSD "
        "calculations so that the centers of mass of the mobile and reference "
        "structure are properly superimposed. You can add custom transformations "
        "to the universe in the Universe Configuration section in the Settings page.\n\n"
        "Note: The reference positions used by this widget are the initial positions "
        "of the selection available for the trajectory from the reference "
        "timestep (`u.trajectory.ref_u`)."
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
            "attribute": "group_selections",
            "name": "Group selections",
            "description": "Comma separated group selection phrases",
            "type": "str",
        },
        {
            "attribute": "labels",
            "name": "Labels",
            "description": "Comma separated labels to use in legend",
            "type": "str",
        },
        {
            "attribute": "weights",
            "name": "Weights",
            "description": "Weights to use to compute weighted average",
            "type": "select",
            "items": [
                "None",
                "masses",
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
            "validations": ["min:0"],
        },
        {
            "attribute": "plot_refresh_frequency",
            "name": "Plot refresh frequency",
            "description": "The frequency with which the plot is refreshed (every n frames)",
            "type": "int",
            "validations": ["min:1"],
        },
        {
            "attribute": "reset_on_connect",
            "name": "Reset on connect",
            "description": "Reset the plot on every connect",
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
        self.selection = "backbone"
        self.group_selections = (
            "backbone and (resid 1-29 or resid 60-121 or resid 160-214),"
            "backbone and resid 122-159,"
            "backbone and resid 30-59"
        )
        self.labels = "backbone,CORE,LID,NMP"
        self.rmsd = None
        self.weights = "None"
        self.weights_function = ""
        self.ag = None
        self.title = "RMSD"
        self.custom_title = None
        self.default_maxlen = 100
        self.maxlen = self.default_maxlen
        self.plot_refresh_count = 1
        self.plot_refresh_frequency = 1
        self.reset_on_connect = False
        self.x_type = "time"
        self.x_values = None
        self._setup_plot()
        self._reset_plot_values()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasAgg(self.fig)
        groups = self.group_selections
        labels = self.labels
        groups = [g.strip() for g in groups.split(",")] if groups.strip() else []
        labels = [l.strip() for l in labels.split(",")] if labels.strip() else []
        self.plots = []
        for i in range(1 + len(groups)):
            label = labels[i] if i < len(labels) else f"Group {i}"
            (line,) = self.ax.plot([], [], label=label)
            self.plots.append(line)
        self.ax.set_ylabel("RMSD (Å)")
        self.ax.legend(loc="upper left")
        self.ax.grid(True)
        self._set_title()

    def _reset_plot_values(self):
        """Reset plot values"""
        self.steps = deque(maxlen=self.maxlen)
        self.times = deque(maxlen=self.maxlen)
        self.y_values = deque(maxlen=self.maxlen)
        self.plot_refresh_count = 1
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

    def _get_weights(self):
        if self.weights == "masses":
            return "mass"
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

    def _update_selection(self):
        """Update atom groups when selection phrase changes"""
        groups = (
            self.group_selections.split(",") if self.group_selections.strip() else []
        )
        self.ag = self.u.select_atoms(self.selection)
        self.rmsd = rms.RMSD(
            self.u,
            self.u.trajectory.ref_u,
            select=self.selection,
            groupselections=groups if len(groups) > 0 else None,
            weights=self._get_weights(),
        )
        self._setup_plot()
        self._reset_plot_values()
        self.title = f"Group RMSD aligned on '{self.selection}'"
        self._set_title()
        self._update_plot(self._compute_current_frame())

    def on_post_create(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_create` handler"""
        self._set_title()
        self._reset_plot_values()

    def on_post_connect(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_connect` handler"""
        self.plot_refresh_count = 1
        if self.reset_on_connect:  # pragma: no cover
            self._reset_plot_values()
        self._update_selection()

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
        elif attribute in (
            "selection",
            "group_selections",
            "labels",
            "weights",
            "weights_function",
        ):
            self._reset_plot_values()
            self._update_selection()
        elif attribute == "plot_refresh_frequency":
            self.plot_refresh_count = 1

    def _compute_current_frame(self):
        """Compute values for current frame"""
        with self.u.trajectory.return_ts_copies():
            self.rmsd.run(frames=[self.u.trajectory.frame])
        rmsd_values = self.rmsd.results.rmsd[0, 2:]
        return (
            self.u.trajectory.ts.data["step"],
            self.u.trajectory.ts.data["time"],
            rmsd_values,
        )

    def _compute_batch(self):
        """Compute values for current batch"""
        with self.u.trajectory.return_ts_copies():
            self.rmsd.run()
        steps = self.u.trajectory._steps
        times = self.u.trajectory._times
        return list(zip(steps, times, self.rmsd.results.rmsd[:, 2:]))

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
        if self._run_frequency == "batch" or (
            self.plot_refresh_count == 1
            or self.plot_refresh_count % self.plot_refresh_frequency == 0
        ):
            data = np.array(self.y_values)
            for plot, y_value in zip(self.plots, data.T):
                plot.set_data(self.x_values, y_value)
            self.ax.relim()
            self.ax.autoscale_view()
            self.display_canvas(self.canvas)
        self.plot_refresh_count += 1

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
