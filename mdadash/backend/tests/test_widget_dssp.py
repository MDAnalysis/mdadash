import sys

from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import XTC

from .utils import (
    add_widget,
    check_input_changes,
    file_simulation,
    remove_widget,
    resume_file_simulation,
    sio_event_emitted,
)


async def test_widget_run_dssp_serial_every_frame(_client):
    async with file_simulation(XTC):
        uuid = await add_widget("DSSP Analysis")
        inputs = [
            ("maxlen", -1),
            ("custom_title", "Title"),
            ("x_type", "step"),
            ("plot_refresh_frequency", 1),
            ("reset_on_connect", False),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_dssp_serial_batch(_client):
    uuid = await add_widget("DSSP Analysis")
    async with file_simulation(XTC):
        inputs = [
            ("_run_frequency", "batch"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_dssp_parallel_every_frame(_client):
    uuid = await add_widget("DSSP Analysis")
    inputs = [
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    async with file_simulation(XTC):
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_dssp_parallel_batch(_client):
    uuid = await add_widget("DSSP Analysis")
    inputs = [
        ("_run_frequency", "batch"),
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    async with file_simulation(XTC):
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)
