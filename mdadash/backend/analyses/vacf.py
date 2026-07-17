import logging

import matplotlib.pyplot as plt
import MDAnalysis as mda
import numpy as np
from IPython.display import display
from joblib import delayed
from matplotlib.collections import LineCollection
from scipy import integrate

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class VACFAnalysis(WidgetBase):
    name = "VACF"
    description = "Velociy Autocorrelation Function"

    _inputs = [
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
            "description": "Desired dimensions to be included in the VACF",
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
            "attribute": "show_running_integral",
            "name": "Show running integral",
            "description": "Show running integral of the VACF",
            "type": "bool",
        },
        {
            "attribute": "show_particle_vacfs",
            "name": "Show particle VACFs",
            "description": "Show VACFs for individual particles of the selection",
            "type": "bool",
        },
        {
            "attribute": "normalized",
            "name": "Normalize",
            "description": "Normalize VACF values",
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
        self.vacf = None
        self.selection = "all"
        self.dim_type = "xyz"
        self.show_running_integral = False
        self.show_particle_vacfs = False
        self.normalized = False
        self.custom_title = None
        self._setup_plot()

    def _setup_plot(self):
        """Setup matplotlib plot"""
        self.fig, self.ax = plt.subplots()
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
            title = f"Running integral of VACF of '{self.selection}'"
        else:
            title = f"VACF of '{self.selection}'"
        self.ax.set_title(self.custom_title if self.custom_title else title)

    def _set_y_label(self):
        """Set plot y label"""
        if self.show_running_integral:
            self.ax.set_ylabel(r"Running integral of VACF (${\AA}^2$/ps)")
        else:
            self.ax.set_ylabel(r"Velocity Autocorrelation Function (${\AA}^2/ps^2$)")

    def _create_vacf(self):
        """Create vacf instance"""
        self.vacf = SlidingWindowVACF(
            self.u,
            select=self.selection,
            dim_type=self.dim_type,
            show_running_integral=self.show_running_integral,
            show_particle_vacfs=self.show_particle_vacfs,
        )
        self._set_title()
        self._set_y_label()

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._set_y_label()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._create_vacf()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "custom_title":
            self._set_title()
        elif attribute in ("normalized", "_run_mode"):
            pass
        else:
            self._create_vacf()

    def _compute(self, normalized: bool = False, parallel: bool = False):
        """Run VACF for the current timesteps window"""
        return self.vacf.run(normalized=normalized, parallel=parallel)

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
        x, y1, y2, _ = self._compute(normalized=self.normalized)
        self._update_plot(x, y1, y2)

    def get_parallel_job(self):
        """get parallel job handler"""
        return delayed(self._compute)(normalized=self.normalized, parallel=True)

    def apply_parallel_results(self, values):
        """apply parallel results handler"""
        x, y1, y2, (v1, v2, v3, v4) = values
        self._update_plot(x, y1, y2)
        # update vacf state
        self.vacf.vacf_sums = v1
        self.vacf.vacf_counts = v2
        if v3 is not None:
            self.vacf.particle_vacf_sums = v3
            self.vacf.particle_vacf_counts = v4


class SlidingWindowVACF:
    """Sliding Window VACF

    Calculate VACF for a sliding window of frames

    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        u: mda.Universe,
        select: str = "all",
        dim_type: str = "xyz",
        show_running_integral: bool = False,
        show_particle_vacfs: bool = False,
    ):
        self.u = u
        self.select = select
        self.dim_type = dim_type
        self.show_running_integral = show_running_integral
        self.show_particle_vacfs = (not show_running_integral) and show_particle_vacfs
        self._parse_dim_type()
        self.ag = u.select_atoms(self.select)
        self.n_atoms = self.ag.atoms.n_atoms
        self.n_lags = u.trajectory.buffer_size
        self.vacf_sums = np.zeros(self.n_lags)
        self.vacf_counts = np.zeros(self.n_lags, dtype=int)
        self.vacf_counts[0] = 1
        if self.show_particle_vacfs:
            self.particle_vacf_sums = np.zeros((self.n_lags, self.n_atoms))
            self.particle_vacf_counts = np.zeros((self.n_lags, self.n_atoms), dtype=int)
            self.particle_vacf_counts[0, :] = 1

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

    def run(self, normalized: bool = False, parallel: bool = False) -> tuple:
        """Run VACF for the current window"""

        n = len(self.u.trajectory)  # buffer / window might not be full yet
        velocities_current = self.ag.velocities[:, self._dim]
        for i in range(n):
            lag = n - 1 - i
            _ = self.u.trajectory[i]  # set the buffered trajectory frame
            veloc = velocities_current * self.ag.velocities[:, self._dim]
            sum_veloc = np.sum(veloc, axis=-1)
            self.vacf_sums[lag] += np.mean(sum_veloc)
            self.vacf_counts[lag] += 1
            if self.show_particle_vacfs:
                self.particle_vacf_sums[lag, :] += sum_veloc
                self.particle_vacf_counts[lag, :] += 1

        # We will have at least 2 frames by the time we are here.
        # frame_dt will ensure the delta_t is correct even if we have step
        # value (other than 1) configured in the universe configuration
        frame_dt = round(self.u.trajectory[1].time - self.u.trajectory[0].time, 2)
        delta_t_values = np.arange(n) * frame_dt
        avg_vacfs = self.vacf_sums[:n] / self.vacf_counts[:n]
        if normalized:
            avg_vacfs = avg_vacfs / avg_vacfs[0]
        vacfs_by_particle_lines = None
        if self.show_particle_vacfs:
            vacfs_by_particle_array = (
                self.particle_vacf_sums[:n, :] / self.particle_vacf_counts[:n, :]
            )
            if normalized:
                vacfs_by_particle_array = (
                    vacfs_by_particle_array / vacfs_by_particle_array[0]
                )
            vacfs_by_particle_lines = np.empty((self.n_atoms, n, 2))
            vacfs_by_particle_lines[:, :, 0] = delta_t_values
            vacfs_by_particle_lines[:, :, 1] = vacfs_by_particle_array.T

        if self.show_running_integral:
            running_integral = integrate.cumulative_trapezoid(
                avg_vacfs,
                delta_t_values,
                initial=0,
            ) / len(self._dim)

        return (
            delta_t_values,
            running_integral if self.show_running_integral else avg_vacfs,
            vacfs_by_particle_lines,
            (
                self.vacf_sums,
                self.vacf_counts,
                self.particle_vacf_sums if self.show_particle_vacfs else None,
                self.particle_vacf_counts if self.show_particle_vacfs else None,
            )
            if parallel
            else (None,) * 4,
        )
