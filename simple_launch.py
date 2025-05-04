"""
Simple launcher for Lab Database web application
Uses only simple_app.py without any other alternatives
"""
import os
import sys
import sqlite3
from pathlib import Path

def print_header(message):
    print(f"\n=== {message} ===\n")

def print_success(message):
    print(f"✓ {message}")

def print_warning(message):
    print(f"! {message}")

def print_error(message):
    print(f"✗ {message}")

def check_database():
    """Check if the database exists and initialize it if needed"""
    print_header("Checking Database")
    
    db_path = Path("student_register.db")
    
    if not db_path.exists():
        print_warning("Database file not found. Creating a new one...")
        try:
            conn = sqlite3.connect(str(db_path))
            conn.close()
            print_success("Database file created")
            
            print_warning("Database will be initialized when the app starts")
            return True
        except Exception as e:
            print_error(f"Failed to create database: {e}")
            return False
    else:
        print_success(f"Database found at: {db_path.absolute()}")
    
    return True

def fix_exercise_slots():
    """Fix exercise slot names in the database"""
    print_header("Fixing Exercise Slot Names")
    
    try:
        conn = sqlite3.connect("student_register.db")
        cursor = conn.cursor()
        
        # Define the mapping from old to new values
        mappings = {
            'Άσκηση 1': 'Lab1',
            'Άσκηση 2': 'Lab2',
            'Άσκηση 3': 'Lab3',
            'Άσκηση 4': 'Lab4',
            'Άσκηση 5': 'Lab5',
            'Ε1': 'Lab1',
            'Ε2': 'Lab2',
            'Ε3': 'Lab3',
            'Ε4': 'Lab4',
            'Ε5': 'Lab5',
            'Ε6': 'Lab6',
            'Ε7': 'Lab7',
            'Ε8': 'Lab8',
            'Ε9': 'Lab9',
            'Ε10': 'Lab10',
            'Ε11': 'Lab11',
            'Ε12': 'Lab12',
            'Ε13': 'Lab13'
        }
        
        # Update Attendance table
        updates = 0
        for old_value, new_value in mappings.items():
            cursor.execute(
                'UPDATE Attendance SET exercise_slot = ? WHERE exercise_slot = ?',
                (new_value, old_value)
            )
            rows_updated = cursor.rowcount
            if rows_updated > 0:
                print_success(f"Updated {rows_updated} records in Attendance: '{old_value}' -> '{new_value}'")
                updates += rows_updated
        
        # Update Grades table
        for old_value, new_value in mappings.items():
            cursor.execute(
                'UPDATE Grades SET exercise_slot = ? WHERE exercise_slot = ?',
                (new_value, old_value)
            )
            rows_updated = cursor.rowcount
            if rows_updated > 0:
                print_success(f"Updated {rows_updated} records in Grades: '{old_value}' -> '{new_value}'")
                updates += rows_updated
        
        # Commit the changes and close
        conn.commit()
        
        if updates > 0:
            print_success(f"Updated a total of {updates} records with standardized exercise slot names")
        else:
            print_success("No records needed to be updated (all names are already standardized)")
            
        conn.close()
        return True
        
    except Exception as e:
        print_error(f"Error fixing exercise slots: {e}")
        return False

def start_application():
    """Start the Flask web application"""
    print_header("Starting Web Application")
    
    # Set Flask environment variables
    os.environ["FLASK_APP"] = "simple_app.py"
    os.environ["FLASK_ENV"] = "development"
    os.environ["FLASK_DEBUG"] = "1"
    
    print_success("Environment variables set")
    print_success("Starting the application using simple_app.py")
    
    try:
        print("\nStarting server...")
        print("The web application will be available at: http://localhost:5000/")
        print("Press CTRL+C to stop the server\n")
        
        # Import the application
        from simple_app import app
        
        # Run the application
        app.run(host="0.0.0.0", port=5000, debug=True)
        
    except KeyboardInterrupt:
        print_warning("\nServer stopped by user")
        return True
    except ImportError as e:
        print_error(f"Failed to import application: {e}")
        return False
    except Exception as e:
        print_error(f"Failed to start application: {e}")
        return False
    
    return True

def main():
    """Main function"""
    print_header("Lab Database Web Application")
    
    print("Using only simple_app.py as requested")
    print(f"Working directory: {os.getcwd()}")
    
    # Check database
    if not check_database():
        print_error("Database check failed. Please fix the issues and try again.")
        return
    
    # Fix exercise slots
    fix_exercise_slots()
    
    # Start the application
    start_application()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")
        print("\nPlease report this error.")
    
    input("\nPress Enter to exit...") 