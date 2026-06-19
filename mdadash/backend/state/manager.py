"""
Manager that manages the dashboard state
"""


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
                "dashboard_config": {
                    "show_session_info": True,
                    "show_energies": True,
                    "ui_request_timeout": 5000,
                },
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
            "widgets_layout": [],
        }

    @property
    def state(self) -> dict:
        """The complete state dict"""
        return self._state

    @property
    def running_state(self) -> dict:
        """The running state dict of the dashboard"""
        return self._state["running_state"]

    @property
    def settings(self) -> dict:
        """The complete settings dict"""
        return self._state["settings"]

    @settings.setter
    def settings(self, value: dict) -> None:
        """Setter for settings"""
        self._state["settings"] = value

    @property
    def universe_configs(self) -> dict:
        """All the unviverse configs dict"""
        return self._state["settings"]["universe_configs"]

    @property
    def widgets_layout(self) -> dict:
        """The widgets layout array of the dashboard"""
        return self._state["widgets_layout"]
