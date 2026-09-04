"""
Kernel core where MDAnalysis code runs
"""

import ast
import asyncio
import copy
import io
import logging
import numbers
import sys
from collections import deque
from dataclasses import asdict

import comm
import IPython
import MDAnalysis as mda
import numpy as np
from MDAnalysis.coordinates.base import (
    FrameIteratorAll,
    FrameIteratorBase,
    ProtoReader,
    ReaderBase,
)
from MDAnalysis.coordinates.IMD import IMDReader
from MDAnalysis.lib.util import NamedStream
from MDAnalysis.transformations import NoJump

from mdadash.backend.widgets.base import WidgetManager

logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger(__name__)


class BufferFrameIteratorIndices(FrameIteratorBase):
    """BufferFrameIteratorIndices

    Iterable over the frames of a trajectory buffer listed as a sequence of indices.
    This is very similar to :class:`~MDAnalysis.coordinates.base.FrameIteratorIndices`
    in MDAnalysis, but without ``rewind()`` and ``__getitem__`` as they aren't needed here.

    """

    def __init__(self, trajectory: ReaderBase, frames: list):
        super().__init__(trajectory)
        self._frames = []
        for frame in frames:
            if not isinstance(frame, numbers.Integral):  # pragma: no cover
                raise TypeError("Frames indices must be integers.")
            frame = trajectory._apply_limits(frame)
            self._frames.append(frame)
        self._frames = tuple(self._frames)

    def __len__(self):
        return len(self.frames)

    def __iter__(self):
        for frame in self.frames:
            yield self.trajectory[frame]

    @property
    def frames(self):
        return self._frames


class BufferedTrajectory:
    """Buffered Trajectory

    This class is a wrapper for the trajectory reader and provides
    buffered access to the last n timesteps.

    ``trajectory[index]`` can be used to access individual frames. Index values
    can range from 0 to the configured batch size.

    """

    def __init__(self, trajectory: ReaderBase, buffer_size: int):
        self._trajectory = trajectory
        self._buffer_size = buffer_size
        self._buffer = deque(maxlen=buffer_size)
        self._buffer.append(trajectory.ts.copy())
        BufferedTrajectory.next.__doc__ = type(trajectory).next.__doc__

    @property
    def n_frames(self):
        return len(self._buffer)

    @property
    def buffer_size(self):
        return self._buffer_size

    def __len__(self):
        return len(self._buffer)

    def check_slice_indices(self, start, stop, step):
        return ProtoReader.check_slice_indices(self, start, stop, step)

    def _apply_limits(self, frame):
        if frame >= len(self._buffer):
            frame = -1
        return frame

    def __getitem__(self, index):
        if isinstance(index, numbers.Integral):
            ts = self._buffer[index]
            self._trajectory.ts = ts
            return ts
        if isinstance(index, slice):
            return FrameIteratorAll(self)
        if isinstance(index, (list, np.ndarray)):
            return BufferFrameIteratorIndices(self, index)
        raise TypeError("Unsupported trajectory indexing")  # pragma: no cover

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

    def _prepare_for_next(self):
        """IMDReader during `_read_frame` loads the new frame into the current
        timestep using `_load_imdframe_into_ts`. This will overwrite the values
        if current ts is a reference to a buffer item. Hence make a copy to
        prevent current buffer items from getting overwritten during iteration.
        """
        self._trajectory.ts = self._buffer[-1].copy()


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

    def _handle_msg(self, msg: dict):
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

    def __init__(self, _comms: CommHandler):
        self._universes = []
        self._universe_configs = []
        self._streaming = False
        self._iter_loop_task = None
        self._iter_loop_running = False
        self._iter_loop_resumed = asyncio.Event()
        self._iter_loop_resumed.clear()
        self._wm: WidgetManager = None
        self._comms = _comms
        self._connected = False
        self._running = False
        self._3dview_selection = ""
        self._3dview_selection_ag = None

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

    # pylint: disable=too-many-branches
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
                if config["nojump"]:
                    u.trajectory.add_transformations(NoJump())
                if isinstance(u.trajectory, IMDReader):
                    self._streaming = True
                u.trajectory = BufferedTrajectory(
                    u.trajectory,
                    config["batch_size"],
                )
                if uid == 0:
                    self._send_tsdata(u)
                    if self._streaming:
                        self._send_sessioninfo(u)
                self._universes[uid] = u
                # set variable u to point to the first universe
                IPython.get_ipython().run_cell("u=core.um[0]")
                # run custom universe setup code
                if "custom_universe_setup" in config:
                    IPython.get_ipython().run_cell(config["custom_universe_setup"])
                # set universe for the widget instances with this uid
                self._wm._set_universe(uid, u)
            # save universe configs
            self._universe_configs = copy.deepcopy(universe_configs)
            # start iter loop for trajectories
            self._iter_loop_resumed.clear()
            self._iter_loop_running = True
            self._iter_loop_task = asyncio.create_task(self._iter_loop())
            self._connected = True
            self._comms.send({"status": "ok"})
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to connect to simulations")
            self._comms.send({"status": "error", "message": str(e)})
        # create the 3dview selection AtomGroup
        try:
            self._3dview_selection_ag = self._universes[0].select_atoms(
                self._3dview_selection
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to create 3dview selection AtomGroup")

    def _send_tsdata(self, u: mda.Universe):
        """Internal: Send timestep data out"""
        self._comms.send(
            {
                "tsinfo": {
                    "frame": u.trajectory.frame,
                    "tsdata": u.trajectory.ts.data,
                }
            }
        )
        if self._3dview_selection_ag is not None:
            positions = self._3dview_selection_ag.atoms.positions.T.astype(
                "float32"
            ).tobytes()
            self._comms._comm.send(
                data={"positions": None},
                buffers=[positions],
            )

    def _send_sessioninfo(self, u: mda.Universe):
        """Internal: Send session info from imdclient"""
        self._comms.send(
            {"sessioninfo": asdict(u.trajectory._imdclient.get_imdsessioninfo())}
        )

    def _disconnect_from_simulations(self):
        """Internal: Cancel iteration loop and close trajectories"""
        self._iter_loop_running = False
        if self._iter_loop_task is not None:
            self._iter_loop_task.cancel()
            self._iter_loop_task = None
        for u in self._universes:
            try:
                u.trajectory.close()
            except AttributeError:
                pass
            except Exception:  # pylint: disable=broad-exception-caught # pragma: no cover
                logger.exception("Failed to close trajectory")
        self._connected = False
        self._running = False

    def disconnect_from_simulations(self, _data: dict) -> None:
        """Disconnect from MD simulations"""
        self._disconnect_from_simulations()
        self._wm._invoke_lifecycle_method("on_post_disconnect")
        self._comms.send({"status": "ok"})

    def pause_simulations(self, _data: dict) -> None:
        """Pause MD simulations"""
        self._iter_loop_resumed.clear()
        self._running = False
        self._wm._invoke_lifecycle_method("on_post_pause")
        self._comms.send({"status": "ok"})

    def resume_simulations(self, _data: dict) -> None:
        """Resume MD simulations"""
        self._wm._invoke_lifecycle_method("on_pre_resume")
        self._iter_loop_resumed.set()
        self._running = True
        self._comms.send({"status": "ok"})

    def _trajectory_next(self, u: mda.Universe, step: int):
        """Internal: Iterate trajectory by `step` frame(s)"""
        try:
            # TODO: Modify this when `imdclient` and `IMDReader` are updated
            #   with support for 'Transmission rate' packet
            # Burn the timesteps until we reach the desired step
            # Don't use next() to avoid unnecessary transformations
            u.trajectory._prepare_for_next()
            while (u.trajectory._frame + 1) % step != 0:
                u.trajectory._read_next_timestep()
            u.trajectory.next()
        except (OSError, EOFError, StopIteration):  # pragma: no cover
            pass

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
                        self._wm.run_widgets(uid, batch_ready)
                    # pylint: disable=broad-exception-caught
                    except Exception:  # pragma: no cover
                        logger.exception("Trajectory iteration failed for uid %d", uid)
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass

    def get_topology(self, _data: dict):
        """Get topology of current 3dview selection"""
        ag = self._3dview_selection_ag
        if self._universes[0] is None or ag is None or ag.n_atoms == 0:
            self._comms.send(None)
            return
        buffer = io.StringIO()
        stream = NamedStream(buffer, "topology.gro")
        with mda.Writer(stream, n_atoms=ag.n_atoms) as writer:
            writer.write(ag)
        self._comms.send(buffer.getvalue())

    def update_3dview_selection(self, data: dict):
        """Update 3dview selection phrase"""
        selection = data["selection"]
        self._3dview_selection = selection
        if self._universes[0] is None:
            self._comms.send(None)
            return
        if selection == "":
            self._3dview_selection_ag = None
            self._comms.send("Please enter a selection phrase")
            return
        try:
            self._3dview_selection_ag = self._universes[0].select_atoms(selection)
            error = ""
        except Exception as e:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            self._3dview_selection = ""
            self._3dview_selection_ag = None
            error = str(e)
        self._comms.send(error)


def init_n_universes(data: dict) -> None:
    """Initialize `n` universes in :class:`UniverseManager`"""
    um.init_n_universes(data["n"])


def run_notebooks(notebooks: dict) -> None:
    """Run notebooks from loaded state file"""
    ipy = IPython.get_ipython()
    for notebook in notebooks.values():
        if not notebook["run_on_launch"]:
            continue
        for cell in notebook["cells"]:
            ipy.run_cell(cell["code"])
    comms.send({"status": "ok"})


comms = CommHandler()
wm = WidgetManager(comms)
um = UniverseManager(comms)

# link
um._wm = wm  # WidgetManager to UniverseManager
wm._um = um  # UniverseManager to WidgetManager
# register handlers
# for core
comms.register_handler("init_n_universes", init_n_universes)
comms.register_handler("notebooks:run", run_notebooks)
# for universe manager
comms.register_handler("connect_to_simulations", um.connect_to_simulations)
comms.register_handler("disconnect_from_simulations", um.disconnect_from_simulations)
comms.register_handler("pause_simulations", um.pause_simulations)
comms.register_handler("resume_simulations", um.resume_simulations)
comms.register_handler("get_topology", um.get_topology)
comms.register_handler("update_3dview_selection", um.update_3dview_selection)
# for widget manager
comms.register_handler("widgets:get_available_widgets", wm.get_available_widgets)
comms.register_handler("widgets:recreate_instances", wm.recreate_instances)
comms.register_handler("widgets:remove_instance", wm.remove_widget_instance)
comms.register_handler("widget:get_inputs", wm.get_widget_inputs)
comms.register_handler("widget:set_input", wm.set_widget_input)
comms.register_handler("execute_code", wm.execute_code)
comms.register_handler("update_n_jobs", wm.update_n_jobs)
comms.register_handler("widgets:add_instance", wm.add_widget_instance)
comms.register_handler("widgets:duplicate_instance", wm.duplicate_widget_instance)

# disable jedi for code complete in macOS python 3.12
# this times out when used with AsyncKernelManager
if sys.platform == "darwin" and sys.version == (3, 12):  # pragma: no cover
    IPython.get_ipython().Completer.use_jedi = False
