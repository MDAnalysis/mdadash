import asyncio
import time


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


async def sio_event_emitted(sio, event, timeout=5.0):
    max_time = time.monotonic() + timeout
    emitted = False
    while time.monotonic() < max_time:
        for call in sio.emit.await_args_list:
            args, _ = call
            emitted = args[0] == event
        if emitted:
            break
        await asyncio.sleep(0.01)
    return emitted
