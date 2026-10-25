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


async def test_widget_run_msd_serial(_client):
    uuid = await add_widget("MSD Analysis")
    async with file_simulation(XTC, step=1, batch_size=2):
        inputs = [
            ("selection", "resid 1"),
            ("custom_title", ""),
            ("show_particle_msds", True),
            ("log_scale", False),
            ("plot_refresh_frequency", 1),
            ("reset_on_connect", False),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_msd_parallel(_client):
    uuid = await add_widget("MSD Analysis")
    async with file_simulation(XTC, step=1, batch_size=2):
        inputs = [
            ("selection", "resid 1"),
            ("show_particle_msds", True),
            ("_run_mode", "parallel"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_msd_diffusion_coefficient(_client):
    uuid = await add_widget("MSD Analysis")
    async with file_simulation(XTC, step=1, batch_size=2):
        inputs = [
            ("selection", "resid 1"),
            ("show_diffusion_coefficient", True),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)
