"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Research Agent backend starting up...")
    # Pre-warm ChromaDB directory
    import os
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    yield
    logger.info("Backend shutting down...")


app = FastAPI(
    title="AI Research Agent API",
    description="Multi-agent research report generator with credibility scoring",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "AI Research Agent",
        "version": "1.0.0",
        "docs": "/docs",
    }
