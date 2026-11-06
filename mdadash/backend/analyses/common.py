"""
Common Analyses Classes
"""

import logging

import MDAnalysis as mda
import numpy as np
import numpy.typing as npt
from scipy import integrate

logger = logging.getLogger(__name__)


class SlidingWindowACF:
    """

    **Sliding Window ACF**

    This class computes the ACF of a physical property for each new frame
    against the time-lag buffer / window of past N frames. The total number
    of computations for each frame is O(N).

    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        ag: mda.AtomGroup,
        physical_property: str = "position",
        dim_type: str = "xyz",
        weights: npt.NDArray | None = None,
        centered: bool = False,
        show_running_integral: bool = False,
        show_particle_acfs: bool = False,
    ):
        self.ag = ag
        self.u = ag.universe
        if weights is None:
            self.weights = np.ones(len(self.ag))
        else:
            self.weights = np.sqrt(weights)
        property_map = {
            "position": "positions",
            "velocity": "velocities",
            "force": "forces",
        }
        self.physical_property = property_map[physical_property]
        self.dim_type = dim_type
        self.centered = centered
        self.show_running_integral = show_running_integral
        self.show_particle_acfs = (not show_running_integral) and show_particle_acfs
        self._parse_dim_type()
        self.n_atoms = self.ag.atoms.n_atoms
        self.n_lags = self.u.trajectory.buffer_size
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

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def run(
        self, normalized: bool = False, parallel: bool = False, batch: bool = False
    ) -> tuple:
        """Run ACF for the current window"""

        n = len(self.u.trajectory)  # buffer / window might not be full yet
        if batch:
            array = f"_{self.physical_property}"
            frames = (
                self.weights[np.newaxis, :, np.newaxis]
                * getattr(self.u.trajectory, array)[:n, self.ag.indices][..., self._dim]
            )
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
            current = (
                self.weights[:, np.newaxis]
                * getattr(self.ag, self.physical_property)[:, self._dim]
            )
            self.running_sum += current
            self.running_count += 1
            mu = self.running_sum / self.running_count
            for i in range(frame + 1):
                lag = frame - i
                _ = self.u.trajectory[i]  # set trajectory to past frame
                previous = self.weights[:, np.newaxis] * getattr(
                    self.ag, self.physical_property
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
