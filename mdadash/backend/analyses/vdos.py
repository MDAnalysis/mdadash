"""
Vibrational Density of States (VDoS)
"""

import logging
from typing import ClassVar

import matplotlib.pyplot as plt
import numpy as np
from joblib import delayed
from matplotlib.backends.backend_agg import FigureCanvasAgg
from scipy.fft import fft

from mdadash.backend.widgets.base import WidgetBase

from .common import SlidingWindowACF

logger = logging.getLogger(__name__)


class VDoS(WidgetBase):
    """

    **Vibrational Density of States**

    This widget calculates Vibrational Density of States (VDoS) from Velocity
    Autocorrelation Function (VACF).

    :class:`~mdadash.backend.analyses.common.SlidingWindowACF` is used to calculate
    a mass weighted VACF from which VDoS is calculated.

    .. important::
        VDoS requires trajectories to include velocities.

    **Inputs**

    Run mode
        The mode in which the widget is run - `serial` or `parallel`
            Default: ``serial``

    Selection
        The MDAnalysis selection phrase to run this analysis on
            Default: ``protein``

    Custom title
        Custom title for the output plot
            Default: ''

    Plot refresh frequency
        The frequency with which the plot is refreshed (every n frames).
        This only applies when the run frequency is ``every-frame``

            Default: ``1``

    **Output**

    Here is an example output plot of this widget:

    .. figure:: /_static/images/vdos_output.jpg
        :alt: VDoS output

    .. tip::
        This widget can run in parallel

    """

    name = "VDoS"
    description = "Vibrational Density of States"

    _doclink = (
        "https://mdadash.readthedocs.io/en/latest/autosummary/"
        "mdadash.backend.analyses.vdos.html"
    )

    _notes = "VDoS requires trajectories to include velocities."

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
        self.selection = "protein"
        self.ag = None
        self.has_velocities = False
        self.custom_title = None
        self.plot_refresh_count = 1
        self.plot_refresh_frequency = 1
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasAgg(self.fig)
        (self.plot,) = self.ax.plot([], [], color="red", zorder=2)
        self.ax.set_xlabel("Wavenumber (cm$^{-1}$)")
        self.ax.set_ylabel("VDoS")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self._set_title()

    def _set_title(self):
        """Set plot title"""
        title = f"VDoS of '{self.selection}'"
        self.ax.set_title(
            self.custom_title.replace("\\n", "\n") if self.custom_title else title
        )

    def _create_acf(self):
        """Create acf instance"""
        self.has_velocities = self.u.trajectory.ts.has_velocities
        if not self.has_velocities:
            raise ValueError("Trajectory has no velocities")
        self.ag = self.u.select_atoms(self.selection)
        self.acf = SlidingWindowACF(
            self.ag,
            physical_property="velocity",
            weights=self.ag.masses,
        )
        self._set_title()

    def on_post_create(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.on_post_create` handler"""
        self._set_title()

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
        elif attribute in ("_run_mode", "_run_frequency"):
            pass
        else:
            self._create_acf()

    def _calculate_vdos(self, vacf, normalize=True):
        """Calculate VDoS from VACF"""
        nCorr = len(vacf)
        tmp = np.zeros(2 * nCorr - 1, dtype=np.float32)
        tmp[:nCorr] = vacf
        tmp[nCorr:] = vacf[1:nCorr][::-1]
        fft_complex = fft(tmp)
        vdos = fft_complex[:nCorr].real.astype(np.float32)
        vdos = np.clip(vdos, a_min=0, a_max=None)
        period = self.acf.frame_dt * (2 * nCorr - 1)
        wn0 = (1.0 / period) * 33.35641
        wavenumber = np.arange(0, nCorr) * wn0
        if normalize:
            area = np.sum(vdos) * (wavenumber[1] - wavenumber[0])
            vdos = vdos / area if area > 0 else np.zeros_like(vdos)
        return wavenumber, vdos

    def _compute_current_frame(self, parallel: bool = False):
        """Run VDoS for the current timesteps window"""
        if not self.has_velocities:
            raise ValueError("Trajectory has no velocities")
        _, vacf, _, v = self.acf.run(parallel=parallel)
        x, y = self._calculate_vdos(vacf)
        return x, y, v

    def _compute_batch(self, parallel: bool = False):
        """Compute values for current batch"""
        if not self.has_velocities:
            raise ValueError("Trajectory has no velocities")
        _, vacf, _, v = self.acf.run(parallel=parallel, batch=True)
        x, y = self._calculate_vdos(vacf)
        return x, y, v

    def _update_plot(self, x, y1):
        """Update plot with computed values"""
        if self._run_frequency == "batch" or (
            self.plot_refresh_count == 1
            or self.plot_refresh_count % self.plot_refresh_frequency == 0
        ):
            self.plot.set_data(x, y1)
            self.ax.relim()
            self.ax.autoscale_view()
            self.display_canvas(self.canvas)
        self.plot_refresh_count += 1

    def run_every_frame(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.run_every_frame` handler"""
        x, y, _ = self._compute_current_frame()
        self._update_plot(x, y)

    def run_batch(self):
        """batch run handler"""
        x, y, _ = self._compute_batch()
        self._update_plot(x, y)

    def get_parallel_job(self):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.get_parallel_job` handler"""
        if self._run_frequency == "batch":
            return delayed(self._compute_batch)(parallel=True)
        return delayed(self._compute_current_frame)(parallel=True)

    def apply_parallel_results(self, values):
        """:meth:`~mdadash.backend.widgets.base.WidgetBase.apply_parallel_results` handler"""
        x, y, (v1, v2, *_) = values
        self._update_plot(x, y)
        # update acf state
        self.acf.acf_sums = v1
        self.acf.acf_counts = v2
