import logging
from typing import ClassVar

import matplotlib.pyplot as plt
import MDAnalysis as mda
import numpy as np
from IPython.display import display
from joblib import delayed
from matplotlib.collections import LineCollection

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class MSDAnalysis(WidgetBase):
    name = "MSD Analysis"
    description = "Mean squared displacement analysis"

    _notes = (
        "To correctly compute MSD using this widget, you must supply coordinates "
        "in the unwrapped convention, also known as no-jump. That is, when atoms "
        "pass the periodic boundary, they must not be wrapped back into the primary "
        "simulation cell. You can enable NoJump for the universe in the Universe "
        "Configuration section in the Settings page."
    )

    _inputs: ClassVar = [
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
        },
        {
            "attribute": "dim_type",
            "name": "Dimension type",
            "description": "Desired dimensions to be included in the MSD",
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
            "attribute": "show_diffusion_coefficient",
            "name": "Show diffusion coefficient",
            "description": "Show self-diffusion coefficient calculated from MSD",
            "type": "bool",
        },
        {
            "attribute": "show_particle_msds",
            "name": "Show particle MSDs",
            "description": "Show MSDs for individual particles of the selection",
            "type": "bool",
        },
        {
            "attribute": "log_scale",
            "name": "Log scale",
            "description": "Use a log scale for the axes",
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
        self.msd = None
        self.selection = "all"
        self.dim_type = "xyz"
        self.log_scale = False
        self.show_diffusion_coefficient = False
        self.show_particle_msds = False
        self.custom_title = None
        self._setup_plot()
        self._set_y_label()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
        # use non-empty values to prevent initial exception
        # if widget is configured to use log scale
        (self.plot,) = self.ax.plot([1], [1], color="red", zorder=2)
        self.lc = LineCollection([], colors="gray", alpha=0.2, lw=0.5, zorder=1)
        self.ax.add_collection(self.lc)
        self.ax.set_xlabel(r"Time (ps)")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self._set_title()
        self._set_y_label()
        self._set_axes_scale()

    def _set_title(self):
        """Set plot title"""
        if self.show_diffusion_coefficient:
            title = f"Diffusion coefficient of '{self.selection}'"
        else:
            title = f"MSD of '{self.selection}'"
        self.ax.set_title(self.custom_title if self.custom_title else title)

    def _set_y_label(self):
        """Set plot y label"""
        if self.show_diffusion_coefficient:
            self.ax.set_ylabel(r"Diffusion Coefficient (${\AA}^2$/ps)")
        else:
            self.ax.set_ylabel(r"MSD ($\AA^2$)")

    def _set_axes_scale(self):
        """Set axes scale"""
        self.ax.set_xscale("log" if self.log_scale else "linear")
        self.ax.set_yscale("log" if self.log_scale else "linear")

    def _create_msd(self):
        """Create msd instance"""
        self.msd = SlidingWindowMSD(
            self.u,
            select=self.selection,
            dim_type=self.dim_type,
            show_diffusion_coefficient=self.show_diffusion_coefficient,
            show_particle_msds=self.show_particle_msds,
        )
        self._set_title()
        self._set_y_label()

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._set_y_label()
        self._set_axes_scale()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._create_msd()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "custom_title":
            self._set_title()
        elif attribute == "log_scale":
            self._set_axes_scale()
        elif attribute == "_run_mode":
            pass
        else:
            self._create_msd()

    def _compute(self, parallel: bool = False):
        """Run MSD for the current timesteps window"""
        return self.msd.run(parallel=parallel)

    def _update_plot(self, x, y1, y2):
        """Update plot with computed values"""
        self.plot.set_data(x, y1)
        self.lc.set_segments(y2 if y2 is not None else [])
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw()
        display(self.fig)

    def run_every_frame(self):
        """every-frame run handler"""
        x, y1, y2, _ = self._compute()
        self._update_plot(x, y1, y2)

    def get_parallel_job(self):
        """get parallel job handler"""
        return delayed(self._compute)(parallel=True)

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        x, y1, y2, (v1, v2, v3, v4) = values
        self._update_plot(x, y1, y2)
        # update msd state
        self.msd.msd_sums = v1
        self.msd.msd_counts = v2
        if v3 is not None:
            self.msd.particle_msd_sums = v3
            self.msd.particle_msd_counts = v4


class SlidingWindowMSD:
    """Sliding Window MSD

    Calculate MSD for a sliding window of frames

    """

    def __init__(
        self,
        u: mda.Universe,
        select: str = "all",
        dim_type: str = "xyz",
        show_diffusion_coefficient: bool = False,
        show_particle_msds: bool = False,
    ):
        self.u = u
        self.select = select
        self.dim_type = dim_type
        self.show_diffusion_coefficient = show_diffusion_coefficient
        self.show_particle_msds = (
            not show_diffusion_coefficient
        ) and show_particle_msds
        self._parse_dim_type()
        self.ag = u.select_atoms(self.select)
        self.n_atoms = self.ag.atoms.n_atoms
        self.n_lags = u.trajectory.buffer_size
        self.msd_sums = np.zeros(self.n_lags, dtype=np.float64)
        self.msd_counts = np.zeros(self.n_lags, dtype=int)
        self.msd_counts[0] = 1
        if self.show_particle_msds:
            self.particle_msd_sums = np.zeros(
                (self.n_lags, self.n_atoms), dtype=np.float64
            )
            self.particle_msd_counts = np.zeros((self.n_lags, self.n_atoms), dtype=int)
            self.particle_msd_counts[0, :] = 1

    def _parse_dim_type(self):
        """Sets up the desired dimensionality."""
        keys = {
            "x": [0],
            "y": [1],
            "z": [2],
            "xy": [0, 1],
            "xz": [0, 2],
            "yz": [1, 2],
            "xyz": [0, 1, 2],
        }
        self._dim = keys[self.dim_type.lower()]

    def run(self, parallel: bool = False) -> tuple:
        """Run MSD for the current window"""

        n = len(self.u.trajectory)  # buffer / window might not be full yet
        positions_current = self.ag.positions[:, self._dim]
        for i in range(n - 1):
            lag = n - 1 - i
            _ = self.u.trajectory[i]  # set the buffered trajectory frame
            disp = positions_current - self.ag.positions[:, self._dim]
            squared_disp = np.sum(disp**2, axis=1)
            msd = np.mean(squared_disp)
            self.msd_sums[lag] += msd
            self.msd_counts[lag] += 1
            if self.show_particle_msds:
                self.particle_msd_sums[lag, :] += squared_disp
                self.particle_msd_counts[lag, :] += 1

        # We will have at least 2 frames by the time we are here.
        # frame_dt will ensure the delta_t is correct even if we have step
        # value (other than 1) configured in the universe configuration
        frame_dt = round(self.u.trajectory[1].time - self.u.trajectory[0].time, 2)
        delta_t_values = np.arange(n) * frame_dt
        avg_msds = self.msd_sums[:n] / self.msd_counts[:n]
        msds_by_particle_lines = None
        if self.show_particle_msds:
            msds_by_particle_array = (
                self.particle_msd_sums[:n, :] / self.particle_msd_counts[:n, :]
            )
            msds_by_particle_lines = np.empty((self.n_atoms, n, 2))
            msds_by_particle_lines[:, :, 0] = delta_t_values
            msds_by_particle_lines[:, :, 1] = msds_by_particle_array.T

        if self.show_diffusion_coefficient:
            diffusion_coefficient = np.gradient(avg_msds, delta_t_values) / (
                2 * len(self._dim)
            )

        return (
            delta_t_values,
            diffusion_coefficient if self.show_diffusion_coefficient else avg_msds,
            msds_by_particle_lines,
            (
                self.msd_sums,
                self.msd_counts,
                self.particle_msd_sums if self.show_particle_msds else None,
                self.particle_msd_counts if self.show_particle_msds else None,
            )
            if parallel
            else (None,) * 4,
        )
