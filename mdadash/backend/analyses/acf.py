import logging
from typing import ClassVar

import matplotlib.pyplot as plt
import MDAnalysis as mda
import numpy as np
from IPython.display import display
from joblib import delayed
from matplotlib.collections import LineCollection
from scipy import integrate

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class ACFAnalysis(WidgetBase):
    name = "ACF"
    description = "Autocorrelation Function"

    _notes = (
        "To correctly compute positional ACF using this widget, you must supply "
        "coordinates in the unwrapped convention, also known as no-jump. That is, "
        "when atoms pass the periodic boundary, they must not be wrapped back into "
        "the primary simulation cell. You can enable NoJump for the universe in the "
        "Universe Configuration section in the Settings page."
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
            "attribute": "physical_property",
            "name": "Physical property",
            "description": "Physical property to analyze",
            "type": "select",
            "items": [
                "velocity",
                "position",
                "force",
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
    ]

    def __init__(self):
        super().__init__()
        self.acf = None
        self.physical_property = "velocity"
        self.selection = "all"
        self.dim_type = "xyz"
        self.centered = False
        self.show_running_integral = False
        self.show_particle_acfs = False
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
            title = (
                f"Running integral of {self.physical_property.title()} "
                f"ACF of '{self.selection}'"
            )
        else:
            title = f"{self.physical_property.title()} ACF of '{self.selection}'"
        self.ax.set_title(self.custom_title if self.custom_title else title)

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

    def _create_acf(self):
        """Create acf instance"""
        self.acf = SlidingWindowACF(
            self.u,
            select=self.selection,
            physical_property=self.physical_property,
            dim_type=self.dim_type,
            centered=self.centered,
            show_running_integral=self.show_running_integral,
            show_particle_acfs=self.show_particle_acfs,
        )
        self._set_title()
        self._set_y_label()

    def on_post_create(self):
        """on_post_create handler"""
        self._set_title()
        self._set_y_label()

    def on_post_connect(self):
        """on_post_connect handler"""
        self._create_acf()

    def on_input_change(self, attribute, _old_value, new_value):
        """on_input_change handler"""
        if attribute == "custom_title":
            self._set_title()
        elif attribute in ("normalized", "_run_mode"):
            pass
        else:
            self._create_acf()

    def _compute(self, normalized: bool = False, parallel: bool = False):
        """Run ACF for the current timesteps window"""
        return self.acf.run(normalized=normalized, parallel=parallel)

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


class SlidingWindowACF:
    """Sliding Window ACF

    Calculate ACF for a sliding window of frames

    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        u: mda.Universe,
        physical_property: str = "velocity",
        select: str = "all",
        dim_type: str = "xyz",
        centered: bool = False,
        show_running_integral: bool = False,
        show_particle_acfs: bool = False,
    ):
        self.u = u
        property_map = {
            "velocity": "velocities",
            "position": "positions",
            "force": "forces",
        }
        self.physical_property = property_map[physical_property]
        self.select = select
        self.dim_type = dim_type
        self.centered = centered
        self.show_running_integral = show_running_integral
        self.show_particle_acfs = (not show_running_integral) and show_particle_acfs
        self._parse_dim_type()
        self.ag = u.select_atoms(self.select)
        self.n_atoms = self.ag.atoms.n_atoms
        self.n_lags = u.trajectory.buffer_size
        self.frame_dt = None
        self.running_sum = np.zeros_like(
            getattr(self.ag, self.physical_property)[:, self._dim], dtype=np.float64
        )
        self.running_count = 0
        self.acf_sums = np.zeros(self.n_lags, dtype=np.float64)
        self.acf_counts = np.zeros(self.n_lags, dtype=int)
        if self.show_particle_acfs:
            self.particle_acf_sums = np.zeros(
                (self.n_lags, self.n_atoms), dtype=np.float64
            )
            self.particle_acf_counts = np.zeros((self.n_lags, self.n_atoms), dtype=int)

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

    # pylint: disable=too-many-locals
    def run(self, normalized: bool = False, parallel: bool = False) -> tuple:
        """Run ACF for the current window"""

        n = len(self.u.trajectory)  # buffer / window might not be full yet
        current = getattr(self.ag, self.physical_property)[:, self._dim]
        self.running_sum += current
        self.running_count += 1
        mu = self.running_sum / self.running_count
        for i in range(n):
            lag = n - 1 - i
            _ = self.u.trajectory[i]  # set trajectory to past frame
            previous = getattr(self.ag, self.physical_property)
            acf = current * previous[:, self._dim]
            if self.centered:
                acf = acf - (mu**2)
            acf_sum = np.sum(acf, axis=-1)
            self.acf_sums[lag] += np.mean(acf_sum)
            self.acf_counts[lag] += 1
            if self.show_particle_acfs:
                self.particle_acf_sums[lag, :] += acf_sum
                self.particle_acf_counts[lag, :] += 1

        if self.frame_dt is None:
            # We will have at least 2 frames by the time we are here.
            # frame_dt will ensure the delta_t is correct even if we have step
            # value (other than 1) configured in the universe configuration
            self.frame_dt = self.u.trajectory[1].time - self.u.trajectory[0].time
        delta_t_values = np.arange(n) * self.frame_dt
        avg_acfs = self.acf_sums[:n] / self.acf_counts[:n]

        if normalized:
            avg_acfs = avg_acfs / avg_acfs[0]

        acfs_by_particle_lines = None
        if self.show_particle_acfs:
            acfs_by_particle_array = (
                self.particle_acf_sums[:n, :] / self.particle_acf_counts[:n, :]
            )
            if normalized:
                acfs_by_particle_array = (
                    acfs_by_particle_array / acfs_by_particle_array[0]
                )
            acfs_by_particle_lines = np.empty((self.n_atoms, n, 2))
            acfs_by_particle_lines[:, :, 0] = delta_t_values
            acfs_by_particle_lines[:, :, 1] = acfs_by_particle_array.T

        if self.show_running_integral:
            running_integral = integrate.cumulative_trapezoid(
                avg_acfs,
                delta_t_values,
                initial=0,
            ) / len(self._dim)

        return (
            delta_t_values,
            running_integral if self.show_running_integral else avg_acfs,
            acfs_by_particle_lines,
            (
                self.acf_sums,
                self.acf_counts,
                self.running_sum,
                self.running_count,
                self.particle_acf_sums if self.show_particle_acfs else None,
                self.particle_acf_counts if self.show_particle_acfs else None,
            )
            if parallel
            else (None,) * 4,
        )
