from mdadash.backend import main
from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import XTC

from .utils import (
    file_simulation,
    run_task_until_done,
)


async def test_notebook_cell(_client):
    async with file_simulation(XTC):
        sio.emit.reset_mock()
        # cell run
        handler = sio.handlers["/"]["cell_run"]
        response = await run_task_until_done(
            handler("_sid", '{"cell_id": 0, "code": "u"}')
        )
        assert "Universe with" in response[0]["content"]
        # code complete
        handler = sio.handlers["/"]["cell_code_complete"]
        response = await run_task_until_done(
            handler("_sid", {"code": "u", "cursor_pos": 1})
        )
        if response is not None:
            assert "u" in response["matches"]
        # code inspect
        handler = sio.handlers["/"]["cell_code_inspect"]
        response = await run_task_until_done(
            handler("_sid", {"code": "u", "cursor_pos": 1})
        )
        if response is not None:
            assert "Universe" in response["data"]["text/plain"]


async def test_notebooks_add_del_dup(_client):
    sio.emit.reset_mock()
    # check add notebook 1
    handler = sio.handlers["/"]["notebooks:add_notebook"]
    uuid1 = await run_task_until_done(handler("_sid"))
    assert uuid1 is not None
    # check add notebook 2
    handler = sio.handlers["/"]["notebooks:add_notebook"]
    uuid2 = await run_task_until_done(handler("_sid"))
    assert uuid2 is not None
    # check get notebooks
    handler = sio.handlers["/"]["notebooks:get_notebooks"]
    response = await run_task_until_done(handler("_sid"))
    assert len(response) == 2
    # delete notebook 2
    handler = sio.handlers["/"]["notebooks:remove_notebook"]
    response = await run_task_until_done(handler("_sid", uuid2))
    # check get notebooks
    handler = sio.handlers["/"]["notebooks:get_notebooks"]
    response = await run_task_until_done(handler("_sid"))
    assert len(response) == 1
    # duplicate notebook 1
    handler = sio.handlers["/"]["notebooks:duplicate_notebook"]
    response = await run_task_until_done(handler("_sid", uuid1))
    # check get notebooks
    handler = sio.handlers["/"]["notebooks:get_notebooks"]
    response = await run_task_until_done(handler("_sid"))
    assert len(response) == 2


async def test_notebook_updates(_client):
    sio.emit.reset_mock()
    # check add notebook 1
    handler = sio.handlers["/"]["notebooks:add_notebook"]
    uuid1 = await run_task_until_done(handler("_sid"))
    assert uuid1 is not None
    # check get notebook 1
    handler = sio.handlers["/"]["notebooks:get_notebook"]
    notebook = await run_task_until_done(handler("_sid", uuid1))
    assert notebook["uuid"] == uuid1
    assert len(notebook["cells"]) == 1
    cell0_id = notebook["cells"][0]["id"]
    # update run on launch
    handler = sio.handlers["/"]["notebook:run_on_launch"]
    await run_task_until_done(handler("_sid", uuid1, True))
    # update name and desc
    handler = sio.handlers["/"]["notebook:name_desc_change"]
    await run_task_until_done(handler("_sid", uuid1, "name1", "description1"))
    # update cell 0
    handler = sio.handlers["/"]["notebook:cell_change"]
    await run_task_until_done(handler("_sid", uuid1, cell0_id, "u"))
    # check get notebook 1
    handler = sio.handlers["/"]["notebooks:get_notebook"]
    notebook = await run_task_until_done(handler("_sid", uuid1))
    assert notebook["run_on_launch"]
    assert notebook["name"] == "name1"
    assert notebook["description"] == "description1"
    assert notebook["cells"][0]["code"] == "u"
    # update cells
    handler = sio.handlers["/"]["notebook:update_cells"]
    cells = [
        {"id": "id1", "code": "code1"},
        {"id": "id2", "code": "code2"},
    ]
    await run_task_until_done(handler("_sid", uuid1, cells))
    # check get notebook 1
    handler = sio.handlers["/"]["notebooks:get_notebook"]
    notebook = await run_task_until_done(handler("_sid", uuid1))
    assert len(notebook["cells"]) == 2


async def test_notebooks_run_on_launch(_client):
    main.mdadash.sm.notebooks.update(
        {
            "uuid1": {
                "uuid": "uuid1",
                "run_on_launch": True,
                "cells": [
                    {
                        "id": "id1",
                        "code": "x1 = 5",
                    },
                ],
            },
            "uuid2": {
                "uuid": "uuid2",
                "run_on_launch": False,
                "cells": [
                    {
                        "id": "id1",
                        "code": "x2 = 5",
                    },
                ],
            },
        },
    )
    response = await run_task_until_done(main.mdadash.km.run_notebooks())
    assert response["status"] == "ok"
    code = "print(x1)\nprint(x2)"
    response = await run_task_until_done(main.mdadash.km.execute_code(code))
    assert response == [
        {"type": "error", "content": "name 'x2' is not defined"},
        {"type": "text", "content": "5\n"},
    ]


async def test_notebooks_clone_widget(_client):
    sio.emit.reset_mock()
    # check get clonable widgets
    handler = sio.handlers["/"]["notebooks:get_clonable_widgets"]
    widgets = await run_task_until_done(handler("_sid"))
    assert widgets
    # add notebook with cloned widget code
    widget = widgets[0]
    handler = sio.handlers["/"]["notebooks:clone_widget"]
    uuid = await run_task_until_done(
        handler("_sid", widget["name"], widget["description"], widget["class_name"])
    )
    assert uuid is not None
