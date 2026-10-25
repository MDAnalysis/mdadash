import asyncio
import importlib
import json
import sys
from unittest.mock import ANY

import pytest

from mdadash.backend import main
from mdadash.backend.main import sio
from mdadash.backend.state.manager import StateManager
from mdadash.backend.tests.data.files import TPR, XTC
from mdadash.backend.widgets.base import WidgetBase, WidgetManager

from .utils import (
    add_widget,
    connect_to_file_simulation,
    disconnect_from_simulation,
    file_simulation,
    pause_simulation,
    remove_widget,
    resume_file_simulation,
    resume_imd_simulation,
    run_task_until_done,
)


def test_start_server_imd_trajectory(mocker, monkeypatch):
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
    monkeypatch.delitem(sys.modules, "mdadash.backend.main")
    sandboxed_main = importlib.import_module("mdadash.backend.main")
    # uvicorn.run is a blocking call, so we need to
    # mock it so as to not block the tests. An alternative is
    # to run the real server in a separate thread
    mock_uvicorn_run = mocker.patch("uvicorn.run")
    sandboxed_main.start_server()
    mock_uvicorn_run.assert_called_once_with(
        "mdadash.backend.main:app",
        host="127.0.0.1",
        port=8000,
    )


def test_start_server_file_trajectory(mocker, monkeypatch):
    # mock the command line params
    mocker.patch.object(
        sys,
        "argv",
        [
            "main.py",
            "--topology",
            str(TPR),
            "--trajectory",
            str(XTC),
        ],
    )
    monkeypatch.delitem(sys.modules, "mdadash.backend.main")
    sandboxed_main = importlib.import_module("mdadash.backend.main")
    mock_uvicorn_run = mocker.patch("uvicorn.run")
    sandboxed_main.start_server()
    assert sandboxed_main.mdadash.sm.universe_configs[0]["total_frames"] == 10
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
    main.mdadash.sm.universe_configs[0].update(
        {
            "topology": "",
            "trajectory": "",
        }
    )
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
    # test connect failure when connected
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "error"
    assert "Already connected" in response["message"]
    # test resume
    await resume_imd_simulation(imd_server)
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


async def test_kernel_universe_access(_client):
    async with file_simulation(XTC):
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


async def test_socketio_connect_disconnect(_client):
    async with file_simulation(XTC):
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
        await resume_file_simulation()
    # test dashboard activated response
    sio.emit.reset_mock()
    handler = sio.handlers["/"]["dashboard:activated"]
    await run_task_until_done(handler("_sid"))
    sio.emit.assert_awaited_with("widgets:layout", ANY, to="_sid")


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
    state = {
        "app": "mdadash",
        "settings": {
            "dashboard_config": {},
            "universe_configs": [],
        },
    }
    temp_file = tmp_path / "mdadash3.state.json"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f)
    sm = StateManager(temp_file)
    assert sm.state is not None
    # test alerts related keys
    assert sm._alertID == 0
    assert len(sm.alerts) == 0


async def test_running_state(_client):
    await connect_to_file_simulation(XTC)
    # can't pause when not running
    handler = sio.handlers["/"]["pause_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "error"
    assert "Not running" in response["message"]
    await resume_file_simulation()
    # can't resume when not paused
    handler = sio.handlers["/"]["resume_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "error"
    assert "Not paused" in response["message"]
    await disconnect_from_simulation()
    # can't disconnect when not connected
    handler = sio.handlers["/"]["disconnect_from_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "error"
    assert "Already disconnected" in response["message"]


async def test_utils_alert_pause(_client):
    async with file_simulation(XTC):
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


async def test_long_parallel_job(_client):
    code = """
    import time
    from joblib import delayed
    from mdadash.backend.widgets.base import WidgetBase

    class LongParallel(WidgetBase):
        name = "Long Parallel"

        def __init__(self):
            super().__init__()
            self._run_mode = "parallel"

        def run_every_frame(self):
            if self.u.trajectory.frame == 1:
                time.sleep(2)

        def get_parallel_job(self):
            return delayed(self.run_every_frame)()

        def apply_parallel_results(self, values):
            pass
    """
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == []
    uuid = await add_widget("Long Parallel")
    async with file_simulation(XTC, disconnect_wait=False):
        await resume_file_simulation()
        await asyncio.sleep(0.25)
    # check connect while previous parallel jobs are still running
    handler = sio.handlers["/"]["connect_to_simulations"]
    response = await run_task_until_done(handler("_sid"))
    # ensure error with message
    assert response["status"] == "error"
    assert "Previous jobs are still in progress" in response["message"]
    await remove_widget(uuid)
    # ensure we can connect again in later tests
    await asyncio.sleep(5)
