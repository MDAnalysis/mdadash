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


async def test_widget_run_ramachandran(_client):
    uuid = await add_widget("Ramachandran Plot")
    async with file_simulation(XTC):
        inputs = [
            ("selection", "protein"),
            ("plot_refresh_frequency", 1),
            ("reset_on_connect", False),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_janin(_client):
    uuid = await add_widget("Janin Plot")
    async with file_simulation(XTC):
        inputs = [
            ("selection", "protein"),
            ("plot_refresh_frequency", 1),
            ("reset_on_connect", False),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)
