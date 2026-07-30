from fastapi import FastAPI
from backend.api import routes, websockets
from backend.core.database import init_db
from backend.core.qdrant_setup import init_qdrant
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Eno AI Assistant", description="Offline AI Engineering Professor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")
app.include_router(websockets.router)

import os
public_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "public"))
os.makedirs(public_dir, exist_ok=True)
app.mount("/public", StaticFiles(directory=public_dir), name="public")

from backend.core.mcp_client import mcp_manager
import os

@app.on_event("startup")
async def on_startup():
    print("Initializing Database...")
    init_db()
    init_qdrant()
    
    print("Connecting to local Device MCP Server...")
    # Get absolute path to device_mcp.py
    device_mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "device_mcp.py"))
    
    # We must run it with the venv python so it has access to fastmcp
    python_exec = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "venv312", "bin", "python"))
    
    await mcp_manager.connect_to_server(
        server_name="device_mcp",
        command=python_exec,
        args=[device_mcp_path]
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "eno-api"}
