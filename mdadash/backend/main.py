import argparse
import copy
import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import Any

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .kernel.manager import KernelManager
from .state.manager import StateManager

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await mdadash.km.start()
    yield
    await mdadash.km.stop()


fastapi = FastAPI(lifespan=lifespan)
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, other_asgi_app=fastapi)
mdadash = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

fastapi.mount(
    "/assets",
    StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
    name="assets",
)


@fastapi.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


@fastapi.get("/favicon.ico")
async def read_favicon():
    return FileResponse(os.path.join(FRONTEND_DIST, "favicon.ico"))


# Note: This catchall should be at the end of all API definitions
@fastapi.get("/{catchall:path}")
async def catch_all():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


class MDADash:
    """MDADash

    The main mdadash server that handles browser socket.io events

    """

    def __init__(self, _sio, state_file):
        self.sio = _sio
        self.sm = StateManager(state_file)
        self.km = KernelManager(self.sm, self.sio)
        self.register_sio_events()

    def register_sio_events(self) -> None:
        """Register socket.io events"""
        self.sio.on("connect")(self.on_connect)
        self.sio.on("disconnect")(self.on_disconnect)
        self.sio.on("connect_to_simulations")(self.on_connect_to_simulations)
        self.sio.on("disconnect_from_simulations")(self.on_disconnect_from_simulations)
        self.sio.on("pause_simulations")(self.on_puase_simulations)
        self.sio.on("resume_simulations")(self.on_resume_simulations)
        self.sio.on("update:settings")(self.on_update_settings)
        self.sio.on("widgets:get_available_widgets")(self.on_get_available_widgets)
        self.sio.on("widgets:update_layout")(self.on_update_layout)
        self.sio.on("widgets:remove_widget")(self.on_remove_widget)
        self.sio.on("widgets:add_widget")(self.on_add_widget)
        self.sio.on("widgets:duplicate_widget")(self.on_duplicate_widget)
        self.sio.on("dashboard:activated")(self.on_dashboard_activated)
        self.sio.on("widget:get_details")(self.on_widget_get_details)
        self.sio.on("widget:name_desc_change")(self.on_widget_name_desc_change)
        self.sio.on("widget:input_change")(self.on_widget_input_change)

    async def emit_running_state(self, sid: Any = None) -> None:
        """Emit current dashboard running state"""
        await self.sio.emit("runningState", self.sm.running_state, to=sid)

    async def emit_settings(self, sid: Any = None) -> None:
        """Emit current settings"""
        await self.sio.emit("settings", self.sm.settings, to=sid)

    async def emit_layout(self, sid: Any = None) -> None:
        """Emit current dashboard layout"""
        await self.sio.emit("widgets:layout", self.sm.widgets_layout, to=sid)

    @asynccontextmanager
    async def _emit_running_states(self):
        """Internal: Handle pending state during running state change"""
        self.sm.running_state["pending"] = True
        self.sm.running_state["message"] = ""
        await self.emit_running_state()
        output = {}
        yield output
        response = output["response"]
        self.sm.running_state["pending"] = False
        if response["status"] != "ok":
            self.sm.running_state["message"] = response["message"]
            logger.error(self.sm.running_state["message"])
        await self.emit_running_state()

    async def on_connect(self, sid, _env):
        """connect handler"""
        await self.emit_running_state(sid)
        await self.km._emit_last_known_values(sid)
        await self.emit_layout(sid)
        await self.emit_settings(sid)

    async def on_disconnect(self, _sid):
        """disconnect handler"""

    async def on_connect_to_simulations(self, _sid):
        """connect_to_simulations handler"""
        async with self._emit_running_states() as output:
            output["response"] = await self.km.connect_to_simulations()
            return output["response"]

    async def on_disconnect_from_simulations(self, _sid):
        """disconnect_from_simulations handler"""
        async with self._emit_running_states() as output:
            output["response"] = await self.km.disconnect_from_simulations()
            return output["response"]

    async def on_puase_simulations(self, _sid):
        """pause_simulations handler"""
        async with self._emit_running_states() as output:
            output["response"] = await self.km.pause_simulations()
            return output["response"]

    async def on_resume_simulations(self, _sid):
        """resume_simulations handler"""
        async with self._emit_running_states() as output:
            output["response"] = await self.km.resume_simulations()
            return output["response"]

    async def on_update_settings(self, _sid, settings):
        """update:settings handler"""
        n_jobs = settings["dashboard_config"]["n_jobs"]
        if self.sm.dashboard_config["n_jobs"] != n_jobs:
            await self.km.update_n_jobs(n_jobs)
        self.sm.settings = copy.deepcopy(settings)
        await self.emit_settings()
        await self.sm.save()

    async def on_get_available_widgets(self, _sid):
        """widgets:get_available_widgets handler"""
        return await self.km.get_available_widgets()

    async def on_update_layout(self, _sid, layout):
        """widgets:update_layout handler"""
        self.sm.widgets_layout[:] = layout
        await self.emit_layout()
        await self.sm.save()
        return self.sm.widgets_layout

    async def on_remove_widget(self, _sid, uuid):
        """widgets:remove_widget handler"""
        response = await self.km.remove_widget_instance(uuid)
        if response["status"] == "ok":
            await self.emit_layout()
        return response

    async def on_add_widget(self, _sid, uid, name, description):
        """widgets:add_widget handler"""
        response = await self.km.add_widget_instance(uid, name, description)
        if response["status"] == "ok":
            await self.emit_layout()
        return response

    async def on_duplicate_widget(self, _sid, uid, uuid, name, description):
        """widgets:duplicate_widget handler"""
        response = await self.km.duplicate_widget_instance(uid, uuid, name, description)
        if response["status"] == "ok":
            await self.emit_layout()
        return response

    async def on_dashboard_activated(self, sid=None):
        """dashboard:activated handler"""
        await self.km._emit_last_known_values(sid)
        await self.emit_layout(sid)

    async def on_widget_get_details(self, _sid, uuid):
        """widget:get_details handler"""
        return await self.km.get_widget_details(uuid)

    async def on_widget_name_desc_change(self, _sid, data):
        """widget:name_desc_change handler"""
        uuid = data["uuid"]
        widget = next((w for w in self.sm.widgets_layout if w["i"] == uuid), None)
        if widget is not None:
            widget["name"] = data["name"]
            widget["description"] = data["description"]
            await self.emit_layout()
            await self.sm.save()
        details = await self.km.get_widget_details(uuid)
        await self.sio.emit("widget:details", details)

    async def on_widget_input_change(self, _sid, data):
        """widget:input_change handler"""
        return await self.km.set_widget_input(
            data["uuid"], data["attribute"], data["value"]
        )


def start_server():
    global mdadash  # pylint: disable=global-statement
    parser = argparse.ArgumentParser(description="Start the MDA Dashboard server")
    parser.add_argument(
        "--topology",
        type=str,
        required=True,
        help="Topology filepath (required)",
    )
    parser.add_argument(
        "--trajectory",
        type=str,
        required=True,
        help="Trajectory URL (of the form 'imd://host:port') (required)",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default="mdadash.state.json",
        help="The dashboard state file (default: mdadash.state.json)",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8000,
        help="Port to run the dashboard server on (default: 8000)",
    )
    parser.add_argument(
        "--dashboard-host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind dashboard server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {version('mdadash')}",
        help="Show the dashboard version and exit",
    )
    # update log level if set
    args = parser.parse_args()
    log_level = getattr(logging, args.log_level.upper(), None)
    logging.getLogger().setLevel(log_level)
    logger.info("State file: %s", args.state_file)
    # create mdadash instance
    mdadash = MDADash(sio, args.state_file)
    # update state with topology and trajectory details (first universe)
    mdadash.sm.universe_configs[0].update(
        {
            "topology": args.topology,
            "trajectory": args.trajectory,
        }
    )
    # start the dashboard server
    uvicorn.run(
        "mdadash.backend.main:app",
        host=args.dashboard_host,
        port=args.dashboard_port,
    )
