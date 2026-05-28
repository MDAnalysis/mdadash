import MDAnalysis as mda
import pytest
from fastapi.testclient import TestClient
from imdclient.tests.server import InThreadIMDServer
from imdclient.tests.utils import create_default_imdsinfo_v3

from mdadash.backend.main import app, sm
from mdadash.backend.tests.data.files import TPR, XTC

client = TestClient(app)


def test_main_app():
    response = client.get("/")
    assert response.status_code == 200


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


def test_simulation_connect_disconnect(imd_server):
    sm.state["universe_config"].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
        }
    )
    with TestClient(app) as c:
        # test connect
        response = c.get("/api/connect")
        assert response.json()["status"] == "connected"
        # test disconnect
        response = c.get("/api/disconnect")
        assert response.json()["status"] == "disconnected"
