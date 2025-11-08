# Database Migration Guide: SQLite to Supabase PostgreSQL

This guide explains how to migrate the MGX Engine backend from local SQLite to Supabase-managed PostgreSQL.

## Overview

The backend now supports both:
- **SQLite** (local development, default fallback)
- **Supabase PostgreSQL** (production, recommended)

The system automatically chooses the database based on the `SUPABASE_DB_URL` environment variable.

## Quick Start

### 1. Create a Supabase Project

1. Go to [https://app.supabase.com](https://app.supabase.com)
2. Sign up or log in
3. Click "New Project"
4. Fill in:
   - **Name**: Your project name (e.g., "mgx-engine")
   - **Database Password**: Choose a strong password (save it!)
   - **Region**: Choose closest to your users
5. Wait for project creation (~2 minutes)

### 2. Get Your Connection String

1. In your Supabase project dashboard, go to **Settings** → **Database**
2. Scroll down to **Connection string**
3. Select **URI** tab
4. Copy the connection string (it looks like):
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```

### 3. Update Your `.env` File

Add the connection string to your `.env` file:

```bash
# Use asyncpg driver for better async performance (recommended)
SUPABASE_DB_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres

# Or use standard psycopg2 driver
# SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

**Important Notes:**
- Replace `YOUR_PASSWORD` with your actual database password
- Replace `xxxxx` with your project reference ID
- The `+asyncpg` part enables async PostgreSQL driver (recommended)
- If you don't set `SUPABASE_DB_URL`, the app will use SQLite automatically

### 4. Install PostgreSQL Drivers

Install the required PostgreSQL driver:

```bash
cd backend
pip3 install asyncpg
```

Or if using `psycopg2`:

```bash
pip3 install psycopg[binary]  # For Python 3.13+
# OR
pip3 install psycopg2-binary  # For older Python versions
```

### 5. Test the Connection

Run the connection test script:

```bash
cd backend
python3 scripts/test_supabase_connection.py
```

Expected output:
```
============================================================
Supabase Connection Test
============================================================
✅ SUPABASE_DB_URL is configured
📊 Database URL: postgresql+asyncpg://postgres:***@db...
🔌 Testing connection...
✅ Connection successful!
📦 PostgreSQL version: PostgreSQL 15.x
...
```

### 6. Start the Application

Start the FastAPI server:

```bash
cd backend
python3 -m uvicorn app.main:app --reload
```

You should see:
```
✅ Database connection successful (attempt 1)
✅ Database tables initialized successfully
📊 Using PostgreSQL (Supabase)
```

## Migration Process

### Automatic Table Creation

When you start the app with Supabase, all tables are automatically created:
- `tasks`
- `event_logs`
- `agent_runs`

No manual migration needed! The app uses SQLAlchemy's `create_all()` to set up the schema.

### Data Migration (Optional)

If you have existing data in SQLite and want to migrate it:

1. **Export from SQLite**:
   ```bash
   sqlite3 mgx_engine.db .dump > backup.sql
   ```

2. **Import to Supabase**:
   - Use Supabase SQL Editor or pgAdmin
   - Note: You may need to adjust SQL syntax differences

3. **Or use a migration tool**:
   - [pgloader](https://pgloader.readthedocs.io/) can migrate SQLite to PostgreSQL

## Configuration Details

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_DB_URL` | No | None | Supabase PostgreSQL connection string |
| `DATABASE_URL` | No | Auto | Automatically set based on `SUPABASE_DB_URL` |

### Connection Behavior

- **If `SUPABASE_DB_URL` is set**: Uses Supabase PostgreSQL
- **If `SUPABASE_DB_URL` is not set**: Falls back to SQLite (`sqlite:///./mgx_engine.db`)

### Connection Retry Logic

The app includes automatic retry logic:
- **Max retries**: 3 attempts
- **Retry delay**: 2 seconds between attempts
- **Connection pooling**: Configured for Supabase limits

## Troubleshooting

### Connection Failed

**Error**: `OperationalError: could not connect to server`

**Solutions**:
1. Check your `SUPABASE_DB_URL` in `.env`
2. Verify your Supabase project is active
3. Check network connectivity
4. Ensure your IP is allowed (Supabase allows all by default)

### Password Issues

**Error**: `password authentication failed`

**Solutions**:
1. Verify password in connection string
2. URL-encode special characters in password
3. Reset database password in Supabase dashboard

### Table Creation Issues

**Error**: `relation "tasks" already exists`

**Solutions**:
- Tables already exist (this is fine)
- Or manually drop tables if needed:
  ```sql
  DROP TABLE IF EXISTS agent_runs CASCADE;
  DROP TABLE IF EXISTS event_logs CASCADE;
  DROP TABLE IF EXISTS tasks CASCADE;
  ```

### Driver Not Found

**Error**: `No module named 'asyncpg'`

**Solution**:
```bash
pip3 install asyncpg
```

## Testing

### Run Tests

Tests still work with SQLite (in-memory):

```bash
cd backend
pytest
```

Tests use an in-memory SQLite database for isolation and speed.

### Test Supabase Connection

```bash
cd backend
python3 scripts/test_supabase_connection.py
```

## Production Considerations

### Supabase Free Tier Limits

- **Database size**: 500 MB
- **Connection limit**: 60 connections
- **API requests**: 50,000/month

### Connection Pooling

The app is configured with:
- **Pool size**: 5 connections
- **Max overflow**: 10 connections
- **Pool pre-ping**: Enabled (verifies connections)

### Security

1. **Never commit `.env` files** with real passwords
2. **Use Supabase Row Level Security (RLS)** for production
3. **Rotate database passwords** regularly
4. **Use environment-specific `.env` files**

## Rollback to SQLite

If you need to switch back to SQLite:

1. Remove or comment out `SUPABASE_DB_URL` in `.env`:
   ```bash
   # SUPABASE_DB_URL=...
   ```

2. Restart the application

The app will automatically use SQLite.

## Support

- **Supabase Docs**: [https://supabase.com/docs](https://supabase.com/docs)
- **SQLAlchemy Docs**: [https://docs.sqlalchemy.org](https://docs.sqlalchemy.org)
- **Project Issues**: Check GitHub issues

