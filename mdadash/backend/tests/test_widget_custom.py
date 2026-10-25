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


async def test_custom_widget(_client):
    code = """
    from mdadash.backend.widgets.base import WidgetBase
    class _CustomWidget1(WidgetBase):
        name = "Custom Widget"

        _inputs = [
            {
                "attribute": "input1",
                "name": "Input 1",
                "type": "bool",
            },
        ]

        def __init__(self):
            super().__init__()
            self.input1 = False

        def run_every_frame(self):
            pass
    """
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == []
    uuid1 = await add_widget("Custom Widget")
    uuid2 = await add_widget("Absolute Temperature")
    async with file_simulation(XTC):
        code = """
        from mdadash.backend.widgets.base import WidgetBase
        class _CustomWidget1(WidgetBase):
            name = "Custom Widget"
            _override_name = True

            def run_every_frame(self):
                print(self.u)
        """
        response = await run_task_until_done(main.mdadash.km.execute_code(code))
        assert response == []
        await remove_widget(uuid2)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid1)


async def test_custom_widget_parallel_job(_client):
    code = """
    from joblib import delayed
    from mdadash.backend.widgets.base import WidgetBase

    class CustomWidget2(WidgetBase):
        name = "Custom Widget 2"

        def __init__(self):
            super().__init__()
            self._run_mode = "parallel"

        def run_every_frame(self):
            return u.trajectory.frame

        def get_parallel_job(self):
            return delayed(self.run_every_frame)()

        def apply_parallel_results(self, values):
            print(values)
            
    """
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == []
    uuid = await add_widget("Custom Widget 2")
    async with file_simulation(XTC):
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_custom_code(_client):
    uuid = await add_widget("Custom Code")
    async with file_simulation(XTC):
        inputs = [
            ("setup_code", "u"),
            ("execute_code", "u.trajectory"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)


async def test_widget_run_custom_code_batch(_client):
    uuid = await add_widget("Custom Code")
    async with file_simulation(XTC):
        inputs = [
            ("_run_frequency", "batch"),
            ("setup_code", "u"),
            ("execute_code", "u.trajectory"),
        ]
        await check_input_changes(uuid, inputs)
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid)
