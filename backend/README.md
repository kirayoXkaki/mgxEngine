# MGX Engine Backend

FastAPI backend for the MGX Engine multi-agent system demo.

## Setup

1. Install dependencies:
```bash
pip3 install -r requirements.txt
# 或者
python3 -m pip install -r requirements.txt
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your database URL and settings
```

3. For SQLite (local development):
```env
DATABASE_URL=sqlite:///./mgx_engine.db
```

4. For PostgreSQL:
```env
DATABASE_URL=postgresql://user:password@localhost/mgx_engine
```

5. Run the application:
```bash
# Development mode
uvicorn app.main:app --reload

# Or use Python directly
python3 -m app.main
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation
- `GET /openapi.json` - OpenAPI schema

### Task Endpoints

- `POST /api/tasks` - Create a new task
- `GET /api/tasks` - List tasks (with pagination)
- `GET /api/tasks/{task_id}` - Get task details
- `PATCH /api/tasks/{task_id}` - Update a task
- `DELETE /api/tasks/{task_id}` - Delete a task

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── tasks.py          # Task REST endpoints
│   ├── core/
│   │   ├── config.py         # Configuration settings
│   │   └── db.py             # Database connection
│   ├── models/
│   │   ├── __init__.py
│   │   └── task.py           # Task ORM model
│   ├── schemas/
│   │   └── task.py           # Pydantic schemas
│   └── main.py               # FastAPI app entry point
├── requirements.txt
├── .env.example
└── README.md
```

## Development

The database tables are automatically created on first run via `init_db()` in `app/core/db.py`.

For production, consider using Alembic for database migrations.

