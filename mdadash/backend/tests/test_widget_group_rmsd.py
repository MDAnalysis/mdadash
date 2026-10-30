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


async def test_widget_run_group_rmsd_serial_every_frame(_client):
    uuid = await add_widget("Group RMSD")
    async with file_simulation(XTC):
        inputs = [
            ("selection", "protein"),
            ("maxlen", -1),
            ("x_type", "step"),
            ("custom_title", "Title"),
            ("labels", "backbone"),
            ("plot_refresh_frequency", 1),
            ("reset_on_connect", False),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_group_rmsd_weights_masses(_client):
    uuid = await add_widget("Group RMSD")
    async with file_simulation(XTC):
        inputs = [
            ("weights", "masses"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_group_rmsd_weights_custom_function(_client):
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
    uuid = await add_widget("Group RMSD")
    async with file_simulation(XTC):
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


async def test_widget_run_group_rmsd_serial_batch(_client):
    uuid = await add_widget("Group RMSD")
    async with file_simulation(XTC):
        inputs = [
            ("_run_frequency", "batch"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_group_rmsd_parallel_every_frame(_client):
    uuid = await add_widget("Group RMSD")
    inputs = [
        ("_run_mode", "parallel"),
    ]
    await check_input_changes(uuid, inputs)
    async with file_simulation(XTC):
        await resume_file_simulation()
        timeout = 30 if sys.platform == "win32" else 20
        assert await sio_event_emitted(sio, "widgets:output", n=1, timeout=timeout)
        await remove_widget(uuid)


async def test_widget_run_group_rmsd_parallel_batch(_client):
    uuid = await add_widget("Group RMSD")
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
