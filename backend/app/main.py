"""FastAPI application entry point."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import init_db
from app.api import tasks, websocket

# Configure logging based on settings
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database tables
init_db()

# Log configuration status
logger.info(f"Starting {settings.project_name} v{settings.project_version}")
if settings.is_postgresql:
    # Hide password in logs
    db_url_display = settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url
    logger.info(f"Database: PostgreSQL (Supabase) - {db_url_display}")
else:
    logger.info(f"Database: SQLite - {settings.database_url}")
logger.info(f"Log level: {settings.log_level}")
logger.info(f"Test mode: {settings.mgx_test_mode}")
if settings.has_openai_key:
    logger.info("OpenAI API key: configured")
if settings.has_together_key:
    logger.info("Together AI API key: configured")
if not settings.has_any_api_key:
    logger.warning("No API keys configured. MetaGPT will run in test mode.")

# Create FastAPI app
app = FastAPI(
    title=settings.project_name,
    description="Multi-agent system demo using MetaGPT",
    version=settings.project_version
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tasks.router)
app.include_router(websocket.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "MGX Engine API",
        "version": settings.project_version,
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload
    )

