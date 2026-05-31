import sys

import MDAnalysis as mda
import pytest
from fastapi.testclient import TestClient
from imdclient.tests.server import InThreadIMDServer
from imdclient.tests.utils import create_default_imdsinfo_v3

from mdadash.backend.main import app, km, sm, start_server
from mdadash.backend.tests.data.files import TPR, XTC

from .utils import run_task_until_done


@pytest.fixture(scope="session", name="client")
def client_fixture():
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


def test_start_server(mocker):
    # mock the command line params
    mocker.patch.object(
        sys,
        "argv",
        [
            "main.py",
            "--topology",
            str(TPR),
            "--trajectory",
            "imd://localhost:8889",
        ],
    )
    # uvicorn.run is a blocking call, so we need to
    # mock it so as to not block the tests. An alternative is
    # to run the real server in a separate thread
    mock_uvicorn_run = mocker.patch("uvicorn.run")
    start_server()
    mock_uvicorn_run.assert_called_once_with(
        "mdadash.backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


def test_main_server_url_access(client):
    # main dashboard url
    response = client.get("/")
    assert response.status_code == 200
    # favicon.ico url
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    # test catch all for any other url
    response = client.get("/catch/all")
    assert response.status_code == 200


def test_simulation_connect_invalid_universe_config(client):
    # test connect with no config
    response = client.get("/api/connect/0")
    assert response.json()["status"] == "error"


def test_simulation_connect_disconnect(client, imd_server):
    # configure required config for universe
    sm.state["universe_config"][0].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
            "kwargs": {
                "arg1": "value1",
            },
        }
    )
    # test connect
    response = client.get("/api/connect/0")
    assert response.json()["status"] == "connected"
    # test disconnect
    response = client.get("/api/disconnect/0")
    assert response.json()["status"] == "disconnected"


def test_simulation_connect_disconnect_invalid_universe_id(client):
    # test connect
    response = client.get("/api/connect/1")
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid universe id"}
    # test disconnect
    response = client.get("/api/disconnect/1")
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid universe id"}


async def test_km_unregistered_msg_type():
    # test unregistered msg handler
    response = await run_task_until_done(
        km.send_message_await_response("unregistered_msg_type", {})
    )
    assert response["status"] == "error"


async def test_kernel_universe_access(imd_server):
    # connect to the simulation
    uid = 0
    sm.state["universe_config"][uid].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
        }
    )
    data = {"uid": uid, "config": sm.state["universe_config"][uid]}
    response = await run_task_until_done(km.connect_to_simulation(data))
    assert response["status"] == "connected"
    # check universe manager access in kernel
    code = """
from mdadash.backend.kernel.core import um

try:
    # invalid index access
    u = um[1]
except ValueError as e:
    print(e)
# check length and index access
print(len(um), um[0].atoms.n_atoms)
# iterate universe manager
for u in um:
    print(u.atoms.n_atoms)
"""
    response = await run_task_until_done(km.execute_code(code))
    assert response == "Invalid index 1 of 1 items\n1 47681\n47681\n"


async def test_kernel_execute_code_errors():
    # check code errors in kernel code execution
    code = """
print(x)
"""
    response = await run_task_until_done(km.execute_code(code))
    assert response == "name 'x' is not defined"
