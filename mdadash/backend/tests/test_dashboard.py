from unittest.mock import ANY

from mdadash.backend import main
from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import XTC

from .utils import (
    add_widget,
    check_input_changes,
    duplicate_widget,
    file_simulation,
    remove_widget,
    resume_file_simulation,
    run_task_until_done,
    sio_event_emitted,
)


async def test_update_settings(_client):
    # update settings
    handler = sio.handlers["/"]["update:settings"]
    settings = main.mdadash.sm.settings.copy()
    await run_task_until_done(handler("_sid", settings))
    # assert the updated value is not a reference
    assert settings is not main.mdadash.sm.settings
    assert settings is not main.mdadash.sm.state["settings"]
    # assert values are same
    assert settings == main.mdadash.sm.settings
    # update n_jobs
    settings["dashboard_config"]["n_jobs"] = 3
    handler = sio.handlers["/"]["update:settings"]
    await run_task_until_done(handler("_sid", settings))
    # update view3d_frequency
    settings["dashboard_config"]["view3d_frequency"] = 2
    handler = sio.handlers["/"]["update:settings"]
    await run_task_until_done(handler("_sid", settings))
    # assert values are updated
    assert settings == main.mdadash.sm.settings


async def test_get_available_widgets(_client):
    # get available widgets
    handler = sio.handlers["/"]["widgets:get_available_widgets"]
    response = await run_task_until_done(handler("_sid"))
    assert response["widgets"]


async def test_recreate_widget_instances(_client):
    # test valid state
    main.mdadash.sm.widgets.update(
        {
            "uuid": {
                "uid": 0,
                "class_name": "COMDistance",
                "inputs": [
                    {"attribute": "selection1", "value": "protein", "error": ""},
                ],
            },
        },
    )
    response = await run_task_until_done(main.mdadash.km.recreate_widget_instances())
    assert response["status"] == "ok"
    await remove_widget("uuid")
    # test invalid state
    main.mdadash.sm.widgets.update(
        {
            "uuid": {
                "class_name": "InvalidClassName",
            },
        },
    )
    response = await run_task_until_done(main.mdadash.km.recreate_widget_instances())
    assert response["status"] == "error"


async def test_add_remove_widgets(_client):
    # test add unknown widget
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, "Invalid Widget", ""))
    uuid = response.get("uuid", None)
    assert uuid is None
    # test remove invalid widget
    handler = sio.handlers["/"]["widgets:remove_widget"]
    response = await run_task_until_done(handler("_sid", "invalid_uuid"))
    assert response["status"] == "error"
    # add widget 1
    uuid1 = await add_widget("Absolute Temperature")
    # add widget 2
    uuid2 = await add_widget("Total Energy")
    # remove widget 1
    await remove_widget(uuid1)
    # remove widget 2
    await remove_widget(uuid2)


async def test_duplicate_widgets(_client):
    async with file_simulation(XTC):
        # add a widget
        uuid1 = await add_widget("Absolute Temperature")
        # duplicate the widget
        uuid2 = await duplicate_widget(uuid1)
        await remove_widget(uuid1)
        await remove_widget(uuid2)
        # add widget and set wrong inputs
        uuid1 = await add_widget("ROG")
        inputs = [
            ("selection", "invalid"),
        ]
        await check_input_changes(uuid1, inputs, ["error"])
        # duplicate the widget
        uuid2 = await duplicate_widget(uuid1)
        await remove_widget(uuid1)
        await remove_widget(uuid2)
        await resume_file_simulation()


async def test_update_layout(_client):
    handler = sio.handlers["/"]["widgets:update_layout"]
    response = await run_task_until_done(handler("_sid", []))
    assert response == []


async def test_widget_input_changes(_client):
    uuid = await add_widget("Absolute Temperature")
    # test input changes
    inputs = [
        ("maxlen", -1),
        ("x_type", "step"),
        ("title", "Title"),
    ]
    await check_input_changes(uuid, inputs)
    # test name / desc changes
    sio.emit.reset_mock()
    handler = sio.handlers["/"]["widget:name_desc_change"]
    response = await run_task_until_done(
        handler("_sid", {"uuid": uuid, "name": "name1", "description": "desc1"})
    )
    sio.emit.assert_awaited_with("widget:details", ANY)
    # test input changes in widget details
    handler = sio.handlers["/"]["widget:get_details"]
    response = await run_task_until_done(handler("_sid", uuid))
    assert response["uuid"] == uuid
    maxlen = next(
        (i for i in response["inputs"] if i.get("attribute") == "maxlen"), None
    )
    assert maxlen["value"] == 100
    await remove_widget(uuid)


async def test_widget_invalid_inputs(_client):
    async with file_simulation(XTC):
        uuid0 = await add_widget("Absolute Temperature")
        uuid = await add_widget("ROG")
        # test invalid type change
        inputs = [
            ("maxlen", ""),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        # test invalid input change
        inputs = [
            ("selection", "invalid"),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        # test valid input change
        inputs = [
            ("selection", "resid 1"),
        ]
        await check_input_changes(uuid, inputs)
        # retain invalid input to skip run for this widget
        inputs = [
            ("selection", "invalid"),
        ]
        await check_input_changes(uuid, inputs, ["error"])
        await resume_file_simulation()
        assert await sio_event_emitted(sio, "widgets:output", n=1)
        await remove_widget(uuid0)
        await remove_widget(uuid)
