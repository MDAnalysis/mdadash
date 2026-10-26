"""
Global pytest fixtures
"""

# Use this file if you need to share any fixtures
# across multiple modules
# More information at
# https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session

from unittest.mock import AsyncMock

import MDAnalysis as mda
import pytest
from fastapi.testclient import TestClient
from imdclient.tests.server import InThreadIMDServer
from imdclient.tests.utils import create_default_imdsinfo_v3

from mdadash.backend import main
from mdadash.backend.main import MDADash, app, sio
from mdadash.backend.tests.data.files import TPR, XTC


@pytest.fixture(autouse=True)
def mock_sio_emit(monkeypatch):
    mock_emit = AsyncMock()
    monkeypatch.setattr(main.sio, "emit", mock_emit)
    return mock_emit


@pytest.fixture(scope="session", name="_client")
def client_fixture(tmp_path_factory):
    # _client fixture is needed to ensure app lifecycle is run
    temp_dir = tmp_path_factory.mktemp("mdadash")
    state_file = temp_dir / "mdadash.state.json"
    main.mdadash = MDADash(sio, state_file)
    with TestClient(app) as client:
        yield client


@pytest.fixture(name="imd_server")
def imd_server_fixture():
    u = mda.Universe(TPR, XTC)
    server = InThreadIMDServer(u.trajectory)
    info = create_default_imdsinfo_v3()
    info.velocities = False
    info.forces = False
    info.box = True
    server.set_imdsessioninfo(info)
    server.handshake_sequence("localhost", first_frame=True)
    yield server
    server.cleanup()
