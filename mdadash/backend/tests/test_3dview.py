from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import XTC

from .utils import (
    file_simulation,
    resume_file_simulation,
    run_task_until_done,
)


async def test_3dview(_client):
    # test defaults
    handler = sio.handlers["/"]["load_3dview"]
    response = await run_task_until_done(handler("_sid"))
    assert response is not None
    assert response["inputs"]["selection"] == ""
    assert response["topology"] is None
    async with file_simulation(XTC):
        # update selection - valid
        handler = sio.handlers["/"]["update_3dview_selection"]
        await run_task_until_done(handler("_sid", "resid 1"))
        # verify selection and topology
        handler = sio.handlers["/"]["load_3dview"]
        response = await run_task_until_done(handler("_sid"))
        assert response is not None
        assert response["inputs"]["selection"] == "resid 1"
        assert response["topology"] is not None
        # update selection - empty
        handler = sio.handlers["/"]["update_3dview_selection"]
        await run_task_until_done(handler("_sid", ""))
        handler = sio.handlers["/"]["load_3dview"]
        response = await run_task_until_done(handler("_sid"))
        assert response["inputs"]["selection"] == ""
        # update selection - invalid
        handler = sio.handlers["/"]["update_3dview_selection"]
        await run_task_until_done(handler("_sid", "invalid"))
        handler = sio.handlers["/"]["load_3dview"]
        response = await run_task_until_done(handler("_sid"))
        assert response["inputs"]["selection"] == "invalid"
        assert (
            response["inputs"]["selection_error"]
            == "Unknown selection token: 'invalid'"
        )
        assert response["topology"] is None
        # update selection back to run simulation
        handler = sio.handlers["/"]["update_3dview_selection"]
        await run_task_until_done(handler("_sid", "resid 1"))
        await resume_file_simulation()
