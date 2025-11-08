"""Application configuration."""
from pydantic_settings import BaseSettings
from pydantic import computed_field
from typing import Optional
import os
from pathlib import Path

# Load .env file automatically using python-dotenv
from dotenv import load_dotenv

# Load .env file from project root (backend directory)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    # Supabase PostgreSQL connection string (optional)
    # Format: postgresql+asyncpg://postgres:<password>@db.<project>.supabase.co:5432/postgres
    supabase_db_url: Optional[str] = None
    
    # Database URL (auto-determined from SUPABASE_DB_URL or defaults to SQLite)
    # If SUPABASE_DB_URL is set, use it; otherwise fallback to SQLite
    @computed_field
    @property
    def database_url(self) -> str:
        """Get database URL, preferring Supabase if available."""
        if self.supabase_db_url:
            return self.supabase_db_url
        return "sqlite:///./mgx_engine.db"
    
    @computed_field
    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL (Supabase)."""
        return self.supabase_db_url is not None
    
    @computed_field
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite (local fallback)."""
        return not self.is_postgresql
    
    # API Keys
    # OpenAI API key for MetaGPT (if using OpenAI models)
    openai_api_key: Optional[str] = None
    
    # Together AI API key (alternative to OpenAI)
    together_api_key: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # MGX-specific settings
    mgx_test_mode: bool = False  # Enable test mode (simulated workflow without MetaGPT)
    mgx_max_task_duration: int = 600  # Maximum task duration in seconds (10 minutes)
    
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
        "case_sensitive": False,
        "env_file_encoding": "utf-8",
        "extra": "ignore"  # Ignore extra fields from environment (like DATABASE_URL)
    }
    
    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return self.openai_api_key is not None and len(self.openai_api_key.strip()) > 0
    
    @property
    def has_together_key(self) -> bool:
        """Check if Together AI API key is configured."""
        return self.together_api_key is not None and len(self.together_api_key.strip()) > 0
    
    @property
    def has_any_api_key(self) -> bool:
        """Check if any API key is configured."""
        return self.has_openai_key or self.has_together_key


# Global settings instance
settings = Settings()

