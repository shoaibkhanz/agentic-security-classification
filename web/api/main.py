"""
FastAPI application for the securities classification UI.

Run with:
    cd pydantic-ai/web && uv run uvicorn api.main:app --reload --port 8000

The Next.js frontend proxies /api/* to this server,
so no CORS configuration is needed in development.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.api.routes import router


# Ensure the project root is on the Python path so capstone/ and shared/
# imports resolve when running from the web/ directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    # Ensure the data directory exists
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Securities Classification API",
    description="AI-powered private securities classification with live streaming",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for development (in production, Next.js proxy handles this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
