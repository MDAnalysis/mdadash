import asyncio
import logging
import queue
import sys
import uuid

from jupyter_client import AsyncKernelManager

logger = logging.getLogger(__name__)


class KernelManager:
    """Kernel Manager

    This class is responsible for managing the AsyncKernelManager (async kernel)
    that runs all the MDAnalysis code. It takes care of starting the async
    kernel, stopping it and communicating with it. It interfaces with the
    CommHandler on the kernel side for messaging.

    """

    def __init__(self):
        self.km = AsyncKernelManager(kernel_name="python3")
        self.kc = None
        self._pending_futures = {}
        self._is_running = False
        self.comm_id = uuid.uuid4().hex
        self.listen_task = None

    async def start(self) -> None:
        """Start the async kernel"""
        # start the kernel
        await self.km.start_kernel()
        # create a client
        self.kc = self.km.client()
        self.kc.start_channels()
        await self.kc.wait_for_ready()
        # create task to listen on iopub and shell channels
        self.listen_task = asyncio.create_task(self._start_listening())
        # initialize the kernel core
        self.kc.execute("from mdadash.backend.kernel import core")
        # open comms with the kernel
        self._comm_open()
        self._is_running = True

    async def stop(self) -> None:
        """Stop the async kernel"""
        self._is_running = False
        # wait for listen task to completely exit
        await self.listen_task
        self.kc.stop_channels()
        self.kc = None
        # shutdown kernel gracefully
        await self.km.shutdown_kernel(now=False)
        await self.km.cleanup_resources()

    async def _start_listening(self):
        """Internal: Create separate listen tasks for iopub and shell"""
        await asyncio.gather(
            self._listen_iopub_channel(),
            self._listen_shell_channel(),
        )

    async def _listen_iopub_channel(self):
        """Internal: Listen on iopub channel"""
        while self._is_running:
            try:
                msg = await self.kc.iopub_channel.get_msg(timeout=0.1)
                msg_type = msg["header"]["msg_type"]
                content = msg["content"]
                parent_id = msg.get("parent_header", {}).get("msg_id")
                # check for responses that are being awaited
                if (
                    msg_type == "comm_msg"
                    and parent_id
                    and parent_id in self._pending_futures
                ):
                    future = self._pending_futures[parent_id]
                    if not future.done():
                        future.set_result(msg["content"]["data"])
                # redirect kernel stdout and stderr to this server output
                if msg_type == "stream":
                    if content["name"] == "stdout" or content["name"] == "stderr":
                        output = content["text"]
                        file = sys.stdout if content["name"] == "stdout" else sys.stderr
                        print(f"KERNEL: {output}", end="", file=file)
                else:
                    logger.debug("IOPUB: %s", msg)
                    # TODO: handle other message types
            except (asyncio.TimeoutError, queue.Empty):
                continue

    async def _listen_shell_channel(self):
        """Internal: Listen on shell channel"""
        while self._is_running:
            try:
                msg = await self.kc.shell_channel.get_msg(timeout=0.1)
                # msg_type = msg["header"]["msg_type"]
                # content = msg["content"]
                logger.debug("SHELL: %s", msg)
            except (asyncio.TimeoutError, queue.Empty):
                continue

    def _comm_open(self):
        """Internal: Open comms with the kernel"""
        content = {
            "comm_id": self.comm_id,
            "target_name": "kernel_comm_handler",
            "data": {"msg_type": "handshake"},
        }
        open_msg = self.kc.session.msg("comm_open", content=content)
        self.kc.shell_channel.send(open_msg)

    async def send_message(self, msg_type: str, data: dict) -> None:
        """Send message to kernel and don't await a response

        Parameters
        ----------
        msg_type: str
            A message type string that the kernel has a handler registered for

        data: dict
            Dict that gets passed to the handler in the kernel

        """
        content = {
            "comm_id": self.comm_id,
            "target_name": "kernel_comm_handler",
            "data": {"msg_type": msg_type, "data": data},
        }
        data_msg = self.kc.session.msg("comm_msg", content=content)
        self.kc.shell_channel.send(data_msg)

    async def send_message_await_response(
        self, msg_type: str, data: dict = None, timeout: int = 5
    ) -> dict | None:
        """Send message to kernel and wait for a response (async)

        Parameters
        ----------
        msg_type: str
            A message type string that the kernel has a handler registered for

        data: dict
            Dict that gets passed to the handler in the kernel

        """
        content = {
            "comm_id": self.comm_id,
            "target_name": "kernel_comm_handler",
            "data": {"msg_type": msg_type, "data": data},
        }
        data_msg = self.kc.session.msg("comm_msg", content=content)
        msg_id = data_msg["header"]["msg_id"]
        # add to the _pending_futures to that it gets resolved when the
        # response arrives on the iopub channel
        future = asyncio.get_running_loop().create_future()
        self._pending_futures[msg_id] = future
        self.kc.shell_channel.send(data_msg)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as e:
            raise TimeoutError("Timed out waiting for kernel response") from e
        finally:
            self._pending_futures.pop(msg_id, None)

    async def connect_to_simulation(self, config: dict = None) -> dict:
        """Connect to the MD simulation

        Parameters
        ----------
        config: dict
            Config dict required to create the MDAnalysis Universe

        Returns
        -------
        response: dict
            Response dict indicating status

        """
        return await self.send_message_await_response("connect_to_simulation", config)

    async def disconnect_from_simulation(self) -> dict:
        """Disconnect from the MD simulation

        Returns
        -------
        response: dict
            Response dict indicating status

        """
        return await self.send_message_await_response("disconnect_from_simulation")
