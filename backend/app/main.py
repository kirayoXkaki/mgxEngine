"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.db import init_db
from app.api import tasks

# Initialize database tables
init_db()

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

