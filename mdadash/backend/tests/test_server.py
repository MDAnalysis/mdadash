# pylint: disable=too-many-lines
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
from mdadash.backend.tests.data.files import TPR, TRR, XTC
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


@pytest.fixture(name="imd_server_trr")
def imd_server_fixture_trr():
    u = mda.Universe(TPR, TRR)
    server = InThreadIMDServer(u.trajectory)
    info = create_default_imdsinfo_v3()
    info.velocities = True
    info.forces = False
    info.box = True
    server.set_imdsessioninfo(info)
    server.handshake_sequence("localhost", first_frame=True)
    yield server
    server.cleanup()


def test_start_server_imd_trajectory(mocker):
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
            "--clear-alerts",
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


def x_test_start_server_file_trajectory(mocker):
    # mock the command line params
    mocker.patch.object(
        sys,
        "argv",
        [
            "main.py",
            "--topology",
            str(TPR),
            "--trajectory",
            str(TRR),
        ],
    )
    mock_uvicorn_run = mocker.patch("uvicorn.run")
    start_server()
    assert main.mdadash.sm.universe_configs[0]["total_frames"] == 10
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
            "nojump": True,
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
    assert response[0]["content"] == "Invalid index 1 of 1 items\n1 47681\n47681\n"


async def test_kernel_execute_code_errors(_client):
    # check code errors in kernel code execution
    code = "x"
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert "name 'x' is not defined" in response[0]["content"]
    code = "print(\n"
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert "incomplete input" in response[0]["content"]
    # check stderr
    code = "import sys\nprint('x', file=sys.stderr)"
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response[0]["content"] == "x\n"


async def test_socketio_connect_disconnect(_client, imd_server):
    await connect_to_simulation(imd_server)
    # connect
    handler = sio.handlers["/"]["connect"]
    response = await run_task_until_done(handler("_sid", {}))
    assert response is None
    # init_data
    handler = sio.handlers["/"]["init_data"]
    response = await run_task_until_done(handler("_sid"))
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
    wm = WidgetManager(None)

    class TestWidget1:
        pass

    with pytest.raises(TypeError, match="is not a widget class"):
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
            run_every_frame = None  # not a callable

    # test correct registration - every-frame
    class _TestWidget4a(WidgetBase):
        name = "TestWidget4a"

        def run_every_frame(self):
            pass

    # test correct registration - batch
    class _TestWidget4b(WidgetBase):
        name = "TestWidget4b"

        def run_batch(self):
            pass

    # test duplicate widget name registraion exception
    with pytest.raises(ValueError, match="already registered"):

        class _TestWidget5(WidgetBase):
            name = "TestWidget4a"

            def run_every_frame(self):
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
    response = await run_task_until_done(main.mdadash.km.recreate_widget_instances())
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
    response = await run_task_until_done(main.mdadash.km.recreate_widget_instances())
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
    with pytest.raises(IndexError, match="deque index out of range"):
        _ = u.trajectory[10]
    with pytest.raises(IndexError, match="deque index out of range"):
        _ = u.trajectory[-10]
    assert "_buffer" not in dir(u.trajectory)


async def test_widget_input_changes(_client):
    uuid = await add_widget("Absolute Temperature")
    # test input changes
    inputs = [
        ("maxlen", -1),
        ("x_type", "step"),
        ("title", "Title"),
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


async def test_widget_run_energies_serial(_client, imd_server):
    uuid = await add_widget("Absolute Temperature")
    await connect_to_simulation(imd_server)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_energies_batch(_client, imd_server):
    uuid = await add_widget("Absolute Temperature")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_com_distance_serial_every_frame(_client, imd_server):
    await connect_to_simulation(imd_server)
    uuid = await add_widget("COMDistance")
    inputs = [
        ("selection1", "resid 1"),
        ("selection2", "resid 2"),
        ("maxlen", -1),
        ("x_type", "step"),
        ("updating", True),
        ("custom_title", "Title"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_com_distance_serial_batch(_client, imd_server):
    uuid = await add_widget("COMDistance")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_com_distance_parallel_every_frame(_client, imd_server):
    uuid = await add_widget("COMDistance")
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


async def test_widget_run_com_distance_parallel_batch(_client, imd_server):
    uuid = await add_widget("COMDistance")
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


async def test_widget_run_com_distance_alert_pause(_client, imd_server):
    uuid = await add_widget("COMDistance")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection1", "resid 1"),
        ("selection2", "resid 2"),
        ("max_distance", 0),
        ("max_distance_alert", True),
        ("max_distance_pause", True),
    ]
    await check_input_changes(uuid, inputs)
    # check there are no alerts
    assert len(main.mdadash.sm.alerts) == 0
    # resume simulation
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "runningState", n=3)
    assert main.mdadash.sm.running_state["running"] is False
    # check alert generation
    handler = sio.handlers["/"]["get_alerts"]
    alerts = await run_task_until_done(handler("_sid"))
    previous_alerts = alerts.copy()
    assert alerts[0]["id"] == 0
    # check alert deletion
    handler = sio.handlers["/"]["delete_alert"]
    await run_task_until_done(handler("_sid", 0))
    if len(main.mdadash.sm.alerts) > 0:
        assert alerts[0]["id"] != 0
    # check delete all alerts
    handler = sio.handlers["/"]["delete_all_alerts"]
    await run_task_until_done(handler("_sid"))
    handler = sio.handlers["/"]["get_alerts"]
    alerts = await run_task_until_done(handler("_sid"))
    assert alerts != previous_alerts
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_rog_serial_every_frame(_client, imd_server):
    await connect_to_simulation(imd_server)
    uuid = await add_widget("ROG")
    inputs = [
        ("selection", "protein"),
        ("maxlen", -1),
        ("x_type", "step"),
        ("updating", True),
        ("custom_title", "Title"),
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


async def test_widget_run_rog_parallel_every_frame(_client, imd_server):
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


async def test_widget_run_rmsd_serial_every_frame(_client, imd_server):
    uuid = await add_widget("RMSD")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection", "protein"),
        ("center", True),
        ("superposition", True),
        ("maxlen", -1),
        ("x_type", "step"),
        ("custom_title", "Title"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_rmsd_serial_batch(_client, imd_server):
    uuid = await add_widget("RMSD")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_rmsd_parallel_every_frame(_client, imd_server):
    uuid = await add_widget("RMSD")
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


async def test_widget_run_rmsd_parallel_batch(_client, imd_server):
    uuid = await add_widget("RMSD")
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


async def test_widget_run_native_contacts_serial_every_frame(_client, imd_server):
    uuid = await add_widget("Native Contacts")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection1", "protein and name CA"),
        ("selection2", "protein and name CA"),
        ("maxlen", -1),
        ("x_type", "step"),
        ("custom_title", "Title"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_native_contacts_serial_batch(_client, imd_server):
    uuid = await add_widget("Native Contacts")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_native_contacts_parallel_every_frame(_client, imd_server):
    uuid = await add_widget("Native Contacts")
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


async def test_widget_run_native_contacts_parallel_batch(_client, imd_server):
    uuid = await add_widget("Native Contacts")
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


async def test_widget_run_contacts_serial_every_frame(_client, imd_server):
    uuid = await add_widget("Contacts")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection1", "protein"),
        ("selection2", "resid 1:10"),
        ("maxlen", -1),
        ("x_type", "step"),
        ("custom_title", "Title"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_contacts_serial_batch(_client, imd_server):
    uuid = await add_widget("Contacts")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_contacts_parallel_every_frame(_client, imd_server):
    uuid = await add_widget("Contacts")
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


async def test_widget_run_contacts_parallel_batch(_client, imd_server):
    uuid = await add_widget("Contacts")
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


async def test_widget_run_hbonds_serial_every_frame(_client, imd_server):
    uuid = await add_widget("Hydrogen bonds")
    await connect_to_simulation(imd_server)
    inputs = [
        ("donors_sel", "name O* N*"),
        ("hydrogens_sel", "name H*"),
        ("acceptors_sel", "name O* N*"),
        ("maxlen", -1),
        ("x_type", "step"),
        ("custom_title", "Title"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_hbonds_serial_batch(_client, imd_server):
    uuid = await add_widget("Hydrogen bonds")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_hbonds_parallel_every_frame(_client, imd_server):
    uuid = await add_widget("Hydrogen bonds")
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


async def test_widget_run_hbonds_parallel_batch(_client, imd_server):
    uuid = await add_widget("Hydrogen bonds")
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


async def test_widget_run_helix_analysis_serial_every_frame(_client, imd_server):
    uuid = await add_widget("Helix Analysis")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection", "resid 1:10 and name CA"),
        ("property", "local_twists"),
        ("maxlen", -1),
        ("x_type", "step"),
        ("custom_title", "Title"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_helix_analysis_serial_batch(_client, imd_server):
    uuid = await add_widget("Helix Analysis")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_helix_analysis_parallel_every_frame(_client, imd_server):
    uuid = await add_widget("Helix Analysis")
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


async def test_widget_run_helix_analysis_parallel_batch(_client, imd_server):
    uuid = await add_widget("Helix Analysis")
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


async def test_widget_run_dssp_serial_every_frame(_client, imd_server):
    await connect_to_simulation(imd_server)
    uuid = await add_widget("DSSP Analysis")
    inputs = [
        ("maxlen", -1),
        ("custom_title", "Title"),
        ("x_type", "step"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_dssp_serial_batch(_client, imd_server):
    uuid = await add_widget("DSSP Analysis")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_dssp_parallel_every_frame(_client, imd_server):
    uuid = await add_widget("DSSP Analysis")
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


async def test_widget_run_dssp_parallel_batch(_client, imd_server):
    uuid = await add_widget("DSSP Analysis")
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


async def test_widget_run_ramachandran(_client, imd_server):
    uuid = await add_widget("Ramachandran Plot")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection", "protein"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_janin(_client, imd_server):
    uuid = await add_widget("Janin Plot")
    await connect_to_simulation(imd_server)
    inputs = [
        ("selection", "protein"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_msd_serial(_client, imd_server):
    uuid = await add_widget("MSD Analysis")
    await connect_to_simulation(imd_server, step=1, batch_size=2)
    inputs = [
        ("selection", "resid 1"),
        ("custom_title", ""),
        ("show_particle_msds", True),
        ("log_scale", False),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_msd_parallel(_client, imd_server):
    uuid = await add_widget("MSD Analysis")
    await connect_to_simulation(imd_server, step=1, batch_size=2)
    inputs = [
        ("selection", "resid 1"),
        ("show_particle_msds", True),
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_msd_diffusion_coefficient(_client, imd_server):
    uuid = await add_widget("MSD Analysis")
    await connect_to_simulation(imd_server, step=1, batch_size=2)
    inputs = [
        ("selection", "resid 1"),
        ("show_diffusion_coefficient", True),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_vacf_serial(_client, imd_server_trr):
    uuid = await add_widget("ACF")
    await connect_to_simulation(imd_server_trr, step=1, batch_size=3)
    inputs = [
        ("physical_property", "velocity"),
        ("selection", "resid 1"),
        ("custom_title", ""),
        ("show_particle_acfs", True),
        ("centered", True),
        ("normalized", True),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server_trr, n_frames=5)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_vacf_serial_batch(_client, imd_server_trr):
    uuid = await add_widget("ACF")
    await connect_to_simulation(imd_server_trr, step=1, batch_size=3)
    inputs = [
        ("physical_property", "velocity"),
        ("selection", "resid 1"),
        ("_run_frequency", "batch"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server_trr, n_frames=5)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_vacf_parallel(_client, imd_server_trr):
    uuid = await add_widget("ACF")
    await connect_to_simulation(imd_server_trr, step=1, batch_size=3)
    inputs = [
        ("physical_property", "velocity"),
        ("selection", "resid 1"),
        ("show_particle_acfs", True),
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server_trr, n_frames=5)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_vacf_parallel_batch(_client, imd_server_trr):
    uuid = await add_widget("ACF")
    await connect_to_simulation(imd_server_trr, step=1, batch_size=3)
    inputs = [
        ("physical_property", "velocity"),
        ("selection", "resid 1"),
        ("_run_frequency", "batch"),
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server_trr, n_frames=5)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_vacf_running_integral(_client, imd_server_trr):
    uuid = await add_widget("ACF")
    await connect_to_simulation(imd_server_trr, step=1, batch_size=2)
    inputs = [
        ("physical_property", "velocity"),
        ("selection", "resid 1"),
        ("show_running_integral", True),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server_trr, n_frames=5)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_notebook_cell(_client, imd_server):
    await connect_to_simulation(imd_server)
    sio.emit.reset_mock()
    # cell run
    handler = sio.handlers["/"]["cell_run"]
    response = await run_task_until_done(handler("_sid", '{"cell_id": 0, "code": "u"}'))
    assert "Universe with" in response[0]["content"]
    # code complete
    handler = sio.handlers["/"]["cell_code_complete"]
    response = await run_task_until_done(
        handler("_sid", {"code": "u", "cursor_pos": 1})
    )
    if response is not None:
        assert "u" in response["matches"]
    # code inspect
    handler = sio.handlers["/"]["cell_code_inspect"]
    response = await run_task_until_done(
        handler("_sid", {"code": "u", "cursor_pos": 1})
    )
    if response is not None:
        assert "Universe" in response["data"]["text/plain"]
    await disconnect_from_simulation()


async def test_widget_run_custom_code(_client, imd_server):
    uuid = await add_widget("Custom Code")
    await connect_to_simulation(imd_server)
    inputs = [
        ("setup_code", "u"),
        ("execute_code", "u.trajectory"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid)
    await disconnect_from_simulation()


async def test_widget_run_custom_code_batch(_client, imd_server):
    uuid = await add_widget("Custom Code")
    await connect_to_simulation(imd_server)
    inputs = [
        ("_run_frequency", "batch"),
        ("setup_code", "u"),
        ("execute_code", "u.trajectory"),
    ]
    await check_input_changes(uuid, inputs)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
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
    # test alerts related keys
    assert sm._alertID == 0
    assert len(sm.alerts) == 0


async def test_notebooks_add_del_dup(_client):
    sio.emit.reset_mock()
    # check add notebook 1
    handler = sio.handlers["/"]["notebooks:add_notebook"]
    uuid1 = await run_task_until_done(handler("_sid"))
    assert uuid1 is not None
    # check add notebook 2
    handler = sio.handlers["/"]["notebooks:add_notebook"]
    uuid2 = await run_task_until_done(handler("_sid"))
    assert uuid2 is not None
    # check get notebooks
    handler = sio.handlers["/"]["notebooks:get_notebooks"]
    response = await run_task_until_done(handler("_sid"))
    assert len(response) == 2
    # delete notebook 2
    handler = sio.handlers["/"]["notebooks:remove_notebook"]
    response = await run_task_until_done(handler("_sid", uuid2))
    # check get notebooks
    handler = sio.handlers["/"]["notebooks:get_notebooks"]
    response = await run_task_until_done(handler("_sid"))
    assert len(response) == 1
    # duplicate notebook 1
    handler = sio.handlers["/"]["notebooks:duplicate_notebook"]
    response = await run_task_until_done(handler("_sid", uuid1))
    # check get notebooks
    handler = sio.handlers["/"]["notebooks:get_notebooks"]
    response = await run_task_until_done(handler("_sid"))
    assert len(response) == 2


async def test_notebook_updates(_client):
    sio.emit.reset_mock()
    # check add notebook 1
    handler = sio.handlers["/"]["notebooks:add_notebook"]
    uuid1 = await run_task_until_done(handler("_sid"))
    assert uuid1 is not None
    # check get notebook 1
    handler = sio.handlers["/"]["notebooks:get_notebook"]
    notebook = await run_task_until_done(handler("_sid", uuid1))
    assert notebook["uuid"] == uuid1
    assert len(notebook["cells"]) == 1
    cell0_id = notebook["cells"][0]["id"]
    # update run on launch
    handler = sio.handlers["/"]["notebook:run_on_launch"]
    await run_task_until_done(handler("_sid", uuid1, True))
    # update name and desc
    handler = sio.handlers["/"]["notebook:name_desc_change"]
    await run_task_until_done(handler("_sid", uuid1, "name1", "description1"))
    # update cell 0
    handler = sio.handlers["/"]["notebook:cell_change"]
    await run_task_until_done(handler("_sid", uuid1, cell0_id, "u"))
    # check get notebook 1
    handler = sio.handlers["/"]["notebooks:get_notebook"]
    notebook = await run_task_until_done(handler("_sid", uuid1))
    assert notebook["run_on_launch"]
    assert notebook["name"] == "name1"
    assert notebook["description"] == "description1"
    assert notebook["cells"][0]["code"] == "u"
    # update cells
    handler = sio.handlers["/"]["notebook:update_cells"]
    cells = [
        {"id": "id1", "code": "code1"},
        {"id": "id2", "code": "code2"},
    ]
    await run_task_until_done(handler("_sid", uuid1, cells))
    # check get notebook 1
    handler = sio.handlers["/"]["notebooks:get_notebook"]
    notebook = await run_task_until_done(handler("_sid", uuid1))
    assert len(notebook["cells"]) == 2


async def test_notebooks_run_on_launch(_client):
    main.mdadash.sm.notebooks.update(
        {
            "uuid1": {
                "uuid": "uuid1",
                "run_on_launch": True,
                "cells": [
                    {
                        "id": "id1",
                        "code": "x1 = 5",
                    },
                ],
            },
            "uuid2": {
                "uuid": "uuid2",
                "run_on_launch": False,
                "cells": [
                    {
                        "id": "id1",
                        "code": "x2 = 5",
                    },
                ],
            },
        },
    )
    response = await run_task_until_done(main.mdadash.km.run_notebooks())
    assert response["status"] == "ok"
    code = "print(x1)\nprint(x2)"
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == [
        {"type": "error", "content": "name 'x2' is not defined"},
        {"type": "text", "content": "5\n"},
    ]


async def test_custom_widget(_client, imd_server):
    code = """
    from mdadash.backend.widgets.base import WidgetBase
    class _CustomWidget1(WidgetBase):
        name = "Custom Widget"

        _inputs = [
            {
                "attribute": "input1",
                "name": "Input 1",
                "type": "bool",
            },
        ]

        def __init__(self):
            super().__init__()
            self.input1 = False

        def run_every_frame(self):
            pass
    """
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == []
    uuid1 = await add_widget("Custom Widget")
    uuid2 = await add_widget("Absolute Temperature")
    await connect_to_simulation(imd_server)
    code = """
    from mdadash.backend.widgets.base import WidgetBase
    class _CustomWidget1(WidgetBase):
        name = "Custom Widget"
        _override_name = True

        def run_every_frame(self):
            print(self.u)
    """
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == []
    await remove_widget(uuid2)
    await resume_simulation(imd_server)
    assert await sio_event_emitted(sio, "widgets:output", n=1)
    await remove_widget(uuid1)
    await disconnect_from_simulation()


async def test_notebooks_clone_widget(_client):
    sio.emit.reset_mock()
    # check get clonable widgets
    handler = sio.handlers["/"]["notebooks:get_clonable_widgets"]
    widgets = await run_task_until_done(handler("_sid"))
    assert widgets
    # add notebook with cloned widget code
    widget = widgets[0]
    handler = sio.handlers["/"]["notebooks:clone_widget"]
    uuid = await run_task_until_done(
        handler("_sid", widget["name"], widget["description"], widget["class_name"])
    )
    assert uuid is not None


async def test_utils_alert_pause(_client, imd_server):
    await connect_to_simulation(imd_server)
    # delete all alerts
    handler = sio.handlers["/"]["delete_all_alerts"]
    await run_task_until_done(handler("_sid"))
    # check there are no alerts
    assert len(main.mdadash.sm.alerts) == 0
    # generate alert from custom code
    code = "utils.alert('test alert')"
    await run_task_until_done(main.mdadash.km.execute_code(code))
    # check alert generation
    handler = sio.handlers["/"]["get_alerts"]
    alerts = await run_task_until_done(handler("_sid"))
    assert alerts[0]["message"] == "test alert"
    # pause from custom code
    code = "utils.pause_simulation('test pause')"
    await run_task_until_done(main.mdadash.km.execute_code(code))
    # cleanup - delete all alerts
    handler = sio.handlers["/"]["delete_all_alerts"]
    await run_task_until_done(handler("_sid"))
    await disconnect_from_simulation()


async def test_3dview(_client, imd_server):
    # test defaults
    handler = sio.handlers["/"]["load_3dview"]
    response = await run_task_until_done(handler("_sid"))
    assert response is not None
    assert response["inputs"]["selection"] == ""
    assert response["topology"] is None
    # update selection - valid
    handler = sio.handlers["/"]["update_3dview_selection"]
    await run_task_until_done(handler("_sid", "resid 1"))
    # connect
    await connect_to_simulation(imd_server)
    # verify selection and topology
    handler = sio.handlers["/"]["load_3dview"]
    response = await run_task_until_done(handler("_sid"))
    assert response is not None
    assert response["inputs"]["selection"] == "resid 1"
    assert response["topology"] is not None
    # update selection - empty
    handler = sio.handlers["/"]["update_3dview_selection"]
    await run_task_until_done(handler("_sid", ""))
    handler = sio.handlers["/"]["load_3dview"]
    response = await run_task_until_done(handler("_sid"))
    assert response["inputs"]["selection"] == ""
    # update selection - invalid
    handler = sio.handlers["/"]["update_3dview_selection"]
    await run_task_until_done(handler("_sid", "invalid"))
    handler = sio.handlers["/"]["load_3dview"]
    response = await run_task_until_done(handler("_sid"))
    assert response["inputs"]["selection"] == "invalid"
    assert response["inputs"]["selection_error"] == "Unknown selection token: 'invalid'"
    assert response["topology"] is None
    await disconnect_from_simulation()
