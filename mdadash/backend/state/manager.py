"""
Manager for the dashboard state
"""

import asyncio
import copy
import json
import logging
from pathlib import Path
from uuid import uuid1

logger = logging.getLogger(__name__)


class StateManager:
    """State Manager

    This class is repsonsible for managing the entire state of the dashboard
    application. It persists the state to disk and also restores it back when
    the dashboard server is re-launched.

    The state dictionary has the following keys:

    running_state: dict
        The running state of the dashboard

    settings: dict
        All the values used in the dashboard settings page. This dict has the
        following keys:

        universe_configs:
            An array of universe configurations required to create MDAnalysis
            universes. These include the topology, trajectory, imdclient related
            params and any additional user-defined kwargs setup in the UI

    widgets: dict
        All the details about widget instances

    widgets_layout: list
        The layout details of the widgets on the dashboard GUI

    alertID: int
        The next auto-incrementing ID to use for a new alert

    alerts: list
        List of all the alerts

    notebooks: dict
        All the details about notebooks created

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

    alerts: list
        List of all the alerts

    notebooks: dict
        All the notebooks created

    """

    def __init__(self, state_file: str):
        self._state_file = Path(state_file) if state_file else None
        self._state = None
        self.load()

    def _save(self):
        """Internal: Write state to json file"""
        if self._state_file is not None:
            with open(self._state_file, "w", encoding="utf-8") as file:
                json.dump(self.state, file, indent=4)

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
                    logger.exception(
                        "Failed to parse state file '%s'", self._state_file
                    )
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
                        "nojump": False,
                        "socket_bufsize": None,
                        "buffer_size": 10000000,
                        "timeout": 5,
                        "continue_after_disconnect": None,
                        "step": 1,
                        "total_steps": None,
                        "batch_size": 10,
                        "custom_universe_setup": "",
                        "kwargs": [],
                    },
                ],
            },
            "widgets_layout": [],
            "widgets": {},
            "alertID": 0,
            "alerts": [],
            "notebooks": {},
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
    def widgets_layout(self) -> list:
        """The widgets layout array of the dashboard"""
        return self._state["widgets_layout"]

    @property
    def widgets(self) -> dict:
        """The widgets dict of the dashboard"""
        return self._state["widgets"]

    @property
    def _alertID(self) -> int:
        """Internal: Get current alert ID"""
        if "alertID" not in self._state:
            self._state["alertID"] = 0
        return self._state["alertID"]

    @property
    def alerts(self) -> list:
        """Alerts array"""
        if "alerts" not in self._state:
            self._state["alerts"] = []
        return self._state["alerts"]

    async def add_alert(self, data: dict) -> None:
        """Add alert to alerts array"""
        data["id"] = self._alertID
        self.alerts.append(data)
        self._state["alertID"] += 1
        await self.save()

    @property
    def notebooks(self) -> dict:
        """Notebooks dict"""
        if "notebooks" not in self._state:  # pragma: no cover
            self._state["notebooks"] = {}
        return self._state["notebooks"]

    async def add_notebook(self, name="Untitled", description="", code=""):
        """Add new notebook to notebooks dict"""
        uuid = str(uuid1())
        notebook = {
            "uuid": uuid,
            "name": name,
            "description": description,
            "run_on_launch": False,
            "cells": [
                {
                    "id": str(uuid1()),
                    "code": code,
                },
            ],
        }
        self.notebooks[uuid] = notebook
        await self.save()
        return uuid

    async def duplicate_notebook(self, uuid):
        """Duplicate notebook"""
        new_uuid = str(uuid1())
        new_notebook = copy.deepcopy(self.notebooks[uuid])
        new_notebook["uuid"] = new_uuid
        new_notebook["name"] = f"Copy of {new_notebook['name']}"
        self.notebooks[new_uuid] = new_notebook
        await self.save()
        return new_uuid

    async def remove_notebook(self, uuid):
        """Remove notebook from notebooks dict"""
        del self.notebooks[uuid]
        await self.save()

    @property
    def view3d(self) -> dict:
        """3dview dict"""
        if "3dview" not in self._state:  # pragma: no cover
            self._state["3dview"] = {
                "selection": "",
                "selection_error": "Please enter a selection phrase",
            }
        return self._state["3dview"]
