import os
import sys
import sqlite3
import stat
import time

def setup_database():
    # Try multiple database locations
    if os.environ.get('RENDER'):
        # For Render.com deployment
        DB_LOCATIONS = [
            os.environ.get('DATABASE_PATH', '/data/student_register.db'),  # Disk mount location
            '/tmp/student_register.db',  # Temp directory (always writable)
            'student_register.db'  # Local to app directory
        ]
    else:
        # For local development
        DB_LOCATIONS = [
            os.environ.get('DATABASE_PATH', 'student_register.db')
        ]
    
    # Try each location until one works
    db_path = None
    for location in DB_LOCATIONS:
        try:
            print(f"Trying database location: {location}")
            db_dir = os.path.dirname(location)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    time.sleep(0.5)  # Brief pause to ensure filesystem sync
                    print(f"Created directory: {db_dir}")
                except Exception as e:
                    print(f"Could not create directory {db_dir}: {e}")
                    continue
            
            # Test if we can write to this location
            try:
                with open(location, 'a') as f:
                    pass
                print(f"Successfully wrote to {location}")
                
                # Location works, use it
                db_path = location
                break
            except Exception as e:
                print(f"Cannot write to {location}: {e}")
                continue
        except Exception as e:
            print(f"Error testing location {location}: {e}")
    
    if not db_path:
        print("ERROR: Could not find a writable database location")
        return False
    
    print(f"Using database at: {db_path}")
    
    # Create users table
    try:
        print(f"Setting up database tables")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if users table exists
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
        
        # Also create a test table to verify write access
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS setup_test (
                id INTEGER PRIMARY KEY,
                timestamp TEXT
            )
        ''')
        
        # Add a test entry
        import datetime
        cursor.execute(
            'INSERT INTO setup_test (timestamp) VALUES (?)',
            [datetime.datetime.now().isoformat()]
        )
        
        conn.commit()
        conn.close()
        print(f"Database setup completed successfully at {db_path}")
        
        # Save the successful path to a file that can be read by the app
        try:
            with open('db_location.txt', 'w') as f:
                f.write(db_path)
            print(f"Saved database location to db_location.txt")
        except Exception as e:
            print(f"Could not save database location: {e}")
        
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