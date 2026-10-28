import MDAnalysis as mda
import numpy as np
import pytest

from mdadash.backend.kernel.core import BufferedTrajectory, MultiArrayBuffer
from mdadash.backend.tests.data.files import TPR, XTC


def test_buffered_trajectory():
    u = mda.Universe(TPR, XTC)
    u.trajectory = BufferedTrajectory(u, 10)
    with pytest.raises(IndexError, match="BufferedTrajectory index out of range"):
        _ = u.trajectory[10]
    with pytest.raises(IndexError, match="BufferedTrajectory index out of range"):
        _ = u.trajectory[-10]
    assert "_buffer" not in dir(u.trajectory)


def test_standalone_mab_no_shm():
    spec = {
        "_int1": {"shape": 10, "dtype": "int64"},
    }
    mab1 = MultiArrayBuffer(spec, use_shm=False)
    i1 = mab1.arrays["_int1"]
    assert np.all(i1 == 0)
    i1.fill(2)
    state = mab1.getstate()
    assert "buffer" in state
    assert "shm_name" not in state
    state["buffer"] = np.ones(10, dtype=np.int64)
    mab2 = MultiArrayBuffer.setstate(state)
    i2 = mab2.arrays["_int1"]
    assert np.all(i2 == 1)
    i1[0] = 3
    assert i2[0] != 3


def test_standalone_mab_shm():
    spec = {
        "_int1": {"shape": 10, "dtype": "int64"},
    }
    mab1 = MultiArrayBuffer(spec, use_shm=True)
    i1 = mab1.arrays["_int1"]
    assert np.all(i1 == 0)
    i1.fill(2)
    state = mab1.getstate()
    assert "buffer" not in state
    assert "shm_name" in state
    mab2 = MultiArrayBuffer.setstate(state)
    i2 = mab2.arrays["_int1"]
    assert np.all(i2 == 2)
    i1[0] = 3
    assert i2[0] == 3
    mab1.cleanup()
