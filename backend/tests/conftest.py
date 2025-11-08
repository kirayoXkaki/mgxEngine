"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app import main

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    # FIX: StaticPool ensures all sessions use the same connection
    # isolation_level=None causes issues with transactions, so we remove it
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    # Reset MetaGPT runner instance for clean state
    import app.core.metagpt_runner
    app.core.metagpt_runner._runner_instance = None
    
    # Override database dependency
    main.app.dependency_overrides[get_db] = override_get_db
    
    # FIX: Ensure MetaGPTRunner uses test database session factory
    # This ensures all database operations in MetaGPTRunner use the test session
    # IMPORTANT: For SQLite in-memory, we need to use the same session/connection
    # Return a lambda that returns the test db session to ensure all operations see the same data
    # Note: We'll modify db_utils to not close the session in test mode
    def get_test_db_factory():
        # Return the test db session directly to ensure all operations see the same data
        # Mark it so db_utils knows not to close it
        db._test_session_reuse = True
        return db
    
    # Store original get_metagpt_runner
    original_get_metagpt_runner = app.core.metagpt_runner.get_metagpt_runner
    
    # Create a wrapper that always uses test db
    def get_test_runner():
        # Reset instance to ensure fresh runner with test db
        app.core.metagpt_runner._runner_instance = None
        return original_get_metagpt_runner(db_session_factory=get_test_db_factory)
    
    # Override get_metagpt_runner to use test db
    app.core.metagpt_runner.get_metagpt_runner = get_test_runner
    
    with TestClient(main.app) as test_client:
        yield test_client
    
    # Clean up
    main.app.dependency_overrides.clear()
    app.core.metagpt_runner._runner_instance = None
    # Restore original get_metagpt_runner
    app.core.metagpt_runner.get_metagpt_runner = original_get_metagpt_runner

