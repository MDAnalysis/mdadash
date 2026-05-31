import asyncio


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
