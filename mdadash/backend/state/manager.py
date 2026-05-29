class StateManager:
    """State Manager

    This class is repsonsible for managing the entire state of the dashboard
    application. It persists the state to disk and also restores it back when
    the dashboard server is re-launched.

    The state dictionary has the following keys:
    universe_config:
        An array of universe configurations required to create MDAnalysis
        universes. These include the topology, trajectory, imdclient related
        params and any additional user-defined kwargs setup in the UI

    Attributes
    ----------
    state: dict
        The complete state dictionary

    """

    def __init__(self):
        self._state = {
            "universe_config": [
                {
                    "topology": None,
                    "trajectory": None,
                    "socket_bufsize": None,
                    "buffer_size": 10000000,
                    "timeout": 5,
                    "continue_after_disconnect": None,
                    "kwargs": {},
                },
            ],
        }

    @property
    def state(self):
        return self._state
