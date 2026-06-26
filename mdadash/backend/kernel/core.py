"""
Kernel core where MDAnalysis code runs
"""

import ast
import asyncio
import copy
from collections import deque
from dataclasses import asdict

import comm
import IPython
import MDAnalysis as mda

from mdadash.backend.widgets.base import WidgetManager


class BufferedTrajectory:
    """Buffered Trajectory

    This class is a wrapper for the trajectory reader and provides
    buffered access to the last n timesteps.

    `trajectory[index]` can be used to access individual frames. Index values
    should be <= 0. `trajectory[0]` indicates the current frame, `trajectory[-1]`
    indicates the previous frame and so on till the configured batch size.

    """

    def __init__(self, trajectory: mda.Universe.trajectory, batch_size: int):
        self._trajectory = trajectory
        self._batch_size = batch_size
        self._buffer = deque(maxlen=batch_size)
        self._buffer.append(trajectory.ts.copy())
        BufferedTrajectory.next.__doc__ = type(trajectory).next.__doc__

    def __getitem__(self, index):
        if index > 0:
            raise ValueError("index should be <= 0")
        if index <= -1 * self._batch_size:
            raise ValueError("Out of range of buffer")
        ts = self._buffer[index - 1]
        self._trajectory.ts = ts
        return ts

    def __getattr__(self, name):
        wrapped = object.__getattribute__(self, "_trajectory")
        return getattr(wrapped, name)

    def __dir__(self):
        return list(set(dir(super().__dir__()) + dir(self._trajectory)))

    def next(self):
        """Iterate next frame and copy timestep into buffer"""
        ts = self._trajectory.next()
        self._buffer.append(ts.copy())
        return ts


class CommHandler:
    """Comm Handler

    This class is responsible for handling all the communication to and
    from this kernel. This is the class that interfaces with the
    :class:`~mdadash.backend.kernel.manager.KernelManager` on the server side.

    """

    def __init__(self):
        self._comm = None
        self._handlers = {}
        comm.get_comm_manager().register_target(
            "kernel_comm_handler", self._handle_comm_open
        )

    def register_handler(self, msg_type: str, handler_func: callable) -> None:
        """Register a handler function for a message type

        Parameters
        ----------
        msg_type: str
            A message type to identify the handler

        handler_func: callable
            The handler function to invoke when a message with this message
            type is received

        """
        self._handlers[msg_type] = handler_func

    def send(self, msg: dict) -> None:
        """Send a message (response) back on the comm

        Parameters
        ----------
        msg: dict
            A generic message dictionary

        """
        if self._comm is not None:
            self._comm.send(msg)
        else:
            raise ValueError("comm is not open yet")  # pragma: no cover

    def _handle_comm_open(self, _comm: comm.base_comm.BaseComm, _msg):
        """Internal: Handler when the comm is opened (comm_open)"""
        self._comm = _comm
        # set the handler for comm messages (comm_msg)
        self._comm.on_msg(self._handle_msg)

    def _handle_msg(self, msg):
        """Internal: Dispatch the message to the registered handler"""
        content_data = msg["content"]["data"]
        msg_type = content_data["msg_type"]
        if msg_type in self._handlers:
            self._handlers[msg_type](content_data["data"])
        else:
            error_msg = f"{msg_type} does not have a registered handler"
            self.send({"status": "error", "message": error_msg})
            raise ValueError(error_msg)


class UniverseManager:
    """Universe Manager

    This class is responsible for managing all MDAnalysis universes. It has
    handlers to interact with the MD simulation. These handlers are invoked by
    comm messages sent from the server.

    This also provides an iterable and indexable access to the individual
    universes.

    """

    def __init__(self, _wm: WidgetManager, _comm_handler: CommHandler):
        self._universes = []
        self._universe_configs = []
        self._iter_loop_task = None
        self._iter_loop_running = False
        self._iter_loop_resumed = asyncio.Event()
        self._iter_loop_resumed.clear()
        self._wm = _wm
        self._comm_handler = _comm_handler
        self._connected = False
        self._running = False

    def __iter__(self) -> iter:
        """To support iteration"""
        return iter(self._universes)

    def __len__(self) -> int:
        """Number of universes"""
        return len(self._universes)

    def __getitem__(self, index: int):
        """Return universe based on index"""
        # numeric index based array access
        _max = len(self._universes)
        if 0 <= index < _max:
            return self._universes[index]
        raise ValueError(f"Invalid index {index} of {_max} items")

    def init_n_universes(self, n: int) -> None:
        """Initialize array for n universes

        Parameters
        ----------
        n: int
            Number of universes to initialize

        """
        self._universes = [None] * n
        self._universe_configs = [{}] * n

    def _cast_value(self, value: str):
        """Internal: Infer and cast value to correct type"""
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value

    def connect_to_simulations(self, universe_configs: list[dict]) -> None:
        """Connect to MD simulations

        Parameters
        ----------
        universe_configs: list[dict]
            A list of configurations for universe(s) creation.
            Each dict has universe related config like topology, trajectory,
            imdclient params, user-defined kwargs etc

        """
        self._disconnect_from_simulations()
        try:
            for uid, config in enumerate(universe_configs):
                kwargs = {}
                topology = config["topology"]
                trajectory = config["trajectory"]
                for key, value in config.items():
                    if key in (
                        "topology",
                        "trajectory",
                        "step",
                        "total_steps",
                        "kwargs",
                    ):
                        continue
                    if value is not None:
                        kwargs[key] = value
                for name, value in config["kwargs"]:
                    if name.strip():
                        kwargs[name] = self._cast_value(value)
                # create universe
                u = mda.Universe(
                    topology,
                    trajectory,
                    **kwargs,
                )
                u.trajectory = BufferedTrajectory(
                    u.trajectory,
                    config["batch_size"],
                )
                if uid == 0:
                    self._send_tsdata(u)
                    self._send_sessioninfo(u)
                self._universes[uid] = u
                # set universe for the widget instances with this uid
                self._wm._set_universe(uid, u)
            # save universe configs
            self._universe_configs = copy.deepcopy(universe_configs)
            # start iter loop for trajectories
            self._iter_loop_resumed.clear()
            self._iter_loop_running = True
            self._iter_loop_task = asyncio.create_task(self._iter_loop())
            self._connected = True
            self._comm_handler.send({"status": "ok"})
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(e)
            self._comm_handler.send({"status": "error", "message": str(e)})

    def _send_tsdata(self, u: mda.Universe):
        """Internal: Send timestep data out"""
        self._comm_handler.send(
            {
                "tsinfo": {
                    "frame": u.trajectory.frame,
                    "tsdata": u.trajectory.ts.data,
                }
            }
        )

    def _send_sessioninfo(self, u: mda.Universe):
        self._comm_handler.send(
            {"sessioninfo": asdict(u.trajectory._imdclient.get_imdsessioninfo())}
        )

    def _disconnect_from_simulations(self):
        self._iter_loop_running = False
        if self._iter_loop_task is not None:
            self._iter_loop_task.cancel()
            self._iter_loop_task = None
        for u in self._universes:
            try:
                u.trajectory.close()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        self._connected = False
        self._running = False

    def disconnect_from_simulations(self, _data: dict) -> None:
        """Disconnect from MD simulations"""
        self._disconnect_from_simulations()
        self._wm._invoke_lifecycle_method("post_disconnect")
        self._comm_handler.send({"status": "ok"})

    def pause_simulations(self, _data: dict) -> None:
        """Pause MD simulations"""
        self._iter_loop_resumed.clear()
        self._running = False
        self._wm._invoke_lifecycle_method("post_pause")
        self._comm_handler.send({"status": "ok"})

    def resume_simulations(self, _data: dict) -> None:
        """Resume MD simulations"""
        self._wm._invoke_lifecycle_method("pre_resume")
        self._iter_loop_resumed.set()
        self._running = True
        self._comm_handler.send({"status": "ok"})

    def _trajectory_next(self, u, step):
        """Internal: Iterate trajectory by `step` frame(s)"""
        try:
            # TODO: Modify this when `imdclient` and `IMDReader` are updated
            #   with support for 'Transmission rate' packet
            # Burn the timesteps until we reach the desired step
            # Don't use next() to avoid unnecessary transformations
            while (u.trajectory._frame + 1) % step != 0:
                u.trajectory._read_next_timestep()
        except (EOFError, IOError):  # pragma: no cover
            raise StopIteration from None
        return u.trajectory.next()

    async def _iter_loop(self):
        """Internal: Iteration loop for trajectories"""
        try:
            while self._iter_loop_running:
                await self._iter_loop_resumed.wait()
                for uid, u in enumerate(self._universes):
                    step = self._universe_configs[uid]["step"]
                    batch_size = self._universe_configs[uid]["batch_size"]
                    try:
                        # iterate in thread to not block on a network call here
                        await asyncio.to_thread(
                            self._trajectory_next,
                            u,
                            step,
                        )
                        if uid == 0:
                            self._send_tsdata(u)
                        # run widgets for this timestep
                        batch_ready = (u.trajectory._frame + step) % (
                            step * batch_size
                        ) == 0
                        self._wm.run_widgets(uid, batch_ready, batch_size)
                    # pylint: disable=broad-exception-caught
                    except Exception as e:  # pragma: no cover
                        print(e)
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass


class WidgetsComm:
    """Widgets Communication

    This class is responsible for handling communications related to widgets.
    It uses :class:`~mdadash.backend.widgets.base.WidgetManager` instance and
    communicates via :class:`CommHandler` back to the server from this kernel.

    """

    def __init__(
        self, _um: UniverseManager, _wm: WidgetManager, _comm_handler: CommHandler
    ):
        self._um = _um
        self._wm = _wm
        self._comm_handler = _comm_handler

    def get_available_widgets(self, _data: dict):
        """Send list of available widgets - name and description"""
        widgets = []
        for widget_class in self._wm.classes.values():
            widgets.append(
                {
                    "name": getattr(widget_class, "name"),
                    "description": getattr(widget_class, "description", None),
                }
            )
        self._comm_handler.send({"widgets": widgets})

    def add_instance(self, data: dict) -> dict:
        """Add widget instance based on registered widget name"""
        uid = data["uid"]
        widget_name = data["name"]
        uuid = self._wm.add_widget_instance(uid, widget_name)
        if uuid is not None:
            if self._um._connected:
                # set the universe for the new widget instance
                self._wm._set_universe(uid, self._um._universes[uid], uuid)
            self._comm_handler.send({"status": "ok", "uuid": uuid})
        else:
            self._comm_handler.send(
                {
                    "status": "error",
                    "message": f"Failed to add widget instance for {widget_name}",
                }
            )

    def duplicate_instance(self, data: dict) -> None:
        """Duplicate widget instance based on instance uuid"""
        uid = data["uid"]
        new_uuid = self._wm.duplicate_widget_instance(uid, data["uuid"])
        if self._um._connected:
            # set the universe for the new widget instance
            self._wm._set_universe(uid, self._um._universes[uid], new_uuid)
        self._comm_handler.send({"status": "ok", "uuid": new_uuid})

    def remove_instance(self, data: dict) -> dict:
        """Remove widget instance based on uuid"""
        uuid = self._wm.delete_widget_instance(data["uuid"])
        if uuid is not None:
            self._comm_handler.send({"status": "ok"})
        else:
            self._comm_handler.send(
                {
                    "status": "error",
                    "message": f"Failed to remove widget instance with uuid {uuid}",
                }
            )

    def get_inputs(self, data: dict) -> list:
        """Get the inputs for a widget instance"""
        self._comm_handler.send(
            {"status": "ok", "inputs": self._wm.get_inputs(data["uuid"])}
        )

    def set_input(self, data: dict) -> list:
        """Set an input for a widget instance"""
        ret = self._wm.set_input(data["uuid"], data["attribute"], data["value"])
        self._comm_handler.send({"status": "ok" if ret else "error"})


def init_n_universes(data: dict) -> None:
    """Initialize `n` universes in :class:`UniverseManager`"""
    um.init_n_universes(data["n"])


def execute_code(data: dict) -> dict:
    """Execute code in this kernel"""
    with IPython.utils.capture.capture_output() as output:
        result = IPython.get_ipython().run_cell(data["code"])
        if result.success:
            comm_handler.send({"output": output.stdout})
        else:
            comm_handler.send({"output": str(result.error_in_exec)})


wm = WidgetManager()
comm_handler = CommHandler()
um = UniverseManager(wm, comm_handler)
widgets_comm = WidgetsComm(um, wm, comm_handler)

# register handlers
comm_handler.register_handler("init_n_universes", init_n_universes)
comm_handler.register_handler("connect_to_simulations", um.connect_to_simulations)
comm_handler.register_handler(
    "disconnect_from_simulations", um.disconnect_from_simulations
)
comm_handler.register_handler("pause_simulations", um.pause_simulations)
comm_handler.register_handler("resume_simulations", um.resume_simulations)
comm_handler.register_handler(
    "widgets:get_available_widgets", widgets_comm.get_available_widgets
)
comm_handler.register_handler("widgets:add_instance", widgets_comm.add_instance)
comm_handler.register_handler(
    "widgets:duplicate_instance", widgets_comm.duplicate_instance
)
comm_handler.register_handler("widgets:remove_instance", widgets_comm.remove_instance)
comm_handler.register_handler("widget:get_inputs", widgets_comm.get_inputs)
comm_handler.register_handler("widget:set_input", widgets_comm.set_input)
comm_handler.register_handler("execute_code", execute_code)
comm_handler.register_handler("update_n_jobs", wm.update_n_jobs)
