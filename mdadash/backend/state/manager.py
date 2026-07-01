"""
Manager that manages the dashboard state
"""

import asyncio
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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

    dashboard_config: dict
        All the dashboard related config

    universe_configs: dict
        All the universe(s) related config

    widgets_layout: dict
        All the widgets layout info

    widgets: dict
        All the widget instances info

    """

    def __init__(self, state_file: str):
        self._state_file = Path(state_file) if state_file else None
        self._state = None
        self.load()

    def _save(self):
        """Internal: Write state to json file"""
        if self._state_file is not None:
            with open(self._state_file, "w", encoding="utf-8") as file:
                json.dump(self.state, file, indent=4, sort_keys=True)

    async def save(self):
        """Save state"""
        await asyncio.to_thread(self._save)

    def load(self):
        """Load state"""
        running_state = {
            "pending": False,
            "connected": False,
            "running": False,
            "message": "",
        }
        if self._state_file is not None and self._state_file.is_file():
            with open(self._state_file, "r", encoding="utf-8") as file:
                try:
                    state = json.load(file)
                    if "app" in state and state["app"] == "mdadash":
                        self._state = state
                        self._state["running_state"] = running_state.copy()
                        return
                    logger.error("Invalid mdadash state file")
                except json.JSONDecodeError:
                    logger.error("Failed to parse state file '%s'", self._state_file)
        self._state = {
            "version": 1,
            "app": "mdadash",
            "running_state": running_state.copy(),
            "settings": {
                "dashboard_config": {
                    "show_session_info": True,
                    "show_energies": True,
                    "n_jobs": 2,
                    "ui_request_timeout": 5,
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
                        "batch_size": 10,
                        "kwargs": [],
                    },
                ],
            },
            "widgets_layout": [],
            "widgets": {},
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
    def dashboard_config(self) -> dict:
        """Dashboard config dict"""
        return self._state["settings"]["dashboard_config"]

    @property
    def universe_configs(self) -> dict:
        """All the unviverse configs dict"""
        return self._state["settings"]["universe_configs"]

    @property
    def widgets_layout(self) -> dict:
        """The widgets layout array of the dashboard"""
        return self._state["widgets_layout"]

    @property
    def widgets(self) -> dict:
        """The widgets dict of the dashboard"""
        return self._state["widgets"]
