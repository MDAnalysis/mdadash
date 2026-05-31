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

    def connect_to_simulation(self, data: dict) -> None:
        """Connect to MD simulation

        Parameters
        ----------
        data: dict
            A data dictionary with all params needed for universe creation.
            This dictionary has the following keys:
            uid: int
                The universe index
            config: dict
                Universe related config like topology, trajectory, imdclient
                params, user-defined kwargs etc


        """
        try:
            uid = data.get("uid", None)
            config = data.get("config", None)
            # TODO: add validations
            kwargs = {}
            topology = config.get("topology")
            trajectory = config.get("trajectory")
            for key, value in config.items():
                if key in ("topology", "trajectory", "kwargs"):
                    continue
                if value is not None:
                    kwargs[key] = value
            for key, value in config["kwargs"].items():
                kwargs[key] = value
            # create universe
            self._universes[uid] = mda.Universe(
                topology,
                trajectory,
                **kwargs,
            )
            comm_handler.send({"status": "connected"})
        except Exception as e:  # pylint: disable=broad-exception-caught
            comm_handler.send({"status": "error", "message": str(e)})

    def disconnect_from_simulation(self, data: dict) -> None:
        """Disconnect from MD simulation"""
        uid = data.get("uid", None)
        # TODO: add validations
        self._universes[uid].trajectory.close()
        comm_handler.send({"status": "disconnected"})


def init_n_universes(data: dict) -> None:
    um.init_n_universes(data.get("n"))


um = UniverseManager()
comm_handler = CommHandler()
comm_handler.register_handler("init_n_universes", init_n_universes)
comm_handler.register_handler("connect_to_simulation", um.connect_to_simulation)
comm_handler.register_handler(
    "disconnect_from_simulation", um.disconnect_from_simulation
)
