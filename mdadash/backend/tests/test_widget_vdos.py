import sys

from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import TRR, XTC

from .utils import (
    add_widget,
    check_input_changes,
    file_simulation,
    remove_widget,
    resume_file_simulation,
    sio_event_emitted,
)


async def test_widget_run_vdos_serial(_client):
    uuid = await add_widget("VDoS")
    async with file_simulation(TRR, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
            ("custom_title", ""),
            ("plot_refresh_frequency", 1),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_vdos_serial_batch(_client):
    uuid = await add_widget("VDoS")
    async with file_simulation(TRR, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
            ("_run_frequency", "batch"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_vdos_parallel(_client):
    uuid = await add_widget("VDoS")
    async with file_simulation(TRR, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
            ("_run_mode", "parallel"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_vdos_parallel_batch(_client):
    uuid = await add_widget("VDoS")
    async with file_simulation(TRR, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
            ("_run_frequency", "batch"),
            ("_run_mode", "parallel"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_vdos_serial_no_velocities(_client):
    uuid = await add_widget("VDoS")
    async with file_simulation(TRR, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
            ("custom_title", ""),
            ("plot_refresh_frequency", 1),
        ]
        await check_input_changes(uuid, inputs)
    async with file_simulation(XTC, step=1, batch_size=3):
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_vdos_serial_batch_no_velocities(_client):
    uuid = await add_widget("VDoS")
    async with file_simulation(TRR, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
            ("_run_frequency", "batch"),
        ]
        await check_input_changes(uuid, inputs)
    async with file_simulation(XTC, step=1, batch_size=3):
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)
