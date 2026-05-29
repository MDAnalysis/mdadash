import argparse
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .kernel.manager import KernelManager
from .state.manager import StateManager

logging.basicConfig(level=logging.INFO)

sm = StateManager()
km = KernelManager(sm)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await km.start()
    yield
    await km.stop()


app = FastAPI(lifespan=lifespan)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
    name="assets",
)


@app.get("/api/connect/{uid}")
async def connect_to_simulation(uid: int):
    data = {"uid": uid, "config": sm.state["universe_config"][uid]}
    return await km.connect_to_simulation(data)


@app.get("/api/disconnect/{uid}")
async def disconnect_from_simulation(uid: int):
    return await km.disconnect_from_simulation({"uid": uid})


@app.get("/")
async def read_index():
    return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


@app.get("/favicon.ico")
async def read_favicon():
    return FileResponse(os.path.join(FRONTEND_DIST, "favicon.ico"))


@app.get("/{catchall:path}")
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
        "--reload", action="store_true", help="Enable auto-reload (default: false)"
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
    sm.state["universe_config"][0].update(
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
        reload=args.reload,
    )
