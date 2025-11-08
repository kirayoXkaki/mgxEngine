# MGX Engine

Multi-agent system demo using MetaGPT framework with frontend-backend separation, real-time event streaming, and task management.

## Project Structure

```
mgxEngine/
├── backend/          # FastAPI backend
│   ├── app/          # Application code
│   ├── tests/        # Test suite
│   └── requirements.txt
└── frontend/          # React frontend (to be implemented)
```

## Quick Start

### Backend Setup

1. Install dependencies:
```bash
cd backend
pip3 install -r requirements.txt
```

2. Set environment variables (optional):
```bash
export DATABASE_URL="sqlite:///./mgx_engine.db"
```

3. Run the server:
```bash
uvicorn app.main:app --reload
```

4. Access API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Running Tests

```bash
cd backend
pytest -v
pytest --cov=app --cov-report=html
```

## Features

- ✅ REST API for task management
- ✅ SQLAlchemy ORM with SQLite/PostgreSQL support
- ✅ Comprehensive test suite (94% coverage)
- ✅ Pydantic validation
- ✅ FastAPI with automatic API documentation

## API Endpoints

- `POST /api/tasks` - Create a new task
- `GET /api/tasks` - List tasks (with pagination)
- `GET /api/tasks/{task_id}` - Get task details
- `PATCH /api/tasks/{task_id}` - Update a task
- `DELETE /api/tasks/{task_id}` - Delete a task

## Documentation

- [Backend Setup Guide](backend/SETUP.md)
- [Implementation Guide](backend/IMPLEMENTATION_GUIDE.md)
- [Backend README](backend/README.md)

## License

MIT

