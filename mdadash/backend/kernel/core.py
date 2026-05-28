import comm
import MDAnalysis as mda

u = None  # Universe


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
            raise ValueError("comm is not open yet")

    def _handle_comm_open(self, comm: comm.base_comm.BaseComm, msg):
        """Internal: Handler when the comm is opened (comm_open)"""
        self._comm = comm
        # set the handler for comm messages (comm_msg)
        self._comm.on_msg(self._handle_msg)

    def _handle_msg(self, msg):
        """Internal: Dispatch the message to the registered handler"""
        content_data = msg["content"]["data"]
        msg_type = content_data["msg_type"]
        if msg_type in self._handlers:
            self._handlers[msg_type](content_data["data"])
        else:
            raise ValueError(f"{msg_type} does not have a registered handler")


def connect_to_simulation(config: dict) -> None:
    """Connect to MD simulation

    Parameters
    ----------
    config: dict
        A config dictionary with all params needed for universe creation

    """
    global u
    try:
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
        u = mda.Universe(
            topology,
            trajectory,
            **kwargs,
        )
        comm_handler.send({"status": "connected"})
    except Exception as e:
        comm_handler.send({"status": "error", "message": str(e)})


def disconnect_from_simulation(data: dict) -> None:
    """Disconnect from MD simulation"""
    u.trajectory.close()
    comm_handler.send({"status": "disconnected"})


comm_handler = CommHandler()
comm_handler.register_handler("connect_to_simulation", connect_to_simulation)
comm_handler.register_handler("disconnect_from_simulation", disconnect_from_simulation)
