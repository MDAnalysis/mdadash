import platform
import sys
from unittest.mock import AsyncMock

import MDAnalysis as mda
import pytest
from fastapi.testclient import TestClient
from imdclient.tests.server import InThreadIMDServer
from imdclient.tests.utils import create_default_imdsinfo_v3

from mdadash.backend.main import app, km, sio, sm, start_server
from mdadash.backend.tests.data.files import TPR, XTC

from .utils import run_task_until_done

sio.emit = AsyncMock()


@pytest.fixture(scope="session", name="_client")
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
            "imd://localhost:1234",
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
    )


def test_main_server_url_access(_client):
    # main dashboard url
    response = _client.get("/")
    assert response.status_code == 200
    # favicon.ico url
    response = _client.get("/favicon.ico")
    assert response.status_code == 200
    # test catch all for any other url
    response = _client.get("/catch/all")
    assert response.status_code == 200


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Needs debugging of occasional timeouts only on Windows",
)
async def test_simulation_connect_invalid_universe_config(_client):
    # _client fixture is needed to ensure app lifecycle is run
    # test connect with no config
    handler = sio.handlers["/"]["connect_to_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "error"


async def test_simulation_connectivity(_client, imd_server):
    # configure required config for universe
    sm.universe_configs[0].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
            "kwargs": [["arg1", "value1"]],
        }
    )
    # test connect
    handler = sio.handlers["/"]["connect_to_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"
    # test resume
    imd_server.send_frames(1, 10)
    handler = sio.handlers["/"]["resume_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"
    # test pause
    handler = sio.handlers["/"]["pause_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"
    # test disconnect
    handler = sio.handlers["/"]["disconnect_from_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"


async def test_km_unregistered_msg_type():
    # test unregistered msg handler
    response = await run_task_until_done(
        km.send_message_await_response("unregistered_msg_type", {})
    )
    assert response["status"] == "error"


async def test_kernel_universe_access(imd_server):
    # connect to the simulation
    sm.universe_configs[0].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
        }
    )
    response = await run_task_until_done(km.connect_to_simulations())
    assert response["status"] == "ok"
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


async def test_socketio_connect_disconnect():
    # connect
    handler = sio.handlers["/"]["connect"]
    response = await run_task_until_done(handler("_sid", {}))
    assert response is None
    # disconnect
    handler = sio.handlers["/"]["disconnect"]
    response = await run_task_until_done(handler("_sid"))
    assert response is None


async def test_update_settings():
    # connect
    handler = sio.handlers["/"]["update:settings"]
    settings = sm.settings.copy()
    await run_task_until_done(handler("_sid", settings))
    # assert the updated value is not a reference
    assert settings is not sm.settings
    assert settings is not sm.state["settings"]
    # assert values are same
    assert settings == sm.settings
