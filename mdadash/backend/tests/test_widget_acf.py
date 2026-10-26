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


async def test_widget_run_acf_serial(_client):
    uuid = await add_widget("ACF")
    async with file_simulation(XTC, step=1, batch_size=3):
        inputs = [
            ("physical_property", "position"),
            ("selection", "resid 1"),
            ("custom_title", ""),
            ("show_particle_acfs", True),
            ("centered", True),
            ("normalized", True),
            ("plot_refresh_frequency", 1),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_acf_serial_batch(_client):
    uuid = await add_widget("ACF")
    async with file_simulation(XTC, step=1, batch_size=3):
        inputs = [
            ("physical_property", "position"),
            ("selection", "resid 1"),
            ("show_particle_acfs", True),
            ("centered", True),
            ("_run_frequency", "batch"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_acf_parallel(_client):
    uuid = await add_widget("ACF")
    async with file_simulation(XTC, step=1, batch_size=3):
        inputs = [
            ("physical_property", "position"),
            ("selection", "resid 1"),
            ("show_particle_acfs", True),
            ("_run_mode", "parallel"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_acf_parallel_batch(_client):
    uuid = await add_widget("ACF")
    async with file_simulation(XTC, step=1, batch_size=3):
        inputs = [
            ("physical_property", "position"),
            ("selection", "resid 1"),
            ("_run_frequency", "batch"),
            ("_run_mode", "parallel"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_acf_running_integral(_client):
    uuid = await add_widget("ACF")
    async with file_simulation(XTC, step=1, batch_size=3):
        inputs = [
            ("physical_property", "position"),
            ("selection", "resid 1"),
            ("show_running_integral", True),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)
