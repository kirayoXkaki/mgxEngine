# Configuration Usage Guide

This document explains how to use the configuration system in the MGX Engine backend.

## Configuration Files

### `.env.example`
Template file showing all available environment variables. Copy this to `.env` and fill in your values.

### `app/core/config.py`
Pydantic Settings class that automatically loads environment variables from `.env` file.

## Environment Variables

### Required (for production)

- **DATABASE_URL**: Database connection string
  - SQLite: `sqlite:///./mgx_engine.db`
  - PostgreSQL: `postgresql://user:password@localhost:5432/mgx_engine`

- **OPENAI_API_KEY** or **TOGETHER_API_KEY**: At least one API key is required for MetaGPT
  - OpenAI: Get from https://platform.openai.com/api-keys
  - Together AI: Get from https://api.together.xyz/

### Optional

- **LOG_LEVEL**: Logging level (default: `INFO`)
  - Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

- **MGX_TEST_MODE**: Enable test mode (default: `false`)
  - Set to `true` to run simulated workflow without MetaGPT

- **MGX_MAX_TASK_DURATION**: Maximum task duration in seconds (default: `600` = 10 minutes)

## Usage in Code

### Import Settings

```python
from app.core.config import settings
```

### Access Configuration Values

```python
# Database URL
db_url = settings.database_url

# API Keys
openai_key = settings.openai_api_key
together_key = settings.together_api_key

# Check if API keys are configured
if settings.has_openai_key:
    print("OpenAI API key is configured")
if settings.has_any_api_key:
    print("At least one API key is configured")

# Logging
log_level = settings.log_level

# MGX settings
test_mode = settings.mgx_test_mode
max_duration = settings.mgx_max_task_duration
```

## Examples

### Example 1: Using in `db.py`

```python
from app.core.config import settings

# Use database URL from config
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False
)
```

### Example 2: Using in `metagpt_runner.py`

```python
from app.core.config import settings

def start_task(self, task_id: str, requirement: str, test_mode: Optional[bool] = None):
    # Use config setting if test_mode not explicitly provided
    if test_mode is None:
        test_mode = settings.mgx_test_mode
    
    # Check API keys
    if not settings.has_any_api_key and not test_mode:
        raise RuntimeError("No API key configured. Set OPENAI_API_KEY or TOGETHER_API_KEY")
```

### Example 3: Using in `main.py`

```python
from app.core.config import settings
import logging

# Configure logging based on settings
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Use API settings
app = FastAPI(
    title=settings.project_name,
    version=settings.project_version
)
```

### Example 4: Setting API Keys for MetaGPT

```python
from app.core.config import settings
import os

# Set OpenAI API key for MetaGPT
if settings.has_openai_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key

# Or set Together AI API key
if settings.has_together_key:
    os.environ["TOGETHER_API_KEY"] = settings.together_api_key
```

## Configuration Loading

The configuration is automatically loaded when the module is imported:

1. `python-dotenv` loads `.env` file from project root
2. Pydantic Settings reads environment variables
3. Default values are used if environment variables are not set

## Priority Order

Configuration values are loaded in this order (highest to lowest priority):

1. Environment variables (from `.env` file or system environment)
2. Default values in `Settings` class

## Testing

For testing, you can override settings:

```python
from app.core.config import settings

# Temporarily override for testing
original_value = settings.mgx_test_mode
settings.mgx_test_mode = True

# ... run tests ...

# Restore original value
settings.mgx_test_mode = original_value
```

Or use environment variables in test setup:

```python
import os
os.environ["MGX_TEST_MODE"] = "true"
```

## Best Practices

1. **Never commit `.env` file**: Add `.env` to `.gitignore`
2. **Use `.env.example`**: Keep it updated with all available variables
3. **Use defaults**: Provide sensible defaults for optional settings
4. **Validate on startup**: Check required settings when application starts
5. **Document defaults**: Document default values in code and docs

## Troubleshooting

### Configuration not loading

- Check that `.env` file exists in `backend/` directory
- Verify `python-dotenv` is installed: `pip install python-dotenv`
- Check file encoding (should be UTF-8)

### API keys not working

- Verify keys are set correctly in `.env`
- Check for extra spaces or quotes
- Use `settings.has_openai_key` to verify key is loaded

### Database connection issues

- Verify `DATABASE_URL` format is correct
- For PostgreSQL, ensure database exists
- Check database credentials

