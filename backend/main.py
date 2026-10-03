import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import routes, websockets, account
from backend.core import config
from backend.core.database import init_db

app = FastAPI(title="Eno AI Assistant", description="Offline AI Engineering Professor", version="1.0.0")

_wildcard = config.CORS_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # Auth uses Bearer tokens, not cookies, so credentials are only needed for explicit origins.
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")
app.include_router(account.router, prefix="/api")
app.include_router(websockets.router)

public_dir = os.path.abspath(os.path.join(str(config.STORAGE_DIR), "public"))
os.makedirs(public_dir, exist_ok=True)
app.mount("/public", StaticFiles(directory=public_dir), name="public")


@app.on_event("startup")
async def on_startup():
    print(f"ENO starting (mode={config.ENO_MODE}, llm_backend={config.LLM_BACKEND})")
    print("Initializing Database...")
    init_db()

    if not config.LOCAL_STACK_ENABLED:
        print("Cloud mode: skipping Qdrant / Device MCP (local-stack features).")
        return

    from backend.core.qdrant_setup import init_qdrant
    from backend.core.mcp_client import mcp_manager

    init_qdrant()

    print("Connecting to local Device MCP Server...")
    # Get absolute path to device_mcp.py
    device_mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "services", "device_mcp.py"))

    # We must run it with the venv python so it has access to fastmcp
    python_exec = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "venv312", "bin", "python"))
    if not os.path.exists(python_exec):
        python_exec = sys.executable

    await mcp_manager.connect_to_server(
        server_name="device_mcp",
        command=python_exec,
        args=[device_mcp_path]
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "eno-api"}
