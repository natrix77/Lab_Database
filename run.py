"""
Run script for Lab Database application
"""
import os
import sqlite3
from simple_app import app, init_db

if __name__ == "__main__":
    try:
        # Create database if it doesn't exist
        if not os.path.exists('student_register.db'):
            conn = sqlite3.connect('student_register.db')
            conn.close()
            print("Database file created.")
        
        # Initialize the database schema
        init_db()
        print("Database schema initialized.")
        
        # Run the application
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port, debug=True)
    except Exception as e:
        print(f"Error starting application: {e}") 