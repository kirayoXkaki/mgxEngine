"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    # Default to SQLite for local development
    # For PostgreSQL, set: DATABASE_URL=postgresql://user:password@localhost/mgx_engine
    database_url: str = "sqlite:///./mgx_engine.db"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    
    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080"
    ]
    
    # Project metadata
    project_name: str = "MGX Engine"
    project_version: str = "1.0.0"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }


settings = Settings()

