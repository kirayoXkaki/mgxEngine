#!/usr/bin/env python3
"""Test Supabase PostgreSQL connection.

This script:
1. Reads .env file
2. Tests connection to Supabase database
3. Prints connection status
4. Prints number of rows in tasks table (if exists)
"""
import sys
import os
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError
from app.core.config import settings
# Don't import from app.core.db to avoid creating engine at import time
# from app.core.db import Base
# from app.models import Task, EventLog, AgentRun

def test_connection():
    """Test database connection and print status."""
    print("=" * 60)
    print("Supabase Connection Test")
    print("=" * 60)
    
    # Check if Supabase URL is configured
    if not settings.is_postgresql:
        print("❌ SUPABASE_DB_URL is not set in .env file")
        print("📝 Using SQLite fallback:", settings.database_url)
        print("\nTo use Supabase:")
        print("1. Create a Supabase project at https://app.supabase.com")
        print("2. Go to Settings > Database")
        print("3. Copy the connection string")
        print("4. Add SUPABASE_DB_URL to your .env file")
        return False
    
    print(f"✅ SUPABASE_DB_URL is configured")
    # Hide password in display
    db_url_display = settings.database_url
    if "@" in db_url_display:
        # Show only the part after @ (host:port/database)
        db_url_display = "postgresql+asyncpg://postgres:***@" + db_url_display.split("@")[-1]
    print(f"📊 Database URL: {db_url_display}")
    
    # Validate and fix URL format
    db_url = settings.database_url
    original_url = db_url
    
    print(f"\n🔍 Analyzing URL format...")
    
    # Ensure PostgreSQL URL has a driver specified
    if db_url.startswith("postgresql://") and "+" not in db_url:
        print("⚠️  PostgreSQL URL missing driver, adding psycopg3...")
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        print("✅ Added psycopg3 driver")
    
    # Fix multiple @ symbols (common error)
    at_count = db_url.count("@")
    if at_count > 1:
        print(f"⚠️  Found {at_count} '@' symbols (expected 1), fixing...")
        # Find the last @ which should be before hostname
        last_at = db_url.rfind("@")
        # Everything before last @ is user:pass, everything after is host:port/db
        user_pass_part = db_url[:last_at]
        host_part = db_url[last_at+1:]
        # Reconstruct with single @
        db_url = user_pass_part + "@" + host_part
        print(f"✅ Fixed multiple @ symbols")
    
    # Remove https:// from hostname
    if "@https://" in db_url:
        print("⚠️  Removing 'https://' from hostname...")
        db_url = db_url.replace("@https://", "@")
    
    # Fix password format: if password contains @, it needs to be URL-encoded
    # Parse the URL to extract components
    try:
        parsed = urlparse(db_url)
        if parsed.password and "@" in parsed.password:
            print("⚠️  Password contains '@' symbol, URL-encoding it...")
            # URL-encode the password
            encoded_password = quote(parsed.password, safe='')
            # Reconstruct URL with encoded password
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            db_url = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            print("✅ Password URL-encoded")
        elif ":@" in db_url and db_url.count("@") > 1:
            # Handle case where password format is wrong (:@PASSWORD@)
            print("⚠️  Fixing password format (removing extra ':' before '@')...")
            # Find the position of the last @ (which separates user:pass from host)
            last_at = db_url.rfind("@")
            if last_at > 0:
                # Split into user:pass and host parts
                user_pass_part = db_url[:last_at]
                host_part = db_url[last_at:]
                # Fix :@ in user:pass part
                user_pass_part = user_pass_part.replace(":@", ":", 1)
                db_url = user_pass_part + host_part
                print("✅ Fixed password format")
    except Exception as e:
        print(f"⚠️  Could not parse URL for password encoding: {e}")
        # Fallback: try simple fix
        if ":@" in db_url and db_url.count("@") > 1:
            print("⚠️  Attempting simple password format fix...")
            last_at = db_url.rfind("@")
            if last_at > 0:
                user_pass_part = db_url[:last_at]
                host_part = db_url[last_at:]
                user_pass_part = user_pass_part.replace(":@", ":", 1)
                db_url = user_pass_part + host_part
    
    # Fix hostname: ensure it starts with 'db.' for Supabase
    if "@" in db_url:
        parts = db_url.split("@")
        if len(parts) == 2:
            host_part = parts[1]
            # Extract hostname (before port)
            if ":" in host_part:
                hostname = host_part.split(":")[0]
                port_and_db = host_part.split(":", 1)[1]
            else:
                hostname = host_part
                port_and_db = ""
            
            # Check if hostname is a Supabase hostname
            # Note: Some Supabase projects use direct hostname without 'db.' prefix
            # Test if 'db.' version resolves, if not, try without 'db.'
            if ".supabase.co" in hostname:
                import socket
                # Try with db. prefix first
                db_hostname = "db." + hostname if not hostname.startswith("db.") else hostname
                direct_hostname = hostname.replace("db.", "") if hostname.startswith("db.") else hostname
                
                # Test which one resolves
                db_resolves = False
                direct_resolves = False
                
                try:
                    socket.gethostbyname(db_hostname)
                    db_resolves = True
                except:
                    pass
                
                try:
                    socket.gethostbyname(direct_hostname)
                    direct_resolves = True
                except:
                    pass
                
                if not db_resolves and direct_resolves:
                    print(f"⚠️  'db.{hostname}' doesn't resolve, but '{hostname}' does")
                    print(f"   Using direct hostname (some Supabase projects use this format)")
                    fixed_hostname = direct_hostname
                    # Reconstruct URL
                    if port_and_db:
                        db_url = parts[0] + "@" + fixed_hostname + ":" + port_and_db
                    else:
                        db_url = parts[0] + "@" + fixed_hostname
                    print(f"✅ Using hostname: {fixed_hostname}")
                elif not hostname.startswith("db.") and db_resolves:
                    print("⚠️  Hostname missing 'db.' prefix, fixing...")
                    fixed_hostname = "db." + hostname
                    if port_and_db:
                        db_url = parts[0] + "@" + fixed_hostname + ":" + port_and_db
                    else:
                        db_url = parts[0] + "@" + fixed_hostname
                    print(f"✅ Fixed hostname: {hostname} -> {fixed_hostname}")
    
    if db_url != original_url:
        print(f"\n✅ Corrected URL format")
        print(f"   Original: {original_url[:80]}...")
        print(f"   Fixed:    postgresql+asyncpg://postgres:***@{db_url.split('@')[-1]}")
    
    # Validate URL format
    if "://" not in db_url or "@" not in db_url:
        print("\n❌ Invalid SUPABASE_DB_URL format!")
        print("Expected format: postgresql+asyncpg://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres")
        print(f"Got: {settings.database_url[:100]}")
        print("\n💡 Common issues:")
        print("  - Don't include 'https://' in the hostname")
        print("  - Hostname should be: db.PROJECT.supabase.co (not https://PROJECT.supabase.co)")
        print("  - Port should be: 5432")
        return False
    
    # Update settings to use fixed URL if needed
    # Note: We don't create a new Settings object to avoid importing db.py
    # Just use the fixed db_url directly
    if db_url != settings.database_url:
        print("⚠️  Using corrected URL format")
        # Use the fixed URL directly, don't create new Settings object
        # (Creating Settings would trigger db.py import which might fail)
    
    # Test connection
    try:
        # Use fixed URL if we corrected it
        connection_url = db_url if 'db_url' in locals() else settings.database_url
        
        # For testing, use psycopg (synchronous) instead of asyncpg if asyncpg is in URL
        # This avoids async/await complexity in test script
        if "+asyncpg" in connection_url:
            # Try to use psycopg3 instead for synchronous testing
            # First try psycopg3, fallback to removing driver specifier (uses default)
            try:
                import psycopg
                connection_url_sync = connection_url.replace("+asyncpg", "+psycopg")
                print("💡 Using synchronous driver for testing (psycopg3)")
            except ImportError:
                try:
                    import psycopg2
                    connection_url_sync = connection_url.replace("+asyncpg", "+psycopg2")
                    print("💡 Using synchronous driver for testing (psycopg2)")
                except ImportError:
                    # Remove driver specifier, let SQLAlchemy use default
                    connection_url_sync = connection_url.replace("+asyncpg", "")
                    print("💡 Using default PostgreSQL driver")
        else:
            connection_url_sync = connection_url
        
        # Set connection timeout to avoid hanging
        connect_timeout = 10  # 10 seconds timeout
        engine = create_engine(
            connection_url_sync,
            pool_pre_ping=True,
            connect_args={'connect_timeout': connect_timeout}
        )
        
        print("\n🔌 Testing connection...")
        print(f"   Connecting to: {connection_url_sync.split('@')[-1]}")
        print(f"   Timeout: {connect_timeout} seconds")
        
        # Try to resolve hostname first
        import socket
        if "@" in connection_url_sync:
            hostname = connection_url_sync.split("@")[-1].split(":")[0]
            try:
                print(f"   Resolving hostname: {hostname}...")
                ip = socket.gethostbyname(hostname)
                print(f"   ✅ Hostname resolved: {hostname} -> {ip}")
            except socket.gaierror as e:
                print(f"   ⚠️  DNS resolution failed: {e}")
                print(f"   This might indicate:")
                print(f"     - Hostname is incorrect")
                print(f"     - Network connectivity issues")
                print(f"     - Supabase project might be paused or deleted")
                return False
        
        print(f"   Attempting database connection (this may take up to {connect_timeout}s)...")
        try:
            with engine.connect() as conn:
                print("   ✅ Connection established!")
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                print(f"✅ Connection successful!")
                print(f"📦 PostgreSQL version: {version.split(',')[0]}")
        
                # Check if tables exist
                print("\n📋 Checking database tables...")
                inspector = inspect(engine)
                tables = inspector.get_table_names()
            
                if not tables:
                    print("⚠️  No tables found in database")
                    print("💡 Run the application to auto-create tables")
                else:
                    print(f"✅ Found {len(tables)} table(s): {', '.join(tables)}")
                
                # Count rows in tasks table (using same connection)
                if 'tasks' in tables:
                    result = conn.execute(text("SELECT COUNT(*) FROM tasks"))
                    count = result.scalar()
                    print(f"\n📊 Tasks table: {count} row(s)")
                else:
                    print("\n⚠️  Tasks table does not exist yet")
                    print("💡 Tables will be created automatically when you start the app")
                
                # Check other tables (using same connection)
                if 'event_logs' in tables:
                    result = conn.execute(text("SELECT COUNT(*) FROM event_logs"))
                    count = result.scalar()
                    print(f"📊 EventLogs table: {count} row(s)")
                
                if 'agent_runs' in tables:
                    result = conn.execute(text("SELECT COUNT(*) FROM agent_runs"))
                    count = result.scalar()
                    print(f"📊 AgentRuns table: {count} row(s)")
        
            print("\n" + "=" * 60)
            print("✅ Connection test completed successfully!")
            print("=" * 60)
            return True
        except Exception as conn_error:
            print(f"\n❌ Connection attempt failed: {conn_error}")
            raise
        
    except OperationalError as e:
        print(f"\n❌ Connection failed: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Check your SUPABASE_DB_URL in .env file")
        print("2. Verify your Supabase project is active")
        print("3. Check your network connection")
        print("4. Ensure your IP is allowed in Supabase settings")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

