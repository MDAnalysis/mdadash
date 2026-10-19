"""
Tests for the ACF analysis, including weighted ACF calculations (Issue #54)
"""

import MDAnalysis as mda
import numpy as np
import pytest
from MDAnalysis.coordinates.memory import MemoryReader

from mdadash.backend.analyses.acf import ACFAnalysis, SlidingWindowACF
from mdadash.backend.kernel.core import BufferedTrajectory

N_ATOMS = 3
N_FRAMES = 6
MASSES = np.array([1.0, 2.0, 3.5])
CHARGES = np.array([-0.5, 0.0, 0.7])


class _MemoryReaderWithStep(MemoryReader):
    """MemoryReader with a ``step`` entry in ``ts.data``

    ``BufferedTrajectory`` expects ``step`` in the timestep data. Returning a
    copy of the timestep from ``next`` ensures that ``BufferedTrajectory``
    copies each frame into its buffer (MemoryReader rebinds arrays instead of
    updating them in place).
    """

    def _read_next_timestep(self, ts=None):
        ts = super()._read_next_timestep(ts)
        ts.data["step"] = ts.frame
        return ts

    def next(self):
        ts = super().next()
        return ts.copy()


def _make_trajectory_data(seed=42):
    """Create controlled position / velocity arrays"""
    rng = np.random.default_rng(seed)
    # float32 to match the dtype used by the trajectory buffer
    pos = rng.random((N_FRAMES, N_ATOMS, 3)).astype(np.float32)
    vel = rng.random((N_FRAMES, N_ATOMS, 3)).astype(np.float32)
    return pos, vel


def assert_acf_allclose(actual, expected):
    """Compare ACF values within float32 buffer precision"""
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-8)


def _make_universe(pos, vel=None, masses=None, charges=None):
    """Create a universe with an in-memory buffered trajectory (frame 0 only)"""
    u = mda.Universe.empty(pos.shape[1], trajectory=True)
    if masses is not None:
        u.add_TopologyAttr("masses", masses)
    if charges is not None:
        u.add_TopologyAttr("charges", charges)
    reader = _MemoryReaderWithStep(pos, velocities=vel, order="fac", dt=1.0)
    reader.ts.data["step"] = 0
    u.trajectory = reader
    u.trajectory = BufferedTrajectory(u.trajectory, pos.shape[0], use_shm=False)
    return u


def _feed_frames(u, n_new):
    """Advance the buffered trajectory by n new frames"""
    traj = u.trajectory
    for _ in range(n_new):
        traj._prepare_for_next()
        traj.next()


def _run_serial(u, acf, n_frames):
    """Run the ACF for every frame the way the widget does"""
    traj = u.trajectory
    values = None
    for k in range(n_frames):
        if k > 0:
            traj._prepare_for_next()
            traj.next()
        values = acf.run(parallel=True)
    return values


def reference_acf(frames, weights=None, centered=False, normalized=False):
    """Independent numpy ACF used to verify SlidingWindowACF

    Matches the widget conventions: sum over dimensions followed by
    a mean over particles and time-lag pairs.
    """
    frames = np.asarray(frames, dtype=np.float64)
    if weights is not None:
        frames = frames * np.asarray(weights, dtype=np.float64)[np.newaxis, :, None]
    n = frames.shape[0]
    if centered:
        mu = np.cumsum(frames, axis=0) / np.arange(1, n + 1)[:, None, None]
        mu_squared_sum = np.sum(mu**2, axis=2)
    acfs = np.zeros(n, dtype=np.float64)
    for lag in range(n):
        products = np.sum(frames[lag:] * frames[: n - lag], axis=2)
        if centered:
            products = products - mu_squared_sum[lag:]
        acfs[lag] = np.mean(products)
    if normalized:
        acfs = acfs / acfs[0]
    return acfs


@pytest.fixture(name="pos_vel")
def pos_vel_fixture():
    """Controlled position / velocity trajectory data"""
    return _make_trajectory_data()


@pytest.fixture(name="u_vel")
def u_vel_fixture(pos_vel):
    """Buffered universe with positions, velocities, masses and charges

    All frames are already in the buffer (batch mode ready).
    """
    pos, vel = pos_vel
    u = _make_universe(pos, vel=vel, masses=MASSES, charges=CHARGES)
    _feed_frames(u, N_FRAMES - 1)
    return u


def test_acf_unweighted_matches_reference(u_vel, pos_vel):
    """Existing (unweighted) results match an independent calculation"""
    _, vel = pos_vel
    acf = SlidingWindowACF(u_vel, physical_property="velocity")
    _, values, _, _ = acf.run(parallel=True, batch=True)
    expected = reference_acf(vel)
    assert_acf_allclose(values, expected)


def test_acf_no_weight_option_preserves_behavior(u_vel, pos_vel):
    """Explicit weight='none' is identical to the default"""
    _, vel = pos_vel
    acf_default = SlidingWindowACF(u_vel, physical_property="velocity")
    _, values_default, _, _ = acf_default.run(parallel=True, batch=True)
    acf_none = SlidingWindowACF(u_vel, physical_property="velocity", weight="none")
    assert acf_none.weights is None
    _, values_none, _, _ = acf_none.run(parallel=True, batch=True)
    np.testing.assert_array_equal(values_default, values_none)
    assert_acf_allclose(values_none, reference_acf(vel))


def test_acf_mass_weighted_batch(u_vel, pos_vel):
    """Mass weighted ACF matches an independent calculation"""
    _, vel = pos_vel
    acf = SlidingWindowACF(u_vel, physical_property="velocity", weight="mass")
    np.testing.assert_allclose(acf.weights, MASSES)
    _, values, _, _ = acf.run(parallel=True, batch=True)
    expected = reference_acf(vel, weights=MASSES)
    assert_acf_allclose(values, expected)


def test_acf_mass_weighted_serial(pos_vel):
    """Mass weighted ACF matches an independent calculation (serial runs)"""
    pos, vel = pos_vel
    u = _make_universe(pos, vel=vel, masses=MASSES)
    acf = SlidingWindowACF(u, physical_property="velocity", weight="mass")
    acf.frame_dt = 1.0
    _, values, _, _ = _run_serial(u, acf, N_FRAMES)
    expected = reference_acf(vel, weights=MASSES)
    assert_acf_allclose(values, expected)


def test_acf_weighted_serial_matches_batch(pos_vel):
    """Serial and batch runs agree with weighting enabled"""
    pos, vel = pos_vel
    u_batch = _make_universe(pos, vel=vel, masses=MASSES)
    _feed_frames(u_batch, N_FRAMES - 1)
    batch_acf = SlidingWindowACF(u_batch, physical_property="velocity", weight="mass")
    _, batch_values, _, _ = batch_acf.run(parallel=True, batch=True)

    u_serial = _make_universe(pos, vel=vel, masses=MASSES)
    serial_acf = SlidingWindowACF(u_serial, physical_property="velocity", weight="mass")
    serial_acf.frame_dt = 1.0
    _, serial_values, _, _ = _run_serial(u_serial, serial_acf, N_FRAMES)
    assert_acf_allclose(serial_values, batch_values)


def test_acf_charge_weighted(u_vel, pos_vel):
    """Charge weighted ACF matches an independent calculation"""
    _, vel = pos_vel
    acf = SlidingWindowACF(u_vel, physical_property="velocity", weight="charge")
    np.testing.assert_allclose(acf.weights, CHARGES)
    _, values, _, _ = acf.run(parallel=True, batch=True)
    expected = reference_acf(vel, weights=CHARGES)
    assert_acf_allclose(values, expected)


def test_acf_sqrt_mass_weighted(u_vel, pos_vel):
    """Sqrt(mass) weighted ACF matches an independent calculation"""
    _, vel = pos_vel
    acf = SlidingWindowACF(u_vel, physical_property="velocity", weight="sqrt_mass")
    np.testing.assert_allclose(acf.weights, np.sqrt(MASSES))
    _, values, _, _ = acf.run(parallel=True, batch=True)
    expected = reference_acf(vel, weights=np.sqrt(MASSES))
    assert_acf_allclose(values, expected)


def test_acf_mass_weighted_positions(u_vel, pos_vel):
    """Mass weighting also applies to the position property"""
    pos, _ = pos_vel
    u = _make_universe(pos, masses=MASSES)
    _feed_frames(u, N_FRAMES - 1)
    acf = SlidingWindowACF(u, physical_property="position", weight="mass")
    _, values, _, _ = acf.run(parallel=True, batch=True)
    expected = reference_acf(pos, weights=MASSES)
    assert_acf_allclose(values, expected)


def test_acf_mass_weighted_centered(u_vel, pos_vel):
    """Centered weighted ACF subtracts the weighted running mean"""
    _, vel = pos_vel
    acf = SlidingWindowACF(
        u_vel, physical_property="velocity", weight="mass", centered=True
    )
    _, values, _, _ = acf.run(parallel=True, batch=True)
    expected = reference_acf(vel, weights=MASSES, centered=True)
    assert_acf_allclose(values, expected)


def test_acf_mass_weighted_centered_serial(pos_vel):
    """Centered weighted ACF matches an independent calculation (serial)"""
    pos, vel = pos_vel
    u = _make_universe(pos, vel=vel, masses=MASSES)
    acf = SlidingWindowACF(
        u, physical_property="velocity", weight="mass", centered=True
    )
    acf.frame_dt = 1.0
    _, values, _, _ = _run_serial(u, acf, N_FRAMES)
    expected = reference_acf(vel, weights=MASSES, centered=True)
    assert_acf_allclose(values, expected)


def test_acf_mass_weighted_normalized(u_vel):
    """Normalized weighted ACF is consistent with the un-normalized one"""
    acf = SlidingWindowACF(u_vel, physical_property="velocity", weight="mass")
    _, values, _, _ = acf.run(parallel=True, batch=True)
    norm_acf = SlidingWindowACF(u_vel, physical_property="velocity", weight="mass")
    _, norm_values, _, _ = norm_acf.run(normalized=True, parallel=True, batch=True)
    assert norm_values[0] == pytest.approx(1.0)
    assert_acf_allclose(norm_values, values / values[0])


def test_acf_weighted_particle_acfs(u_vel, pos_vel):
    """Particle ACFs follow the agreed weighting definition

    The weight multiplies the property of each particle at both time points,
    so a particle's ACF is scaled by the square of its weight.
    """
    _, vel = pos_vel
    acf = SlidingWindowACF(u_vel, physical_property="velocity", show_particle_acfs=True)
    _, _, lines, _ = acf.run(parallel=True, batch=True)
    particle_acfs = lines[:, :, 1]

    u2 = _make_universe(_make_trajectory_data()[0], vel=vel, masses=MASSES)
    _feed_frames(u2, N_FRAMES - 1)
    weighted_acf = SlidingWindowACF(
        u2, physical_property="velocity", weight="mass", show_particle_acfs=True
    )
    _, _, weighted_lines, _ = weighted_acf.run(parallel=True, batch=True)
    weighted_particle_acfs = weighted_lines[:, :, 1]
    assert_acf_allclose(weighted_particle_acfs, MASSES[:, None] ** 2 * particle_acfs)
    # overall ACF is the mean of the particle ACFs in both cases
    assert_acf_allclose(
        np.mean(weighted_particle_acfs, axis=0),
        reference_acf(vel, weights=MASSES),
    )


def test_acf_invalid_weight(u_vel):
    """An unknown weight option raises a clear error"""
    with pytest.raises(ValueError, match="Invalid weight"):
        SlidingWindowACF(u_vel, physical_property="velocity", weight="bogus")


def test_acf_missing_masses(pos_vel):
    """Weighting by mass fails clearly when masses are unavailable"""
    pos, _ = pos_vel
    u = _make_universe(pos)  # no masses
    with pytest.raises(ValueError, match="masses"):
        SlidingWindowACF(u, physical_property="position", weight="mass")
    with pytest.raises(ValueError, match="masses"):
        SlidingWindowACF(u, physical_property="position", weight="sqrt_mass")


def test_acf_missing_charges(pos_vel):
    """Weighting by charge fails clearly when charges are unavailable"""
    pos, _ = pos_vel
    u = _make_universe(pos, masses=MASSES)  # no charges
    with pytest.raises(ValueError, match="charges"):
        SlidingWindowACF(u, physical_property="position", weight="charge")


def test_acf_negative_masses_for_sqrt(pos_vel):
    """Sqrt(mass) weighting rejects negative masses"""
    pos, _ = pos_vel
    u = _make_universe(pos, masses=np.array([-1.0, 2.0, 3.5]))
    with pytest.raises(ValueError, match="sqrt"):
        SlidingWindowACF(u, physical_property="position", weight="sqrt_mass")


def test_acf_widget_weight_input(u_vel):
    """Widget passes the weight input to the analysis and titles the plot"""
    widget = ACFAnalysis()
    assert widget.weight == "none"
    attributes = [i["attribute"] for i in widget._inputs]
    assert "weight" in attributes
    weight_input = next(i for i in widget._inputs if i["attribute"] == "weight")
    assert weight_input["items"] == ["none", "mass", "charge", "sqrt_mass"]
    widget.u = u_vel
    widget.weight = "mass"
    widget.physical_property = "velocity"
    widget.on_post_connect()
    assert widget.acf.weight == "mass"
    np.testing.assert_allclose(widget.acf.weights, MASSES)
    assert "Mass-weighted" in widget.ax.get_title()


def test_acf_widget_invalid_weight_input(u_vel):
    """Widget input changes surface weight validation errors"""
    widget = ACFAnalysis()
    widget.u = u_vel
    widget.on_post_connect()
    # the input value is set on the widget before the handler is invoked
    widget.weight = "bogus"
    with pytest.raises(ValueError, match="Invalid weight"):
        widget.on_input_change("weight", "none", "bogus")
    # charges exist on this universe, so the analysis instance is recreated
    widget.weight = "charge"
    widget.on_input_change("weight", "bogus", "charge")
    assert widget.acf.weight == "charge"
