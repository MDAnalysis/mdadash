"""
Manager that manages the jupyter_client's AsyncKernelManager
"""

import asyncio
import logging
import queue
import sys
import uuid
from typing import Any

import socketio
from jupyter_client import AsyncKernelManager

from ..state.manager import StateManager
from .utils import EMATrend

logger = logging.getLogger(__name__)


class KernelManager:
    """Kernel Manager

    This class is responsible for managing the AsyncKernelManager (async kernel)
    that runs all the MDAnalysis code. It takes care of starting the async
    kernel, stopping it and communicating with it. It interfaces with the
    :class:`~mdadash.backend.kernel.core.CommHandler` on the kernel side for messaging.

    Parameters
    ----------
    sm: :class:`~mdadash.backend.state.manager.StateManager`
        Instance of the state manager

    sio: :class:`socketio.AsyncServer`
        Instance of the socket.io server

    """

    def __init__(self, sm: StateManager, sio: socketio.AsyncServer):
        self.sm = sm
        self.sio = sio
        self.km = AsyncKernelManager(kernel_name="python3")
        self.kc = None
        self._pending_futures = {}
        self._is_running = False
        self.comm_id = uuid.uuid4().hex
        self.listen_task = None
        self._sessioninfo = None
        self._last_tsdata = None
        self._energy_keys = [
            "temperature",
            "total_energy",
            "potential_energy",
            "van_der_walls_energy",
            "coulomb_energy",
            "bonds_energy",
            "angles_energy",
            "dihedrals_energy",
            "improper_dihedrals_energy",
        ]
        self._energy_trends = {}

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
        # initialize n universes in kernel universe manager
        await self.send_message(
            "init_n_universes", {"n": len(self.sm.universe_configs)}
        )

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

    def _get_energy_trend(self, key, value):
        """Internal: Update and get trend for energy value"""
        if key not in self._energy_trends:
            self._energy_trends[key] = EMATrend()
        return self._energy_trends[key].update(value)

    async def _emit_tsdata(self, tsinfo):
        """Internal: Emit timestep data"""
        tsdata = tsinfo["tsdata"]
        step = tsdata.get("step", None)
        total_steps = self.sm.universe_configs[0].get("total_steps", None)
        done = (step / total_steps) * 100 if step and total_steps else None
        energies = {}
        if tsdata.get("temperature") is not None:
            for key in self._energy_keys:
                energies[key] = {
                    "value": tsdata.get(key),
                    "trend": self._get_energy_trend(key, tsdata.get(key)),
                }
        timestep_info = {
            "frame": tsinfo.get("frame", None),
            "time": tsdata.get("time", None),
            "step": step,
            "done": done,
            "energies": energies,
        }
        self._last_tsdata = timestep_info
        await self.sio.emit("timestepInfo", timestep_info)

    async def _emit_sessioninfo(self, sessioninfo):
        """Internal: Emit imdclient session info"""
        self._sessioninfo = sessioninfo
        await self.sio.emit("sessionInfo", sessioninfo)

    async def _emit_last_known_values(self, sid=None) -> None:
        """Internal: Emit last saved values"""
        if self._last_tsdata is not None:
            await self.sio.emit("timestepInfo", self._last_tsdata, to=sid)
        if self._sessioninfo is not None:
            await self.sio.emit("sessionInfo", self._sessioninfo, to=sid)

    # pylint: disable=too-many-branches
    async def _listen_iopub_channel(self):
        """Internal: Listen on iopub channel"""
        # pylint: disable=too-many-nested-blocks
        while self._is_running:
            try:
                msg = await self.kc.iopub_channel.get_msg(timeout=0.1)
                msg_type = msg["header"]["msg_type"]
                content = msg["content"]
                # handle different msg_type's
                if msg_type == "comm_msg":
                    data = msg["content"]["data"]
                    if "tsinfo" in data:
                        await self._emit_tsdata(data["tsinfo"])
                    elif "sessioninfo" in data:
                        await self._emit_sessioninfo(data["sessioninfo"])
                    else:
                        parent_id = msg.get("parent_header", {}).get("msg_id")
                        # check if a pending future can be resolved with msg
                        resolve_future = False
                        if parent_id and parent_id in self._pending_futures:
                            future = self._pending_futures[parent_id]
                            if not future.done():
                                resolve_future = True
                        if resolve_future:
                            future.set_result(data)
                elif msg_type == "stream":
                    # redirect kernel stdout and stderr to this server output
                    if content["name"] == "stdout" or content["name"] == "stderr":
                        output = content["text"]
                        file = sys.stdout if content["name"] == "stdout" else sys.stderr
                        print(
                            f"KERNEL ({content['name']}): {output}", end="", file=file
                        )
                elif msg_type == "error":
                    # redirect kernel errors to server output
                    print(f"KERNEL (error): {content['ename']}: {content['evalue']}")
                elif msg_type == "display_data":
                    if "metadata" in content and "widget_uuid" in content["metadata"]:
                        # send widget output to browser
                        await self.sio.emit(
                            "widgets:output",
                            {
                                "uuid": content["metadata"]["widget_uuid"],
                                "data": content["data"],
                            },
                        )
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
            Dict that gets passed to the handler in the kernel (default: None)

        timeout: int
            Timeout in seconds (default: 5)

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

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
        except asyncio.TimeoutError as e:  # pragma: no cover
            raise TimeoutError("Timed out waiting for kernel response") from e
        finally:
            self._pending_futures.pop(msg_id, None)

    async def execute_code(self, code: str, timeout: int = 5) -> str:
        """Execute code in the kernel

        Parameters
        ----------
        code: str
            Code to execute in the kernel

        timeout: int
            Timeout in seconds (default: 5)

        Returns
        -------
        response: str
            A string representation of the output of the code executed

        """
        response = await self.send_message_await_response(
            "execute_code", {"code": code}, timeout
        )
        return response["output"]

    async def connect_to_simulations(self) -> dict:
        """Connect to the MD simulation

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

        """
        try:
            response = await self.send_message_await_response(
                "connect_to_simulations",
                self.sm.universe_configs,
                timeout=20,
            )
            if response["status"] == "ok":
                self.sm.running_state["connected"] = True
                self.sm.running_state["running"] = False
        except TimeoutError:  # pragma: no cover
            response = {
                "status": "error",
                "message": "Timeout connecting to simulation",
            }
        return response

    async def disconnect_from_simulations(self) -> dict:
        """Disconnect from the MD simulation

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

        """
        response = await self.send_message_await_response(
            "disconnect_from_simulations", {}
        )
        if response["status"] == "ok":
            self.sm.running_state["connected"] = False
        return response

    async def pause_simulations(self) -> dict:
        """Pause MD simulations

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

        """
        response = await self.send_message_await_response("pause_simulations", {})
        if response["status"] == "ok":
            self.sm.running_state["running"] = False
        return response

    async def resume_simulations(self) -> dict:
        """Resume MD simulations

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

        """
        response = await self.send_message_await_response("resume_simulations", {})
        if response["status"] == "ok":
            self.sm.running_state["running"] = True
        return response

    async def get_available_widgets(self) -> dict:
        """Get list of available widgets

        Returns
        -------
        response: dict
            List of widget names and descriptions

        """
        return await self.send_message_await_response(
            "widgets:get_available_widgets", {}
        )

    async def add_widget_instance(self, uid: int, widget_name: str) -> dict:
        """Add widget instance

        Parameters
        ----------
        uid: int
            Universe ID (index into universes array)

        widget_name: str
            Widget name to create an instance for

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

        """
        return await self.send_message_await_response(
            "widgets:add_instance", {"uid": uid, "name": widget_name}
        )

    async def duplicate_widget_instance(self, uid: int, widget_uuid: str) -> dict:
        """Duplicate widget instance

        Parameters
        ----------
        uid: int
            Universe ID (index into universes array)

        widget_uuid: str
            UUID of the widget instance to be duplicated

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

        """
        return await self.send_message_await_response(
            "widgets:duplicate_instance", {"uid": uid, "uuid": widget_uuid}
        )

    async def remove_widget_instance(self, widget_uuid: str) -> dict:
        """Remove widget instance

        Parameters
        ----------
        widget_uuid: str
            UUID of the widget instance to be removed

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

            message
                An error message string when status is 'error'

        """
        return await self.send_message_await_response(
            "widgets:remove_instance", {"uuid": widget_uuid}
        )

    async def _get_widget_inputs(self, widget_uuid: str) -> list:
        """Internal: Get widget inputs from kernel core"""
        return await self.send_message_await_response(
            "widget:get_inputs", {"uuid": widget_uuid}
        )

    async def get_widget_details(self, widget_uuid: str) -> dict:
        """Get widget details

        Get the widget name, description and inputs

        Parameters
        ----------
        widget_uuid: str
            UUID of the widget instance

        Returns
        -------
        response: dict
            Response dict containing name, desc and inputs

        """
        widget = next(
            (w for w in self.sm.widgets_layout if w["i"] == widget_uuid), None
        )
        response = await self._get_widget_inputs(widget_uuid)
        return {
            "uuid": widget_uuid,
            "name": widget["name"],
            "description": widget["description"],
            "inputs": response["inputs"],
        }

    async def set_widget_input(
        self, widget_uuid: str, attribute: str, value: Any
    ) -> dict:
        """Set widget input

        Set the widget input value for given attribute

        Parameters
        ----------
        widget_uuid: str
            UUID of the widget instance

        attribute: str
            The attribtue to set in the instance

        value: Any
            The value to set for the above attribute

        Returns
        -------
        response: dict
            Response dict indicating status. This has the following keys:

            status
                String indication status: 'ok' or 'error'

        """
        response = await self.send_message_await_response(
            "widget:set_input",
            {
                "uuid": widget_uuid,
                "attribute": attribute,
                "value": value,
            },
        )
        details = await self.get_widget_details(widget_uuid)
        await self.sio.emit("widget:details", details)
        return response

    async def update_n_jobs(self, n_jobs: int) -> None:
        """Update n_jobs for joblib.Parallel

        Parameters
        ----------
        n_jobs: int
            Number of parallel jobs

        """
        await self.send_message("update_n_jobs", {"n_jobs": n_jobs})
