class StateManager:
    """State Manager

    This class is repsonsible for managing the entire state of the dashboard
    application. It persists the state to disk and also restores it back when
    the dashboard server is re-launched.

    Attributes
    ----------
    state: dict
        The complete state dictionary

    """

    def __init__(self):
        self._state = {
            "universe_config": {
                "topology": None,
                "trajectory": None,
                "socket_bufsize": None,
                "buffer_size": 10000000,
                "timeout": 5,
                "continue_after_disconnect": None,
                "kwargs": {},
            },
        }

    @property
    def state(self):
        return self._state
