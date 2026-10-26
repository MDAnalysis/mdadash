import sys

from mdadash.backend import main
from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import XTC

from .utils import (
    add_widget,
    check_input_changes,
    file_simulation,
    remove_widget,
    resume_file_simulation,
    run_task_until_done,
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


async def test_widget_run_acf_weights_masses(_client):
    uuid = await add_widget("ACF")
    async with file_simulation(XTC, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
            ("weights", "masses"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_acf_weights_custom_function(_client):
    code = """
    custom_weights_function_not_callable = None

    def custom_weights_function_improper():
        pass

    def custom_weights_function_wrong_1D(ag):
        return [1]

    def custom_weights_function_valid(ag):
        return ag.masses
    """
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == []
    uuid = await add_widget("ACF")
    async with file_simulation(XTC, step=1, batch_size=3):
        inputs = [
            ("selection", "resid 1"),
        ]
        await check_input_changes(uuid, inputs)
        inputs = [
            ("weights", "Custom function"),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        inputs = [
            ("weights_function", "custom_weights_function_undefined"),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        inputs = [
            ("weights_function", "custom_weights_function_not_callable"),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        inputs = [
            ("weights_function", "custom_weights_function_improper"),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        inputs = [
            ("weights_function", "custom_weights_function_wrong_1D"),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        inputs = [
            ("weights_function", "custom_weights_function_valid"),
            ("weights", "Custom function"),
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
