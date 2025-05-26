import os
import sqlite3
import sys

print("WSGI initializing...")

# Keep track of DB connection counts
_db_connections = 0

# Monkey patch sqlite3.connect to log and redirect
original_connect = sqlite3.connect
def patched_connect(database, *args, **kwargs):
    global _db_connections
    _db_connections += 1
    
    # Force in-memory database regardless of input
    if database != ':memory:' and isinstance(database, str):
        print(f"⚠️ Intercepted DB connection to '{database}', redirecting to in-memory DB (connection #{_db_connections})")
        database = ':memory:'
    
    return original_connect(database, *args, **kwargs)

# Apply the monkey patch
sqlite3.connect = patched_connect
print("SQLite patched to force in-memory database")

# Set environment variable for good measure
os.environ['DATABASE_PATH'] = ':memory:'
print(f"Set DATABASE_PATH={os.environ.get('DATABASE_PATH')}")

# Print debug info
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in current directory: {os.listdir('.')}")

# Now import the application
from simple_app_lite import app as application

# Test database connection
with application.app_context():
    try:
        import sqlite3
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)')
        cursor.execute('INSERT INTO test VALUES (1)')
        conn.commit()
        print("Test database connection successful")
    except Exception as e:
        print(f"Test database connection failed: {e}")

print("WSGI initialization complete")

if __name__ == '__main__':
    application.run() 