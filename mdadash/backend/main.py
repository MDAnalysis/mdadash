import argparse
import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")

app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
    name="assets",
)


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
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (default: false)"
    )
    args = parser.parse_args()
    uvicorn.run(
        "mdadash.backend.main:app", host=args.host, port=args.port, reload=args.reload
    )
