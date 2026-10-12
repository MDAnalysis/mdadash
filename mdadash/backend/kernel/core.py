# pylint: disable=too-many-lines
"""
Kernel core where MDAnalysis code runs
"""

import ast
import asyncio
import copy
import io
import logging
import numbers
import os
import socket
import sys
from dataclasses import asdict
from multiprocessing import shared_memory

import comm
import IPython
import MDAnalysis as mda
import numpy as np
from joblib import Parallel
from MDAnalysis.coordinates.base import (
    FrameIteratorAll,
    FrameIteratorBase,
    ProtoReader,
    ReaderBase,
)
from MDAnalysis.coordinates.IMD import IMDReader
from MDAnalysis.coordinates.timestep import Timestep
from MDAnalysis.lib.util import NamedStream
from MDAnalysis.transformations import NoJump

from mdadash.backend.widgets.base import WidgetManager

os.environ["PYTHONWARNINGS"] = (
    f"{os.environ.get('PYTHONWARNINGS', '')},ignore:resource_tracker:UserWarning".strip(
        ","
    )
)


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


class MultiArrayBuffer:
    """Multi Array Buffer

    This class manages a single contiguous buffer that is used by multiple
    numpy arrays. All individual np arrays are 64-byte aligned. There is an
    option to create this memory buffer as shared memory to achieve zero-copy
    access from parallel worker processes.

    """

    # The following class variables are only used by the workers to cache and
    # re-use the shared memory without having to re-attach every time.
    # The gen value is used to indicate a new shared mem block which happens
    # during a disconnect / re-connect when a new BufferedTrajectory is created
    _cached_shm = None
    _cached_buffer = None
    _cached_gen = -1

    def __init__(self, spec: dict, use_shm: bool = True):
        # only the main process creates the buffer
        self.is_worker = False
        self.spec = spec
        self.use_shm = use_shm

        self.offsets = {}
        current_offset = 0
        for name, array in self.spec.items():
            dtype = np.dtype(array["dtype"])
            size_bytes = int(np.prod(array["shape"]) * dtype.itemsize)
            self.offsets[name] = {
                "start": current_offset,
                "end": current_offset + size_bytes,
                "shape": array["shape"],
                "dtype": array["dtype"],
            }
            current_offset += size_bytes
            current_offset = (current_offset + 63) // 64 * 64  # 64-byte aligned
        self.total_bytes = current_offset

        if self.use_shm:
            self.shm = shared_memory.SharedMemory(create=True, size=self.total_bytes)
            self.shm_name = self.shm.name
            self.buffer = np.ndarray(
                (self.total_bytes,), dtype=np.uint8, buffer=self.shm.buf
            )
        else:
            self.shm = None
            self.shm_name = None
            self.buffer = np.ndarray((self.total_bytes,), dtype=np.uint8)

        self.arrays = {}
        for name, array in self.offsets.items():
            self.arrays[name] = np.ndarray(
                array["shape"],
                dtype=array["dtype"],
                buffer=self.buffer[array["start"] : array["end"]],
            )
            self.arrays[name][:] = 0

    def getstate(self, gen: int = 0) -> dict:
        """Get the state to use for serialization"""
        state = {
            "gen": gen,
            "use_shm": self.use_shm,
            "offsets": self.offsets,
        }
        if self.use_shm:
            state["shm_name"] = self.shm_name
            state["total_bytes"] = self.total_bytes
        else:
            state["buffer"] = self.buffer
        return state

    @classmethod
    def setstate(cls, state: dict):
        """Set the state and re-create the instance

        This method is invoked only on workers during de-serialization

        """
        instance = cls.__new__(cls)
        instance.is_worker = True
        instance.use_shm = state["use_shm"]

        if instance.use_shm:
            gen = state["gen"]
            instance.shm_name = state["shm_name"]
            if cls._cached_gen < gen:
                if cls._cached_shm is not None:
                    try:
                        cls._cached_shm.close()
                    except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
                        logger.exception("Failed to close cached shm")
                    cls._cached_shm = None
                    cls._cached_buffer = None
                cls._cached_gen = gen
            if cls._cached_shm is None:
                cls._cached_shm = shared_memory.SharedMemory(name=instance.shm_name)
                cls._cached_buffer = np.ndarray(
                    (state["total_bytes"],),
                    dtype=np.uint8,
                    buffer=cls._cached_shm.buf,
                )
            instance.shm = cls._cached_shm
            instance.buffer = cls._cached_buffer
        else:
            instance.shm = None
            instance.shm_name = None
            instance.buffer = state["buffer"]

        instance.arrays = {}
        for name, array in state["offsets"].items():
            instance.arrays[name] = np.ndarray(
                array["shape"],
                dtype=array["dtype"],
                buffer=instance.buffer[array["start"] : array["end"]],
            )

        return instance

    def cleanup(self):
        """Cleanup in case of shm"""
        if self.is_worker:
            # since workers cache the shm, the shm close is handled
            # when the shm changes or implicitly when the worker process quits
            return
        if self.shm is not None:
            try:
                self.shm.close()
            except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
                logger.exception("Failed to close shm")
            if not self.is_worker and sys.platform != "win32":
                try:
                    self.shm.unlink()
                except FileNotFoundError:  # pragma: no cover
                    pass
            self.shm = None
            self.shm_name = None
            self.buffer = None
            self.arrays.clear()

    def __del__(self):
        self.cleanup()


class BufferedTrajectory:
    """Buffered Trajectory

    This class is a wrapper for the trajectory reader and provides
    buffered access to the last n timesteps.

    ``trajectory[index]`` can be used to access individual frames. Index values
    can range from 0 to the configured batch size.

    """

    _gen = 0

    def __init__(
        self,
        trajectory: ReaderBase,
        buffer_size: int,
        reference_ts: Timestep = None,
        use_shm: bool = True,
    ):
        self._trajectory = trajectory
        self._buffer_size = buffer_size
        ts = trajectory.ts
        if reference_ts is not None:
            self._reference_ts = reference_ts
        else:
            self._reference_ts = ts.copy()
        self._use_shm = use_shm

        # _load_ts is used to load timestep info into this buffer
        # _return_ts is used to return the timestep from this buffer
        # A copy is made so the timestep instance is like the initial one
        # Internal attributes point to the items in this buffer during load / return
        self._load_ts = ts.copy()
        self._return_ts = ts.copy()

        # use contiguous arrays to hold arrays within a Timestep for whole buffer size
        unitcell_shape = (self.buffer_size,) + ts._unitcell.shape
        self._arrays = {
            "_steps": {"shape": buffer_size, "dtype": "int64"},
            "_frames": {"shape": buffer_size, "dtype": "int64"},
            "_times": {"shape": buffer_size, "dtype": "float64"},
            "_unitcells": {"shape": unitcell_shape, "dtype": "float32"},
            "_positions": {
                "shape": (buffer_size, trajectory.n_atoms, 3),
                "dtype": "float32",
            },
        }
        if ts.has_velocities:  # pragma: no cover
            self._arrays["_velocities"] = {
                "shape": (buffer_size, trajectory.n_atoms, 3),
                "dtype": "float32",
            }
        if ts.has_forces:  # pragma: no cover
            self._arrays["_forces"] = {
                "shape": (buffer_size, trajectory.n_atoms, 3),
                "dtype": "float32",
            }

        BufferedTrajectory._gen += 1
        self.gen = BufferedTrajectory._gen

        # use MultiArrayBuffer to have all these arrays reside in one common memory block
        self._buffer = MultiArrayBuffer(self._arrays, use_shm=self._use_shm)
        self._create_array_attributes()

        self._data = [{} for _ in range(buffer_size)]
        self._aux = [{} for _ in range(buffer_size)]

        # save initial timestep
        self._save_ts_arrays(ts, 0)
        self._save_ts_metadata(ts, 0)

        self._head = 1 % self._buffer_size
        self._size = min(1, self._buffer_size)

        BufferedTrajectory.next.__doc__ = type(trajectory).next.__doc__

    def cleanup(self):
        """Cleanup the buffer"""
        if self._buffer is not None:
            self._buffer.cleanup()
            self._buffer = None
            for array in self._arrays:
                delattr(self, array)

    def _create_array_attributes(self):
        """Internal: Create array attributes from the spec"""
        for array in self._arrays:
            setattr(self, array, self._buffer.arrays[array])

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_load_ts"]
        del state["_return_ts"]
        del state["_buffer"]
        for array in self._arrays:
            state.pop(array, None)
        state["array_buffer_state"] = self._buffer.getstate(self.gen)
        return state

    def __setstate__(self, state):
        array_buffer_state = state.pop("array_buffer_state")
        self.__dict__.update(state)
        self._buffer = MultiArrayBuffer.setstate(array_buffer_state)
        self._create_array_attributes()
        self._return_ts = self._trajectory.ts

    def _save_ts_arrays(self, ts: Timestep, index: int) -> None:
        """Internal: Copy the positions/velocities/forces arrays into buffer"""
        np.copyto(self._positions[index], ts._pos)
        if ts.has_velocities:  # pragma: no cover
            np.copyto(self._velocities[index], ts._velocities)
        if ts.has_forces:  # pragma: no cover
            np.copyto(self._forces[index], ts._forces)
        np.copyto(self._unitcells[index], ts._unitcell)

    def _save_ts_metadata(self, ts: Timestep, index: int) -> None:
        """Internal: Copy the metadata from the timestep into buffer"""
        self._frames[index] = ts.frame
        self._times[index] = ts.time
        self._steps[index] = ts.data["step"]
        self._data[index] = ts.data.copy()
        self._aux[index] = ts.aux.copy()

    @property
    def reference_ts(self) -> Timestep:
        """Reference timestep

        The earliest timestep available for this trajectory since the dashboard
        was launched. This timestep persists across multiple connect / disconnects
        while the dashboard is running, but not across different runs of the
        dashboard (`mdadash`) itself.

        """
        self._trajectory.ts = self._reference_ts
        return self._trajectory.ts

    @property
    def n_frames(self):
        """Number of frames in the buffer"""
        return self._size

    @property
    def buffer_size(self):
        """Total buffer size"""
        return self._buffer_size

    def __len__(self):
        return self._size

    def check_slice_indices(self, start, stop, step):
        return ProtoReader.check_slice_indices(self, start, stop, step)

    def _apply_limits(self, frame):
        if frame >= self._size:
            frame = -1
        return frame

    def __getitem__(self, index):
        if isinstance(index, numbers.Integral):
            if index < 0:
                index = self._size + index
            if index < 0 or index >= self._size:
                raise IndexError("BufferedTrajectory index out of range")
            buffer_index = (
                index
                if self._size < self._buffer_size
                else (self._head + index) % self._buffer_size
            )
            ts = self._return_ts
            ts.frame = self._frames[buffer_index]
            ts._pos = self._positions[buffer_index]
            if ts.has_velocities:  # pragma: no cover
                ts._velocities = self._velocities[buffer_index]
            if ts.has_forces:  # pragma: no cover
                ts._forces = self._forces[buffer_index]
            ts._unitcell = self._unitcells[buffer_index]
            ts.data = self._data[buffer_index]
            ts.aux = self._aux[buffer_index]
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
        """Iterate next frame and save timestep into buffer"""
        head = self._head
        old_ts = self._trajectory.ts
        ts = self._trajectory.next()
        if ts is not old_ts:  # pragma: no cover
            # only DCDReader and MemoryReader seem to return new
            # timestep instances instead of updating in-place
            self._save_ts_arrays(ts, head)
        self._save_ts_metadata(ts, head)
        self._head = (head + 1) % self._buffer_size
        self._size = min(self._size + 1, self._buffer_size)
        return ts

    def _prepare_for_next(self):
        """
        Prepare for next() to update timestep in-place and not overwrite existing
        buffer contents. This is done outside of next() because iter loop can skip
        over timesteps (if configured) before invoking next()

        """
        head = self._head
        ts = self._load_ts
        ts._pos = self._positions[head]
        if ts.has_velocities:  # pragma: no cover
            ts._velocities = self._velocities[head]
        if ts.has_forces:  # pragma: no cover
            ts._forces = self._forces[head]
        ts._unitcell = self._unitcells[head]
        self._trajectory.ts = ts


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
        self._3dview_count = 0
        self._3dview_frequency = 1
        self._reference_ts = None
        self._n_jobs = 2
        self._parallel_executor = None
        self._parallel_executor_n_jobs = None
        self._patch_IMDReader()
        self._create_parallel_executor()
        self._iter_next_done = asyncio.Event()
        self._iter_next_done.set()
        self._disconnect_cleanup_task = None

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

    @staticmethod
    def _patch_IMDReader():
        """Internal: Patch `IMDReader` to make it serializable"""
        # pylint: disable=import-outside-toplevel, redefined-outer-name, reimported
        from MDAnalysis.coordinates.IMD import IMDReader

        def custom_getstate(self):
            state = self.__dict__.copy()
            del state["_imdclient"]
            return state

        def custom_setstate(self, state):
            self.__dict__.update(state)
            self._imdclient = None

        IMDReader.__setstate__ = custom_setstate
        IMDReader.__getstate__ = custom_getstate

    def update_n_jobs(self, data: dict) -> None:
        """Update n_jobs for ``joblib.Parallel``

        Parameters
        ----------
        data: dict
            Dict that has the following keys:

            n_jobs: int
                The number of parallel jobs

        """
        self._n_jobs = data["n_jobs"]

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
        if self._connected:
            self._comms.send({"status": "error", "message": "Already connected"})
            return
        if not self._wm.parallel_jobs_done.is_set():
            self._wm.notify_parallel_jobs_compelte = True
            self._comms.send(
                {
                    "status": "error",
                    "message": "Parallel jobs are still in progress. "
                    "An alert will be generated once they are complete and "
                    "you can connect to the simulation again after that.",
                }
            )
            return
        try:
            for uid, config in enumerate(universe_configs):
                kwargs = {}
                topology = config["topology"]
                trajectory = config["trajectory"]
                for key, value in config.items():
                    if (
                        key
                        in (
                            "socket_bufsize",
                            "buffer_size",
                            "timeout",
                            "continue_after_disconnect",
                        )
                        and value is not None
                    ):
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
                self._streaming = isinstance(u.trajectory, IMDReader)
                u.trajectory = BufferedTrajectory(
                    u.trajectory,
                    config["batch_size"],
                    self._reference_ts,
                    use_shm=config["shared_memory"],
                )
                if self._reference_ts is None:
                    self._reference_ts = u.trajectory.ts.copy()
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
            # create the 3dview selection AtomGroup
            self._3dview_selection_ag = None
            if self._3dview_selection.strip():
                try:
                    self._3dview_selection_ag = self._universes[0].select_atoms(
                        self._3dview_selection
                    )
                except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
                    logger.exception("Failed to create 3dview selection AtomGroup")
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
            if self._3dview_count % self._3dview_frequency == 0:
                positions = self._3dview_selection_ag.atoms.positions.T.astype(
                    "float32"
                ).tobytes()
                self._comms._comm.send(
                    data={"positions": None},
                    buffers=[positions],
                )
            self._3dview_count += 1

    def _send_sessioninfo(self, u: mda.Universe):
        """Internal: Send session info from imdclient"""
        self._comms.send(
            {"sessioninfo": asdict(u.trajectory._imdclient.get_imdsessioninfo())}
        )

    async def _ensure_iter_loop_cancelled(self, wait=False, run_after=None):
        try:
            if self._iter_loop_task is not None:
                await self._iter_loop_task
        except asyncio.CancelledError:
            self._connected = False
            self._running = False
            self._iter_loop_task = None
        except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
            logger.exception("Exception during iter loop cancellation")
        finally:
            if wait:
                # UI will show disconnect right away (and prevent re-connects) but
                # run the disconnect cleanup task in the background.
                # Tests will wait till everything is cleaned up before continuing
                await self._disconnect_cleanup_task
            if run_after is not None:
                run_after()

    def _disconnect_from_simulations(self, wait=False, run_after=None):
        """Internal: Cancel iteration loop and close trajectories"""
        self._iter_loop_running = False
        if self._iter_loop_task is not None:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._ensure_iter_loop_cancelled(wait=wait, run_after=run_after)
            )
            self._iter_loop_task.cancel()
        else:
            if run_after is not None:
                run_after()

    def disconnect_from_simulations(self, data: dict) -> None:
        """Disconnect from MD simulations"""
        if not self._connected:
            self._comms.send({"status": "error", "message": "Already disconnected"})
            return

        def run_after():
            self._comms.send({"status": "ok"})
            self._comms.send({"disconnect_clients": {}})

        self._disconnect_from_simulations(wait=data["wait"], run_after=run_after)
        self._wm._invoke_lifecycle_method("on_post_disconnect")

    def pause_simulations(self, _data: dict) -> None:
        """Pause MD simulations"""
        if self._connected and self._running:
            self._iter_loop_resumed.clear()
            self._running = False
            self._wm._invoke_lifecycle_method("on_post_pause")
            self._comms.send({"status": "ok"})
            self._comms.send({"pause_clients": {}})
        else:
            self._comms.send({"status": "error", "message": "Not running"})

    def resume_simulations(self, _data: dict) -> None:
        """Resume MD simulations"""
        if self._connected and not self._running:
            self._wm._invoke_lifecycle_method("on_pre_resume")
            self._iter_loop_resumed.set()
            self._running = True
            self._comms.send({"status": "ok"})
        else:
            self._comms.send({"status": "error", "message": "Not paused"})

    def _trajectory_next(self, u: mda.Universe, step: int):
        """Internal: Iterate trajectory by `step` frame(s)"""
        try:
            self._iter_next_done.clear()
            # TODO: Modify this when `imdclient` and `IMDReader` are updated
            #   with support for 'Transmission rate' packet
            # Burn the timesteps until we reach the desired step
            # Don't use next() to avoid unnecessary transformations
            u.trajectory._prepare_for_next()
            while (u.trajectory._frame + 1) % step != 0:
                u.trajectory._read_next_timestep()
            u.trajectory.next()
            return True
        except (OSError, EOFError, StopIteration):
            return False
        finally:
            self._iter_next_done.set()

    def _create_parallel_executor(self):
        if self._parallel_executor is not None:
            self._parallel_executor.__exit__(None, None, None)
        executor = Parallel(
            n_jobs=self._n_jobs,
            max_nbytes=None,
            mmap_mode=None,
            initializer=self._patch_IMDReader,
            # temp_folder=,
        )
        self._parallel_executor = executor.__enter__()  # pylint: disable=unnecessary-dunder-call
        self._parallel_executor_n_jobs = self._n_jobs

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
                        ret = await asyncio.to_thread(
                            self._trajectory_next,
                            u,
                            step,
                        )
                        if not ret:
                            logger.warning(
                                "trajectory.next() failed. "
                                "Simulation likely complete. Disconnecting"
                            )
                            self._disconnect_from_simulations()
                            self._wm._invoke_lifecycle_method("on_post_disconnect")
                            self._comms.send({"disconnect_clients": {}})
                            raise asyncio.CancelledError
                        if uid == 0:
                            self._send_tsdata(u)
                        # run widgets for this timestep
                        batch_ready = (u.trajectory._frame + step) % (
                            step * batch_size
                        ) == 0

                        if self._n_jobs != self._parallel_executor_n_jobs:
                            self._create_parallel_executor()

                        await self._wm.run_widgets(
                            self._parallel_executor, uid, batch_ready
                        )
                    except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
                        logger.exception("Trajectory iteration failed for uid %d", uid)
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            for u in self._universes:
                try:
                    if hasattr(u.trajectory, "_imdclient"):
                        # calling a close() here only seems to decrement the ref count
                        # and not close the underlying connection. The _trajectory_next
                        # thread remains blocked (default imdclient timeout is 600 seconds).
                        # Use the python recommended approach to first shutdown the socket
                        # See: https://docs.python.org/3/library/socket.html#socket.socket.close
                        # TODO: Fix this in imdclient?
                        u.trajectory._imdclient._conn.shutdown(socket.SHUT_RD)
                    u.trajectory.close()
                except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
                    logger.exception("Failed to close trajectory")
            self._disconnect_cleanup_task = asyncio.create_task(
                self._disconnect_cleanup()
            )
            raise

    def _cleanup_buffered_trajectory(self):
        """Internal: Cleanup the buffered trajectory"""
        for i, u in enumerate(self._universes):
            if u is not None:
                u.trajectory.cleanup()
                self._universes[i] = None

    async def _disconnect_cleanup(self):
        """Internal: Cleanup after disconnecting from simulation

        The main iteration loop could have been blocked during trajectory.next()
        or within the WidgetManager's parallel run - because both of them happen
        in a separate thread (asyncio.to_thread). We need to wait till they are
        done to cleanup any shared memory in the buffered trajectory as they will
        be referencing it. Not doing this could lead to hard crashes

        """
        await self._iter_next_done.wait()
        await self._wm.parallel_jobs_done.wait()
        self._cleanup_buffered_trajectory()
        self._3dview_selection_ag = None

    def cleanup(self, _data: dict):
        """Cleanup the UniverseManager

        This is invoked when mdadash is being shutdown. The simulation is disconnected,
        but we don't have to wait till all parallel jobs are done etc because the app
        itself is shutting down

        """

        def run_after():
            # cleanup joblib
            if self._parallel_executor is not None:
                self._parallel_executor.__exit__(None, None, None)
                # TODO: Use temp_folder param to make cleanup easy of joblib's
                # empty joblib_memmapping_folder_* and sem.loky-* leftover files?
            # cleanup universes
            self._cleanup_buffered_trajectory()
            self._comms.send({"status": "ok"})

        self._disconnect_from_simulations(run_after=run_after)

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
        self._3dview_count = 0
        self._comms.send(error)

    def update_3dview_frequency(self, data: dict):
        self._3dview_count = 0
        self._3dview_frequency = data["frequency"]
        self._comms.send({"status": "ok"})


if (
    os.environ.get("MDADASH_KERNEL") == "1"
    and os.environ.get("SETUP_MDADASH_KERNEL") == "1"
):

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
    comms.register_handler(
        "disconnect_from_simulations", um.disconnect_from_simulations
    )
    comms.register_handler("pause_simulations", um.pause_simulations)
    comms.register_handler("resume_simulations", um.resume_simulations)
    comms.register_handler("get_topology", um.get_topology)
    comms.register_handler("update_3dview_selection", um.update_3dview_selection)
    comms.register_handler("update_3dview_frequency", um.update_3dview_frequency)
    comms.register_handler("update_n_jobs", um.update_n_jobs)
    comms.register_handler("cleanup", um.cleanup)
    # for widget manager
    comms.register_handler("widgets:get_available_widgets", wm.get_available_widgets)
    comms.register_handler("widgets:recreate_instances", wm.recreate_instances)
    comms.register_handler("widgets:remove_instance", wm.remove_widget_instance)
    comms.register_handler("widget:get_inputs", wm.get_widget_inputs)
    comms.register_handler("widget:set_input", wm.set_widget_input)
    comms.register_handler("execute_code", wm.execute_code)
    comms.register_handler("widgets:add_instance", wm.add_widget_instance)
    comms.register_handler("widgets:duplicate_instance", wm.duplicate_widget_instance)

    # disable jedi for code complete in macOS python 3.12
    # this times out when used with AsyncKernelManager
    if sys.platform == "darwin" and sys.version == (3, 12):  # pragma: no cover
        IPython.get_ipython().Completer.use_jedi = False

    del os.environ["SETUP_MDADASH_KERNEL"]
