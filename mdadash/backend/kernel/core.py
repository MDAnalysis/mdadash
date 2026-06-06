import asyncio

import comm
import MDAnalysis as mda


class CommHandler:
    """Comm Handler

    This class is responsible for handling all the communication to and from
    this kernel. This is the class that interfaces with the KernelManager on
    the server side.

    """

    def __init__(self):
        self._comm = None
        self._handlers = {}
        comm.get_comm_manager().register_target(
            "kernel_comm_handler", self._handle_comm_open
        )

    def register_handler(self, msg_type: str, handler_func: callable) -> None:
        """Register a handler function for a message type"""
        self._handlers[msg_type] = handler_func

    def send(self, msg: dict) -> None:
        """Send a message (response) back on the comm

        Parameters
        ----------
        msg: dict
            A message dictionary

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

    def __init__(self):
        self._universes = []
        self._iter_loop_task = None
        self._iter_loop_running = False
        self._iter_loop_resumed = asyncio.Event()
        self._iter_loop_resumed.clear()

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

    def connect_to_simulations(self, universe_configs: list[dict]) -> None:
        """Connect to MD simulations

        Parameters
        ----------
        universe_configs: list[dict]
            A list of configurations for universe(s) creation.
            Each dict has universe related config like topology, trajectory,
            imdclient params, user-defined kwargs etc

        """
        try:
            for uid, config in enumerate(universe_configs):
                kwargs = {}
                topology = config.get("topology")
                trajectory = config.get("trajectory")
                for key, value in config.items():
                    if key in ("topology", "trajectory", "kwargs"):
                        continue
                    if value is not None:
                        kwargs[key] = value
                for name, value in config["kwargs"]:
                    if name.strip():
                        kwargs[name] = value
                # create universe
                u = mda.Universe(
                    topology,
                    trajectory,
                    **kwargs,
                )
                if uid == 0:
                    self._send_tsdata(u)
                self._universes[uid] = u
            # start iter loop for trajectories
            self._iter_loop_resumed.clear()
            self._iter_loop_running = True
            self._iter_loop_task = asyncio.create_task(self._iter_loop())
            comm_handler.send({"status": "ok"})
        except Exception as e:  # pylint: disable=broad-exception-caught
            comm_handler.send({"status": "error", "message": str(e)})

    def _send_tsdata(self, u: mda.Universe):
        """Internal: Send timestep data out"""
        comm_handler.send(
            {
                "tsinfo": {
                    "frame": u.trajectory.frame,
                    "tsdata": u.trajectory.ts.data,
                }
            }
        )

    def disconnect_from_simulations(self, _data: dict) -> None:
        """Disconnect from MD simulations"""
        self._iter_loop_running = False
        self._iter_loop_task.cancel()
        for u in self._universes:
            u.trajectory.close()
        comm_handler.send({"status": "ok"})

    def pause_simulations(self, _data: dict) -> None:
        """Pause MD simulations"""
        self._iter_loop_resumed.clear()
        comm_handler.send({"status": "ok"})

    def resume_simulations(self, _data: dict) -> None:
        """Resume MD simulations"""
        self._iter_loop_resumed.set()
        comm_handler.send({"status": "ok"})

    def _trajectory_next(self, u):
        """Internal: Iterate trajectory by 1 frame"""
        return u.trajectory.next()

    async def _iter_loop(self):
        """Internal: Iteration loop for trajectories"""
        try:
            while self._iter_loop_running:
                await self._iter_loop_resumed.wait()
                for uid, u in enumerate(self._universes):
                    try:
                        # iterate in thread to not block on a network call here
                        await asyncio.to_thread(self._trajectory_next, u)
                        if uid == 0:
                            self._send_tsdata(u)
                        # await asyncio.sleep(0)
                    except StopIteration as e:  # pragma: no cover
                        print(e)
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass


def init_n_universes(data: dict) -> None:
    um.init_n_universes(data.get("n"))


um = UniverseManager()
comm_handler = CommHandler()
comm_handler.register_handler("init_n_universes", init_n_universes)
comm_handler.register_handler("connect_to_simulations", um.connect_to_simulations)
comm_handler.register_handler(
    "disconnect_from_simulations", um.disconnect_from_simulations
)
comm_handler.register_handler("pause_simulations", um.pause_simulations)
comm_handler.register_handler("resume_simulations", um.resume_simulations)
