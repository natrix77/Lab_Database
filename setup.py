import os
import sys
import sqlite3
import stat
import time

def setup_database():
    # Get database path from environment or use default
    db_path = os.environ.get('DATABASE_PATH', 'student_register.db')
    print(f"Setting up database at: {db_path}")
    
    # Create directory if it doesn't exist
    db_dir = os.path.dirname(db_path)
    if db_dir:
        try:
            print(f"Checking if directory exists: {db_dir}")
            if not os.path.exists(db_dir):
                print(f"Creating directory: {db_dir}")
                os.makedirs(db_dir, exist_ok=True)
                # Wait a moment to ensure the directory creation is complete
                time.sleep(1)
                print(f"Created database directory: {db_dir}")
                
            # Check if directory is writable
            if os.access(db_dir, os.W_OK):
                print(f"Directory {db_dir} is writable")
            else:
                print(f"WARNING: Directory {db_dir} is not writable")
                # Try to make it writable
                try:
                    current_permissions = os.stat(db_dir).st_mode
                    os.chmod(db_dir, current_permissions | stat.S_IWUSR | stat.S_IWGRP)
                    print(f"Attempted to make directory writable: {db_dir}")
                except Exception as e:
                    print(f"Failed to update directory permissions: {e}")
        except Exception as e:
            print(f"Error with database directory: {e}")
            return False
    
    # Create empty database file if it doesn't exist
    try:
        if not os.path.exists(db_path):
            print(f"Creating database file: {db_path}")
            open(db_path, 'a').close()
            # Make file writable
            try:
                os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)
                print(f"Set permissions on database file")
            except Exception as e:
                print(f"Failed to set permissions on database file: {e}")
            print(f"Created empty database file: {db_path}")
        else:
            print(f"Database file already exists at: {db_path}")
            # Check if file is writable
            if os.access(db_path, os.W_OK):
                print(f"Database file is writable")
            else:
                print(f"WARNING: Database file is not writable")
                # Try to make it writable
                try:
                    os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP)
                    print(f"Attempted to make database file writable")
                except Exception as e:
                    print(f"Failed to update file permissions: {e}")
        
        # Test if we can connect to the database
        print(f"Testing database connection")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if users table exists
        print(f"Checking if users table exists")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        
        if not result:
            # Create users table
            print(f"Creating users table")
            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0
                )
            ''')
            
            # We'll add the default user in the app
            print("Created users table")
        else:
            print("Users table already exists")
        
        conn.commit()
        conn.close()
        print("Database setup completed successfully")
        return True
    except Exception as e:
        print(f"Error setting up database: {e}")
        # Additional diagnostic information
        try:
            import platform
            print(f"Platform: {platform.platform()}")
            print(f"Python version: {sys.version}")
            print(f"Current directory: {os.getcwd()}")
            print(f"Environment variables:")
            for key, value in os.environ.items():
                if 'PATH' in key or 'DATABASE' in key or 'RENDER' in key:
                    print(f"  {key}: {value}")
        except Exception as diag_error:
            print(f"Error getting diagnostic info: {diag_error}")
        return False

if __name__ == "__main__":
    print("Starting database setup script")
    success = setup_database()
    print(f"Setup completed with {'success' if success else 'errors'}")
    sys.exit(0 if success else 1) 