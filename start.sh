#!/bin/bash
set -e

# Debugging output
echo "Starting custom entrypoint script"
echo "Current directory: $(pwd)"
echo "Files in current directory: $(ls -la)"

# Force environment variables
export DATABASE_PATH=":memory:"
export PYTHONUNBUFFERED=1
export FLASK_DEBUG=1
export RENDER_DEBUG=1

# Run setup script
echo "Running setup script..."
python setup.py

# Create a temporary patch to fix the issue
echo "Creating temporary app patch..."
cat > patch_app.py << 'EOF'
import sqlite3
import os

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
print("✅ SQLite patched to force in-memory database")

# Set environment variable for good measure
os.environ['DATABASE_PATH'] = ':memory:'
print(f"✅ Set DATABASE_PATH={os.environ.get('DATABASE_PATH')}")
EOF

# Create the custom startup wrapper
echo "Creating application wrapper..."
cat > app_wrapper.py << 'EOF'
# Import the patch first to ensure SQLite is patched
import patch_app

# Then import the actual app
from simple_app_lite import app as application

if __name__ == '__main__':
    application.run()
EOF

# Start gunicorn with the wrapper
echo "Starting gunicorn with patched application..."
exec gunicorn --log-level debug app_wrapper:application 