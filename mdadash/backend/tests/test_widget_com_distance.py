import sys

from mdadash.backend import main
from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import XTC

from .utils import (
    add_widget,
    check_input_changes,
    file_simulation,
    imd_simulation,
    remove_widget,
    resume_file_simulation,
    resume_imd_simulation,
    run_task_until_done,
    sio_event_emitted,
)


async def test_widget_run_com_distance_serial_every_frame(_client):
    async with file_simulation(XTC):
        uuid = await add_widget("COMDistance")
        inputs = [
            ("selection1", "resid 1"),
            ("selection2", "resid 2"),
            ("maxlen", -1),
            ("x_type", "step"),
            ("updating", True),
            ("custom_title", "Title"),
            ("plot_refresh_frequency", 1),
            ("reset_on_connect", False),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_com_distance_serial_batch(_client):
    uuid = await add_widget("COMDistance")
    async with file_simulation(XTC):
        inputs = [
            ("_run_frequency", "batch"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_com_distance_serial_batch_vectorized(_client):
    uuid = await add_widget("COMDistance")
    async with file_simulation(XTC):
        inputs = [
            ("_run_frequency", "batch"),
            ("batch_vectorization", True),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_com_distance_parallel_every_frame(_client):
    uuid = await add_widget("COMDistance")
    inputs = [
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    async with file_simulation(XTC, use_shm=False):
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_com_distance_parallel_batch(_client, imd_server):
    async with imd_simulation(imd_server):
        uuid = await add_widget("COMDistance")
        inputs = [
            ("_run_frequency", "batch"),
            ("_run_mode", "parallel"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_imd_simulation(imd_server)
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_com_distance_alert_pause(_client):
    uuid = await add_widget("COMDistance")
    async with file_simulation(XTC):
        inputs = [
            ("selection1", "resid 1"),
            ("selection2", "resid 2"),
            ("max_distance", 0),
            ("max_distance_alert", True),
            ("max_distance_pause", True),
        ]
        await check_input_changes(uuid, inputs)
        # delete all alerts
        handler = sio.handlers["/"]["delete_all_alerts"]
        await run_task_until_done(handler("_sid"))
        # check there are no alerts
        assert len(main.mdadash.sm.alerts) == 0
        # resume simulation
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "runningState", n=3)
        assert main.mdadash.sm.running_state["running"] is False
        # check alert generation
        handler = sio.handlers["/"]["get_alerts"]
        alerts = await run_task_until_done(handler("_sid"))
        previous_alerts = alerts.copy()
        assert len(alerts)
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
