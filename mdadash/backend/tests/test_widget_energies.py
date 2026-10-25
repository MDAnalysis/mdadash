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
    sio_event_emitted,
)


async def test_widget_run_energies_serial(_client, imd_server):
    async with imd_simulation(imd_server):
        uuid = await add_widget("Absolute Temperature")
        inputs = [
            ("plot_refresh_frequency", 1),
            ("reset_on_connect", False),
        ]
        await check_input_changes(uuid, inputs)
        await resume_imd_simulation(imd_server)
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_energies_batch(_client):
    uuid = await add_widget("Absolute Temperature")
    async with file_simulation(XTC):
        inputs = [
            ("_run_frequency", "batch"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)
