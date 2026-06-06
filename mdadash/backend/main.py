import argparse
import copy
import logging
import os
from contextlib import asynccontextmanager

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
    await km.start()
    yield
    await km.stop()


fastapi = FastAPI(lifespan=lifespan)
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, other_asgi_app=fastapi)

sm = StateManager()
km = KernelManager(sm, sio)

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


@sio.on("connect")
async def connect(_sid, _env):
    await emit_running_state()
    await emit_settings()


@sio.on("disconnect")
async def disconnect(_sid):
    pass


async def emit_running_state():
    await sio.emit("runningState", sm.running_state)


async def emit_settings():
    await sio.emit("settings", sm.settings)


@asynccontextmanager
async def _emit_running_states():
    sm.running_state["pending"] = True
    sm.running_state["message"] = ""
    await emit_running_state()
    output = {}
    yield output
    response = output["response"]
    sm.running_state["pending"] = False
    if response["status"] != "ok":
        sm.running_state["message"] = response["message"]
        logger.error(sm.running_state["message"])
    await emit_running_state()


@sio.on("connect_to_simulations")
async def connect_to_simulations(_sid):
    async with _emit_running_states() as output:
        output["response"] = await km.connect_to_simulations()
        return output["response"]


@sio.on("disconnect_from_simulations")
async def disconnect_from_simulations(_sid):
    async with _emit_running_states() as output:
        output["response"] = await km.disconnect_from_simulations()
        return output["response"]


@sio.on("pause_simulations")
async def puase_simulations(_sid):
    async with _emit_running_states() as output:
        output["response"] = await km.pause_simulations()
        return output["response"]


@sio.on("resume_simulations")
async def resume_simulations(_sid):
    async with _emit_running_states() as output:
        output["response"] = await km.resume_simulations()
        return output["response"]


@sio.on("update:settings")
async def update_settings(_sid, settings):
    sm.settings = copy.deepcopy(settings)
    await emit_settings()


# Note: This catchall should be at the end of all API definitions
@fastapi.get("/{catchall:path}")
async def catch_all():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


def start_server():
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
    # update log level if set
    args = parser.parse_args()
    log_level = getattr(logging, args.log_level.upper(), None)
    logging.getLogger().setLevel(log_level)
    # update state with topology and trajectory details (first universe)
    sm.universe_configs[0].update(
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
