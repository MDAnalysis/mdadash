import argparse
import copy
import inspect
import json
import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Any

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from MDAnalysis.coordinates.core import get_reader_for

from .analyses.energies import EnergyWidgetBase
from .kernel.manager import KernelManager
from .state.manager import StateManager
from .widgets.base import WidgetBase

logging.basicConfig(level=logging.WARNING)

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


# pylint: disable=too-many-public-methods
class MDADash:
    """MDADash

    The main mdadash server that handles browser socket.io events

    """

    def __init__(self, _sio, state_file, log_level=30):
        self.sio = _sio
        self.sm = StateManager(state_file)
        self.km = KernelManager(self.sm, self.sio, log_level)
        self.register_sio_events()

    def register_sio_events(self) -> None:
        """Register socket.io events"""
        self.sio.on("connect")(self.on_connect)
        self.sio.on("init_data")(self.on_init_data)
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
        self.sio.on("get_alerts")(self.on_get_alerts)
        self.sio.on("delete_alert")(self.on_delete_alert)
        self.sio.on("delete_all_alerts")(self.on_delete_all_alerts)
        self.sio.on("cell_run")(self.on_cell_run)
        self.sio.on("cell_code_complete")(self.on_cell_code_complete)
        self.sio.on("cell_code_inspect")(self.on_cell_code_inspect)
        self.sio.on("notebooks:get_notebooks")(self.on_get_notebooks)
        self.sio.on("notebooks:add_notebook")(self.on_add_notebook)
        self.sio.on("notebooks:remove_notebook")(self.on_remove_notebook)
        self.sio.on("notebooks:duplicate_notebook")(self.on_duplicate_notebook)
        self.sio.on("notebooks:get_notebook")(self.on_get_notebook)
        self.sio.on("notebook:run_on_launch")(self.on_notebook_run_on_launch)
        self.sio.on("notebook:name_desc_change")(self.on_notebook_name_desc_change)
        self.sio.on("notebook:cell_change")(self.on_notebook_cell_change)
        self.sio.on("notebook:update_cells")(self.on_notebook_update_cells)
        self.sio.on("notebooks:get_clonable_widgets")(self.on_get_clonable_widgets)
        self.sio.on("notebooks:clone_widget")(self.on_notebook_clone_widget)
        self.sio.on("load_3dview")(self.on_load_3dview)
        self.sio.on("update_3dview_selection")(self.on_update_3dview_selection)

    async def emit_running_state(self, sid: Any = None) -> None:
        """Emit current dashboard running state"""
        await self.sio.emit("runningState", self.sm.running_state, to=sid)

    async def emit_settings(self, sid: Any = None) -> None:
        """Emit current settings"""
        await self.sio.emit("settings", self.sm.settings, to=sid)

    async def emit_layout(self, sid: Any = None) -> None:
        """Emit current dashboard layout"""
        await self.sio.emit("widgets:layout", self.sm.widgets_layout, to=sid)

    async def emit_alerts_count(self, sid: Any = None) -> None:
        """Emit alerts count"""
        await self.sio.emit("alertsCount", len(self.sm.alerts), to=sid)

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

    async def on_init_data(self, sid):
        """init_data handler"""
        await self.emit_running_state(sid)
        await self.km._emit_last_known_values(sid)
        await self.emit_layout(sid)
        await self.emit_settings(sid)
        await self.emit_alerts_count(sid)

    async def on_disconnect(self, _sid):
        """disconnect handler"""

    async def on_connect_to_simulations(self, _sid):
        """connect_to_simulations handler"""
        async with self._emit_running_states() as output:
            output["response"] = await self.km.connect_to_simulations()
            await self.sio.emit("3dview", await self.on_load_3dview(_sid))
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

    async def on_get_alerts(self, _sid):
        """get_alerts handler"""
        return self.sm.alerts

    async def on_delete_alert(self, _sid, _id):
        """delete_alert handler"""
        self.sm.alerts[:] = [a for a in self.sm.alerts if a["id"] != _id]
        await self.emit_alerts_count()
        await self.sm.save()

    async def on_delete_all_alerts(self, _sid):
        """delete_all_alerts handler"""
        self.sm.alerts.clear()
        await self.emit_alerts_count()
        await self.sm.save()

    async def on_cell_run(self, _sid, data):
        """cell_run handler"""
        cell_data = json.loads(data)
        return await self.km.execute_code(cell_data["code"])

    async def on_cell_code_complete(self, _sid, data):
        """cell_code_complete handler"""
        try:
            response = await self.km.kc.complete(
                code=data["code"],
                cursor_pos=data["cursor_pos"],
                reply=True,
                timeout=2.0,
            )
            return response["content"]  # pragma: no cover
        except TimeoutError:  # pragma: no cover
            return None

    async def on_cell_code_inspect(self, _sid, data):
        """cell_code_inspect handler"""
        try:
            response = await self.km.kc.inspect(
                code=data["code"],
                cursor_pos=data["cursor_pos"],
                detail_level=0,
                reply=True,
                timeout=2.0,
            )
            return response["content"]  # pragma: no cover
        except TimeoutError:  # pragma: no cover
            return None

    async def on_get_notebooks(self, _sid):
        """notebooks:get_notebooks handler"""
        return [
            {
                "uuid": uuid,
                "name": notebook["name"],
                "description": notebook["description"],
                "run_on_launch": notebook["run_on_launch"],
            }
            for uuid, notebook in self.sm.notebooks.items()
        ]

    async def on_add_notebook(self, _sid):
        """notebooks:add_notebook handler"""
        return await self.sm.add_notebook()

    async def on_remove_notebook(self, _sid, uuid):
        """notebooks:remove_notebook handler"""
        return await self.sm.remove_notebook(uuid)

    async def on_duplicate_notebook(self, _sid, uuid):
        """notebooks:duplicate_notebook handler"""
        return await self.sm.duplicate_notebook(uuid)

    async def on_get_notebook(self, _sid, uuid):
        """notebooks:get_notebook handler"""
        return self.sm.notebooks.get(uuid)

    async def on_notebook_run_on_launch(self, _sid, uuid, run_on_launch):
        """notebook:run_on_launch handler"""
        self.sm.notebooks[uuid].update({"run_on_launch": run_on_launch})
        await self.sm.save()

    async def on_notebook_name_desc_change(self, _sid, uuid, name, description):
        """notebook:name_desc_change handler"""
        self.sm.notebooks[uuid].update({"name": name, "description": description})
        await self.sm.save()

    async def on_notebook_cell_change(self, _sid, uuid, _id, code):
        """notebook:cell_change handler"""
        notebook = self.sm.notebooks[uuid]
        cell = next((c for c in notebook["cells"] if c["id"] == _id), None)
        cell["code"] = code
        await self.sm.save()

    async def on_notebook_update_cells(self, _sid, uuid, cells):
        """notebook:update_cells handler"""
        self.sm.notebooks[uuid]["cells"] = cells
        await self.sm.save()

    async def on_get_clonable_widgets(self, _sid):
        """notebooks:get_clonable_widgets handler"""
        widgets = [
            subclass
            for subclass in WidgetBase.__subclasses__()
            if EnergyWidgetBase not in subclass.__mro__
        ]
        return [
            {
                "name": w.name,
                "description": getattr(w, "description", None),
                "class_name": w.__name__,
            }
            for w in sorted(widgets, key=lambda w: w.name.lower())
        ]

    async def on_notebook_clone_widget(self, _sid, name, description, class_name):
        """notebooks:clone_widget handler"""
        widget_class = next(
            (cls for cls in WidgetBase.__subclasses__() if cls.__name__ == class_name),
            None,
        )
        source_file = inspect.getsourcefile(widget_class)
        with open(source_file, "r", encoding="utf-8") as file:  # noqa: ASYNC230
            code = file.read()
        return await self.sm.add_notebook(name, description, code)

    async def on_load_3dview(self, _sid):
        """load_3dview handler"""
        topology = await self.km.get_topology()
        return {
            "inputs": self.sm.view3d,
            "topology": topology,
        }

    async def on_update_3dview_selection(self, _sid, selection):
        """update_3dview_selection handler"""
        self.sm.view3d["selection"] = selection
        response = await self.km.update_3dview_selection(selection)
        if response is not None:
            self.sm.view3d["selection_error"] = response
        await self.sio.emit("3dview", await self.on_load_3dview(_sid))
        await self.sm.save()


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
        help="Trajectory URL or file (Eg: 'imd://host:port' or trajectory.xtc) (required)",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default="mdadash.state.json",
        help="The dashboard state file (default: mdadash.state.json)",
    )
    parser.add_argument(
        "--clear-alerts",
        action="store_true",
        help="Clear alerts if any from dashboard state",
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
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: WARNING)",
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
    mdadash = MDADash(sio, args.state_file, log_level)
    # clear alerts if specified
    if args.clear_alerts:
        mdadash.sm.alerts.clear()
    # update state with topology and trajectory details (first universe)
    mdadash.sm.universe_configs[0].update(
        {
            "topology": args.topology,
            "trajectory": args.trajectory,
        }
    )
    # update total frames if trajectory is a file
    trajectory_path = Path(args.trajectory)
    if trajectory_path.exists():  # pragma: no cover
        try:
            reader = get_reader_for(trajectory_path)
            with reader(trajectory_path) as r:
                mdadash.sm.universe_configs[0].update({"total_frames": r.n_frames})
        except ValueError:  # pragma: no cover
            pass
    # start the dashboard server
    uvicorn.run(
        "mdadash.backend.main:app",
        host=args.dashboard_host,
        port=args.dashboard_port,
    )
