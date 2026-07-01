import json
import sys
from unittest.mock import ANY, AsyncMock

import MDAnalysis as mda
import pytest
from fastapi.testclient import TestClient
from imdclient.tests.server import InThreadIMDServer
from imdclient.tests.utils import create_default_imdsinfo_v3

from mdadash.backend import main
from mdadash.backend.kernel.core import BufferedTrajectory
from mdadash.backend.main import MDADash, app, sio, start_server
from mdadash.backend.state.manager import StateManager
from mdadash.backend.tests.data.files import TPR, XTC
from mdadash.backend.widgets.base import WidgetBase, WidgetManager

from .utils import (
    add_widget,
    check_input_changes,
    connect_to_simulation,
    disconnect_from_simulation,
    duplicate_widget,
    pause_simulation,
    remove_widget,
    resume_simulation,
    run_task_until_done,
    sio_event_emitted,
)

sio.emit = AsyncMock()


@pytest.fixture(scope="session", name="_client")
def client_fixture(tmp_path_factory):
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
            "--state-file",
            "",
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
    main.mdadash.sm.universe_configs[0].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
            "kwargs": [["arg1", "value1"], ["bool1", "true"], ["bool2", "false"]],
            "step": 2,
        }
    )
    # test connect
    handler = sio.handlers["/"]["connect_to_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"
    # test resume
    await resume_simulation(imd_server)
    # test pause
    await pause_simulation()
    # test disconnect
    await disconnect_from_simulation()


async def test_km_unregistered_msg_type(_client):
    # test unregistered msg handler
    response = await run_task_until_done(
        main.mdadash.km.send_message_await_response("unregistered_msg_type", {})
    )
    assert response["status"] == "error"


async def test_kernel_universe_access(_client, imd_server):
    await connect_to_simulation(imd_server)
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
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == "Invalid index 1 of 1 items\n1 47681\n47681\n"


async def test_kernel_execute_code_errors(_client):
    # check code errors in kernel code execution
    code = """
print(x)
"""
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == "name 'x' is not defined"


async def test_socketio_connect_disconnect(imd_server):
    await connect_to_simulation(imd_server)
    # connect
    handler = sio.handlers["/"]["connect"]
    response = await run_task_until_done(handler("_sid", {}))
    assert response is None
    # disconnect
    handler = sio.handlers["/"]["disconnect"]
    response = await run_task_until_done(handler("_sid"))
    assert response is None
    await resume_simulation(imd_server)
    await disconnect_from_simulation()


async def test_update_settings(_client):
    # update settings
    handler = sio.handlers["/"]["update:settings"]
    settings = main.mdadash.sm.settings.copy()
    await run_task_until_done(handler("_sid", settings))
    # assert the updated value is not a reference
    assert settings is not main.mdadash.sm.settings
    assert settings is not main.mdadash.sm.state["settings"]
    # assert values are same
    assert settings == main.mdadash.sm.settings
    # update n_jobs
    settings["dashboard_config"]["n_jobs"] = 5
    handler = sio.handlers["/"]["update:settings"]
    await run_task_until_done(handler("_sid", settings))
    # assert values are updated
    assert settings == main.mdadash.sm.settings


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

        class _TestWidget3a(WidgetBase):
            name = "TestWidget3"

    # test widget class without valid run method
    with pytest.raises(ValueError, match="run method not found in class"):

        class _TestWidget3b(WidgetBase):
            name = "TestWidget3"
            run_per_frame = None  # not a callable

    # test correct registration - per-frame
    class _TestWidget4a(WidgetBase):
        name = "TestWidget4a"

        def run_per_frame(self):
            pass

    # test correct registration - batch
    class _TestWidget4b(WidgetBase):
        name = "TestWidget4b"

        def run_batch(self, batch_size):
            pass

    # test duplicate widget name registraion exception
    with pytest.raises(ValueError, match="already registered"):

        class _TestWidget5(WidgetBase):
            name = "TestWidget4a"

            def run_per_frame(self):
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


async def test_recreate_widget_instances(_client):
    # test valid state
    main.mdadash.sm.widgets.update(
        {
            "uuid": {
                "uid": 0,
                "class_name": "COMDistance",
                "inputs": [
                    {"attribute": "selection1", "value": "protein", "error": ""},
                ],
            },
        },
    )
    response = await main.mdadash.km.recreate_widget_instances()
    assert response["status"] == "ok"
    await remove_widget("uuid")
    # test invalid state
    main.mdadash.sm.widgets.update(
        {
            "uuid": {
                "class_name": "InvalidClassName",
            },
        },
    )
    response = await main.mdadash.km.recreate_widget_instances()
    assert response["status"] == "error"


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
    uuid1 = await add_widget("Absolute Temperature")
    # add widget 2
    uuid2 = await add_widget("Total Energy")
    # remove widget 1
    await remove_widget(uuid1)
    # remove widget 2
    await remove_widget(uuid2)


async def test_duplicate_widgets(_client, imd_server):
    await connect_to_simulation(imd_server)
    # add a widget
    uuid1 = await add_widget("Absolute Temperature")
    # duplicate the widget
    uuid2 = await duplicate_widget(uuid1)
    await remove_widget(uuid1)
    await remove_widget(uuid2)
    # add widget and set wrong inputs
    uuid1 = await add_widget("ROG")
    inputs = [
        ("selection", "invalid"),
    ]
    await check_input_changes(uuid1, inputs, "error")
    # duplicate the widget
    uuid2 = await duplicate_widget(uuid1)
    await remove_widget(uuid1)
    await remove_widget(uuid2)
    await resume_simulation(imd_server)
    await disconnect_from_simulation()


async def test_update_layout(_client):
    handler = sio.handlers["/"]["widgets:update_layout"]
    response = await run_task_until_done(handler("_sid", []))
    assert response == []


def test_buffered_trajectory():
    u = mda.Universe(TPR, XTC)
    u.trajectory = BufferedTrajectory(u.trajectory, 10)
    with pytest.raises(ValueError, match="index should be <= 0"):
        _ = u.trajectory[1]
    with pytest.raises(ValueError, match="Out of range of buffer"):
        _ = u.trajectory[-10]
    assert "_buffer" not in dir(u.trajectory)


async def test_widget_input_changes(_client):
    uuid = await add_widget("Absolute Temperature")
    # test input changes
    inputs = [
        ("maxlen", -1),
        ("x_type", "time"),
    ]
    await check_input_changes(uuid, inputs)
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
    assert maxlen["value"] == 100
    await remove_widget(uuid)


async def test_widget_invalid_inputs(_client, imd_server):
    await connect_to_simulation(imd_server)
    uuid = await add_widget("ROG")
    # test invalid input change
    inputs = [
        ("selection", "invalid"),
    ]
    await check_input_changes(uuid, inputs, "error")
    # test valid input change
    inputs = [
        ("selection", "resid 1"),
    ]
    await check_input_changes(uuid, inputs)
    # retain invalid input to skip run for this widget
    inputs = [
        ("selection", "invalid"),
    ]
    await check_input_changes(uuid, inputs, "error")
    await resume_simulation(imd_server)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_energies(_client, imd_server):
    uuid = await add_widget("Absolute Temperature")
    await connect_to_simulation(imd_server)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_com_distance(_client, imd_server):
    uuid = await add_widget("COMDistance")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection1", "resid 1"),
        ("selection2", "resid 2"),
        ("maxlen", -1),
        ("x_type", "time"),
        ("updating", True),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_rog_serial_per_frame(_client, imd_server):
    await connect_to_simulation(imd_server)
    uuid = await add_widget("ROG")
    inputs = [
        ("selection", "protein"),
        ("maxlen", -1),
        ("x_type", "time"),
        ("updating", True),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_rog_serial_batch(_client, imd_server):
    uuid = await add_widget("ROG")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_rog_parallel_per_frame(_client, imd_server):
    uuid = await add_widget("ROG")
    inputs = [
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    await connect_to_simulation(imd_server)
    await resume_simulation(imd_server)
    timeout = 30 if sys.platform == "win32" else 20
    assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_rog_parallel_batch(_client, imd_server):
    uuid = await add_widget("ROG")
    inputs = [
        ("_run_frequency", "batch"),
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    await connect_to_simulation(imd_server)
    await resume_simulation(imd_server)
    timeout = 30 if sys.platform == "win32" else 20
    assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
    await remove_widget(uuid)
    await disconnect_from_simulation()


def test_state_load(tmp_path):
    # test with no state file
    sm = StateManager("")
    assert sm.state is not None
    # test with invalid (emtpy) file
    temp_file = tmp_path / "mdadash1.state.json"
    temp_file.touch()
    sm = StateManager(temp_file)
    assert sm.state is not None
    # test with invalid json (no mdadash key) file
    temp_file = tmp_path / "mdadash2.state.json"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump({}, f)
    sm = StateManager(temp_file)
    assert sm.state is not None
    # test with valid json
    state = {"app": "mdadash"}
    temp_file = tmp_path / "mdadash3.state.json"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f)
    sm = StateManager(temp_file)
    assert sm.state is not None
