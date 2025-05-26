import os
import sys
import sqlite3

def setup_database():
    # Get database path from environment or use default
    db_path = os.environ.get('DATABASE_PATH', 'student_register.db')
    print(f"Setting up database at: {db_path}")
    
    # Create directory if it doesn't exist
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            print(f"Created database directory: {db_dir}")
        except Exception as e:
            print(f"Error creating database directory: {e}")
            return False
    
    # Create empty database file if it doesn't exist
    try:
        if not os.path.exists(db_path):
            open(db_path, 'a').close()
            print(f"Created empty database file: {db_path}")
        
        # Create users table
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        
        if not result:
            # Create users table
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
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting up database: {e}")
        return False

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1) 