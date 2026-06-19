import sys
from unittest.mock import ANY, AsyncMock

import MDAnalysis as mda
import pytest
from fastapi.testclient import TestClient
from imdclient.tests.server import InThreadIMDServer
from imdclient.tests.utils import create_default_imdsinfo_v3

from mdadash.backend.main import app, km, sio, sm, start_server
from mdadash.backend.tests.data.files import TPR, XTC
from mdadash.backend.widgets.base import WidgetBase, WidgetManager

from .utils import run_task_until_done, sio_event_emitted

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
            "step": 2,
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


async def test_widget_registration():
    # test invalid widget class
    wm = WidgetManager()

    class TestWidget1:
        pass

    with pytest.raises(ValueError, match="is not a widget class"):
        wm.register_class(TestWidget1)

    # test widget class without a name
    with pytest.raises(ValueError, match="name not specified in widget class"):

        class _TestWidget2(WidgetBase):
            pass

    # test widget class without run method
    with pytest.raises(ValueError, match="run method not found in class"):

        class _TestWidget3(WidgetBase):
            name = "TestWidget3"

    # test correct registration
    class _TestWidget4(WidgetBase):
        name = "TestWidget4"

        def run(self):
            pass

    # test duplicate widget name registraion exception
    with pytest.raises(ValueError, match="already registered"):

        class _TestWidget5(WidgetBase):
            name = "TestWidget4"

            def run(self):
                pass


async def test_dashboard_activated(_client):
    # test dashboard activated response
    sio.emit.reset_mock()
    handler = sio.handlers["/"]["dashboard:activated"]
    await run_task_until_done(handler("_sid"))
    sio.emit.assert_awaited_with("widgets:layout", ANY, to="_sid")


async def test_get_available_widgets(_client):
    # get available widgets
    handler = sio.handlers["/"]["widgets:get_available_widgets"]
    response = await run_task_until_done(handler("_sid"))
    assert response["widgets"]


async def test_add_remove_widgets(_client):
    # test add unknown widget
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "Invalid Widget", ""))
    uuid = response.get("uuid", None)
    assert uuid is None
    # test remove invalid widget
    handler = sio.handlers["/"]["widgets:remove_widget"]
    response = await run_task_until_done(handler("_sid", "invalid_uuid"))
    assert response["status"] == "error"
    # add widget 1
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "Absolute Temperature", ""))
    uuid1 = response.get("uuid", None)
    assert uuid1 is not None
    # add widget 2
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "Absolute Temperature", ""))
    uuid2 = response.get("uuid", None)
    assert uuid2 is not None
    # remove widget 1
    handler = sio.handlers["/"]["widgets:remove_widget"]
    response = await run_task_until_done(handler("_sid", uuid1))
    assert response["status"] == "ok"
    # remove widget 2
    handler = sio.handlers["/"]["widgets:remove_widget"]
    response = await run_task_until_done(handler("_sid", uuid2))
    assert response["status"] == "ok"


async def test_update_layout(_client):
    handler = sio.handlers["/"]["widgets:update_layout"]
    response = await run_task_until_done(handler("_sid", []))
    assert response == []


async def _test_input_changes(uuid, inputs, status="ok"):
    for i in inputs:
        handler = sio.handlers["/"]["widget:input_change"]
        attribute, value = i
        response = await run_task_until_done(
            handler(
                "_sid",
                {"uuid": uuid, "attribute": attribute, "value": value},
            )
        )
        assert response["status"] == status


async def test_widget_runs(_client, imd_server):
    # connect to simulation
    sm.universe_configs[0].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
        }
    )
    handler = sio.handlers["/"]["connect_to_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"

    # add widget
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "Absolute Temperature", ""))
    uuid = response.get("uuid", None)
    # check if instance is created
    assert uuid is not None
    # test input changes
    inputs = [
        ("maxlen", 10),
        ("x_type", "time"),
    ]
    await _test_input_changes(uuid, inputs)
    # test name / desc changes
    sio.emit.reset_mock()
    handler = sio.handlers["/"]["widget:name_desc_change"]
    response = await run_task_until_done(
        handler("_sid", {"uuid": uuid, "name": "name1", "description": "desc1"})
    )
    sio.emit.assert_awaited_with("widget:details", ANY)
    # test input changes in widget details
    handler = sio.handlers["/"]["widget:get_details"]
    response = await run_task_until_done(handler("_sid", uuid))
    assert response["uuid"] == uuid
    maxlen = next(
        (i for i in response["inputs"] if i.get("attribute") == "maxlen"), None
    )
    assert maxlen["value"] == 10

    # add widget with invalid input
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "ROG", ""))
    uuid = response.get("uuid", None)
    # check if instance is created
    assert uuid is not None
    # test invalid input change
    inputs = [
        ("selection", "invalid"),
    ]
    await _test_input_changes(uuid, inputs, "error")
    # test valid input change
    inputs = [
        ("selection", "resid 1"),
    ]
    await _test_input_changes(uuid, inputs)
    # retain invalid input to skip run for this widget
    inputs = [
        ("selection", "invalid"),
    ]
    await _test_input_changes(uuid, inputs, "error")

    # add widget
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "ROG", ""))
    uuid = response.get("uuid", None)
    # check if instance is created
    assert uuid is not None
    # test input changes
    inputs = [
        ("selection", "protein"),
        ("maxlen", 10),
        ("x_type", "time"),
        ("updating", True),
    ]
    await _test_input_changes(uuid, inputs)

    # add widget
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "COMDistance", ""))
    uuid = response.get("uuid", None)
    # check if instance is created
    assert uuid is not None
    # test input changes
    inputs = [
        ("selection1", "resid 1"),
        ("selection2", "resid 2"),
        ("maxlen", 10),
        ("x_type", "time"),
        ("updating", True),
    ]
    await _test_input_changes(uuid, inputs)

    # run simulation
    sio.emit.reset_mock()  # clear emit.await_args_list
    imd_server.send_frames(1, 10)
    handler = sio.handlers["/"]["resume_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"

    # check that 3 widget outputs emitted
    assert await sio_event_emitted(sio, "widgets:output", n=3)
