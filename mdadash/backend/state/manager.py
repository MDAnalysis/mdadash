class StateManager:
    """State Manager

    This class is repsonsible for managing the entire state of the dashboard
    application. It persists the state to disk and also restores it back when
    the dashboard server is re-launched.

    The state dictionary has the following keys:

    running_state:
        The running state of the dashboard

    settings:
        All the values used in the dashboard settings page. This dict has the
        following keys:

        universe_configs:
            An array of universe configurations required to create MDAnalysis
            universes. These include the topology, trajectory, imdclient related
            params and any additional user-defined kwargs setup in the UI

    Attributes
    ----------
    state: dict
        The complete state dictionary

    running_state: dict
        The running state of the dashboard

    settings: dict
        All the values used in the dashboard settings page

    universe_configs: dict
        All the universe(s) related config

    """

    def __init__(self):
        self._state = {
            "running_state": {
                "pending": False,
                "connected": False,
                "running": False,
                "message": "",
            },
            "settings": {
                "universe_configs": [
                    {
                        "topology": None,
                        "trajectory": None,
                        "socket_bufsize": None,
                        "buffer_size": 10000000,
                        "timeout": 5,
                        "continue_after_disconnect": None,
                        "step": 1,
                        "total_steps": None,
                        "kwargs": [],
                    },
                ],
            },
        }

    @property
    def state(self):
        return self._state

    @property
    def running_state(self):
        return self._state["running_state"]

    @property
    def settings(self):
        return self._state["settings"]

    @settings.setter
    def settings(self, value):
        self._state["settings"] = value

    @property
    def universe_configs(self):
        return self._state["settings"]["universe_configs"]
