"""
Autocorrelation Function (ACF)
"""

import logging
from typing import ClassVar

import matplotlib.pyplot as plt
import MDAnalysis as mda
import numpy as np
from joblib import delayed
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection
from MDAnalysis.exceptions import NoDataError
from scipy import integrate

from mdadash.backend.widgets.base import WidgetBase

logger = logging.getLogger(__name__)


class ACFAnalysis(WidgetBase):
    """

    **Autocorrelation Function**

    This widget calculates time-lag autocorrelation for different physical properties.

    The following physical properties are supported:

    * position
    * velocity
    * force

    A custom :class:`SlidingWindowACF` is used to calculate autocorrelation of chosen
    physical property for each new frame against the time-lag buffer / window of past frames.

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

    Weight
        Weighting factor applied to the physical property before the
        autocorrelation is computed - `none`, `mass`, `charge` or `sqrt_mass`

            Default: ``none``

        .. tip::
            The weight `w` multiplies the physical property of each particle
            at both time points, i.e., the ACF of ``w * property`` is
            computed. For example, a mass weighted velocity ACF is
            ``<(m_i * v_i(t)) . (m_i * v_i(t + tau))>_t``, so a particle's
            contribution scales with the square of its weight.

        .. caution::
            Weighting by `mass` or `sqrt_mass` requires the topology to have
            masses and weighting by `charge` requires it to have charges

    Selection
        The MDAnalysis selection phrase to run this analysis on
            Default: ``all``

    Dimension type
        The desired dimensions to include in the ACF -
        `xyz`, `xy`, `yz`, `xz`, `x`, `y` or `z`

            Default: ``xyz``

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
            "attribute": "weight",
            "name": "Weight",
            "description": (
                "Weighting factor applied to the physical property - "
                "none, mass, charge or sqrt_mass"
            ),
            "type": "select",
            "items": [
                "none",
                "mass",
                "charge",
                "sqrt_mass",
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
        self.weight = "none"
        self.selection = "all"
        self.dim_type = "xyz"
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

    _weight_titles: ClassVar = {
        "mass": "Mass-weighted",
        "charge": "Charge-weighted",
        "sqrt_mass": "Sqrt-mass-weighted",
    }

    def _weight_label(self):
        """Internal: Plot label prefix for the selected weight"""
        weight_title = self._weight_titles.get(self.weight)
        return f"{weight_title} " if weight_title else ""

    def _set_title(self):
        """Set plot title"""
        label = self._weight_label()
        if self.show_running_integral:
            title = (
                f"Running integral of {label}{self.physical_property.title()} "
                f"ACF of '{self.selection}'"
            )
        else:
            title = (
                f"{label}{self.physical_property.title()} "
                f"ACF of '{self.selection}'"
            )
        self.ax.set_title(
            self.custom_title.replace("\\n", "\n") if self.custom_title else title
        )

    def _set_y_label(self):
        """Set plot y label"""
        label = self._weight_label()
        if self.show_running_integral:
            self.ax.set_ylabel(
                f"Running integral of {label}{self.physical_property.title()} ACF"
            )
        else:
            self.ax.set_ylabel(
                f"{label}{self.physical_property.title()} "
                f"Autocorrelation Function"
            )

    def _create_acf(self):
        """Create acf instance"""
        self.acf = SlidingWindowACF(
            self.u,
            select=self.selection,
            physical_property=self.physical_property,
            weight=self.weight,
            dim_type=self.dim_type,
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


class SlidingWindowACF:
    """

    **Sliding Window ACF**

    This class computes the ACF of a physical property for each new frame
    against the time-lag buffer / window of past N frames. The total number
    of computations for each frame is O(N).

    The physical property can optionally be weighted by a per-particle
    factor (mass, charge or sqrt of mass). The weight multiplies the
    property of each particle at both time points, i.e., the ACF of
    ``weight * property`` is computed. With no weight, the unweighted
    ACF of the physical property is computed.

    """

    _weight_attrs: ClassVar = {
        "mass": ("masses", False),
        "sqrt_mass": ("masses", True),
        "charge": ("charges", False),
    }

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        u: mda.Universe,
        physical_property: str = "position",
        select: str = "all",
        weight: str = "none",
        dim_type: str = "xyz",
        centered: bool = False,
        show_running_integral: bool = False,
        show_particle_acfs: bool = False,
    ):
        self.u = u
        property_map = {
            "position": "positions",
            "velocity": "velocities",
            "force": "forces",
        }
        self.physical_property = property_map[physical_property]
        self.select = select
        self.weight = weight
        self.dim_type = dim_type
        self.centered = centered
        self.show_running_integral = show_running_integral
        self.show_particle_acfs = (not show_running_integral) and show_particle_acfs
        self._parse_dim_type()
        self.ag = u.select_atoms(self.select)
        self.weights = self._get_weights()
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

    def _get_weights(self):
        """Internal: Resolve the per-particle weighting factors

        Returns None if weighting is disabled.

        """
        if self.weight is None or self.weight == "none":
            return None
        if self.weight not in self._weight_attrs:
            options = ", ".join(["none"] + list(self._weight_attrs))
            raise ValueError(
                f"Invalid weight '{self.weight}'. Valid options: {options}"
            )
        attr, sqrt = self._weight_attrs[self.weight]
        try:
            values = np.asarray(getattr(self.ag, attr), dtype=np.float64)
        except NoDataError as e:
            raise ValueError(
                f"Weighting by '{self.weight}' requires {attr} for the "
                f"selection '{self.select}', but the topology does not "
                f"provide them"
            ) from e
        if sqrt and np.any(values < 0):
            raise ValueError(
                f"Weighting by '{self.weight}' requires non-negative masses"
            )
        return np.sqrt(values) if sqrt else values

    def _apply_weights(self, values):
        """Internal: Multiply per-particle property values by the weights

        ``values`` is of shape (n_atoms, n_dims) or (n_frames, n_atoms, n_dims)

        """
        if self.weights is None:
            return values
        if values.ndim == 3:
            return values * self.weights[np.newaxis, :, np.newaxis]
        return values * self.weights[:, np.newaxis]

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

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def run(
        self, normalized: bool = False, parallel: bool = False, batch: bool = False
    ) -> tuple:
        """Run ACF for the current window"""

        n = len(self.u.trajectory)  # buffer / window might not be full yet
        if batch:
            array = f"_{self.physical_property}"
            frames = getattr(self.u.trajectory, array)[:n, self.ag.indices][
                ..., self._dim
            ]
            frames = self._apply_weights(frames)
            if self.centered:
                batch_sums = np.cumsum(frames, axis=0)
                batch_counts = np.arange(1, n + 1)[:, np.newaxis, np.newaxis]
                mu_matrix = (self.running_sum[np.newaxis, :, :] + batch_sums) / (
                    self.running_count + batch_counts
                )
                mu_squared_sum = np.sum(mu_matrix**2, axis=2)
                self.running_sum += batch_sums[-1]
                self.running_count += n
            for lag in range(n):
                current = frames[lag:]
                previous = frames[: n - lag]
                acf_sum = np.sum(current * previous, axis=2)
                if self.centered:
                    acf_sum = acf_sum - mu_squared_sum[lag:]
                self.acf_sums[lag] += np.sum(np.mean(acf_sum, axis=1))
                self.acf_counts[lag] += n - lag
                if self.show_particle_acfs:
                    self.particle_acf_sums[lag, :] += np.sum(acf_sum, axis=0)
                    self.particle_acf_counts[lag, :] += n - lag
        else:
            frame = n - 1
            _ = self.u.trajectory[frame]
            current = self._apply_weights(
                getattr(self.ag, self.physical_property)[:, self._dim]
            )
            self.running_sum += current
            self.running_count += 1
            mu = self.running_sum / self.running_count
            for i in range(frame + 1):
                lag = frame - i
                _ = self.u.trajectory[i]  # set trajectory to past frame
                previous = self._apply_weights(
                    getattr(self.ag, self.physical_property)
                )
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
