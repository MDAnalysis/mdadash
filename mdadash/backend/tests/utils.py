import asyncio
import time
from unittest.mock import AsyncMock

from mdadash.backend import main
from mdadash.backend.main import sio
from mdadash.backend.tests.data.files import TPR

sio.emit = AsyncMock()


async def run_task_until_done(coroutine, timeout=5.0):
    tick = 0.001
    elapsed = 0.0
    task = asyncio.create_task(coroutine)
    while not task.done():
        if elapsed >= timeout:
            task.cancel()
            raise TimeoutError("Timeout running task")
        await asyncio.sleep(tick)
        elapsed += tick
    return await task


async def sio_event_emitted(_sio, event, n=1, timeout=5.0):
    """Check if event is emitted n times"""
    max_time = time.monotonic() + timeout
    emitted = False
    while time.monotonic() < max_time:
        count = 0
        for call in _sio.emit.await_args_list:
            args, _ = call
            if args[0] == event:
                count += 1
        if count == n:
            emitted = True
            break
        await asyncio.sleep(0)
    return emitted


async def check_input_changes(uuid, inputs, status="ok"):
    for i in inputs:
        handler = sio.handlers["/"]["widget:input_change"]
        attribute, value = i
        response = await run_task_until_done(
            handler(
                "_sid",
                {"uuid": uuid, "attribute": attribute, "value": value},
            )
        )
        assert response["status"] == status


async def connect_to_simulation(imd_server):
    main.mdadash.sm.universe_configs[0].update(
        {
            "topology": str(TPR),
            "trajectory": f"imd://localhost:{imd_server.port}",
            "step": 2,
            "batch_size": 1,
        }
    )
    handler = sio.handlers["/"]["connect_to_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"


async def disconnect_from_simulation():
    handler = sio.handlers["/"]["disconnect_from_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"


async def resume_simulation(imd_server):
    sio.emit.reset_mock()  # clear emit.await_args_list
    handler = sio.handlers["/"]["resume_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"
    # send the frames needed by imdclient here
    imd_server.send_frames(1, 10)


async def pause_simulation():
    handler = sio.handlers["/"]["pause_simulations"]
    response = await run_task_until_done(handler("_sid"))
    assert response["status"] == "ok"


async def add_widget(name):
    handler = sio.handlers["/"]["widgets:add_widget"]
    response = await run_task_until_done(handler("_sid", 0, name, ""))
    uuid = response.get("uuid", None)
    assert uuid is not None
    return uuid


async def duplicate_widget(uuid1):
    handler = sio.handlers["/"]["widgets:duplicate_widget"]
    response = await run_task_until_done(handler("_sid", 0, uuid1, "Current Name", ""))
    uuid2 = response.get("uuid", None)
    assert uuid2 is not None
    return uuid2


async def remove_widget(uuid):
    handler = sio.handlers["/"]["widgets:remove_widget"]
    response = await run_task_until_done(handler("_sid", uuid))
    assert response["status"] == "ok"
