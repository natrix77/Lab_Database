"""
This script updates the exercise slot names in the database to maintain consistency.

To run this script:
1. Make sure the student_register.db file is in the same directory as this script
2. Run this script using Python: python fix_database_standalone.py
"""

import sqlite3
import os

def main():
    # Check if database exists
    db_path = 'student_register.db'
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found!")
        return
    
    try:
        # Connect to database
        print(f"Connecting to database '{db_path}'...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Show current values
        print("\nCurrent exercise slot values:")
        try:
            cursor.execute('SELECT DISTINCT exercise_slot FROM Attendance')
            attendance_values = [row[0] for row in cursor.fetchall()]
            print(f"In Attendance table: {attendance_values}")
        except:
            print("Could not read from Attendance table")
            
        try:
            cursor.execute('SELECT DISTINCT exercise_slot FROM Grades')
            grades_values = [row[0] for row in cursor.fetchall()]
            print(f"In Grades table: {grades_values}")
        except:
            print("Could not read from Grades table")
        
        # Exercise slot mappings
        mappings = {
            'Άσκηση 1': 'Lab1',
            'Άσκηση 2': 'Lab2',
            'Άσκηση 3': 'Lab3',
            'Άσκηση 4': 'Lab4',
            'Άσκηση 5': 'Lab5',
            'Άσκηση 6': 'Lab6',
            'Άσκηση 7': 'Lab7',
            'Άσκηση 8': 'Lab8',
            'Άσκηση 9': 'Lab9',
            'Άσκηση 10': 'Lab10',
            'Άσκηση 11': 'Lab11',
            'Άσκηση 12': 'Lab12',
            'Άσκηση 13': 'Lab13',
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
        print("\nUpdating Attendance table...")
        for old_value, new_value in mappings.items():
            try:
                cursor.execute('UPDATE Attendance SET exercise_slot = ? WHERE exercise_slot = ?', 
                             (new_value, old_value))
                if cursor.rowcount > 0:
                    print(f"  Updated {cursor.rowcount} rows: '{old_value}' -> '{new_value}'")
            except Exception as e:
                print(f"  Error updating '{old_value}' in Attendance: {e}")
        
        # Update Grades table
        print("\nUpdating Grades table...")
        for old_value, new_value in mappings.items():
            try:
                cursor.execute('UPDATE Grades SET exercise_slot = ? WHERE exercise_slot = ?', 
                             (new_value, old_value))
                if cursor.rowcount > 0:
                    print(f"  Updated {cursor.rowcount} rows: '{old_value}' -> '{new_value}'")
            except Exception as e:
                print(f"  Error updating '{old_value}' in Grades: {e}")
        
        # Commit changes
        conn.commit()
        print("\nChanges committed to database.")
        
        # Show updated values
        print("\nUpdated exercise slot values:")
        try:
            cursor.execute('SELECT DISTINCT exercise_slot FROM Attendance')
            attendance_values = [row[0] for row in cursor.fetchall()]
            print(f"In Attendance table: {attendance_values}")
        except:
            print("Could not read from Attendance table")
            
        try:
            cursor.execute('SELECT DISTINCT exercise_slot FROM Grades')
            grades_values = [row[0] for row in cursor.fetchall()]
            print(f"In Grades table: {grades_values}")
        except:
            print("Could not read from Grades table")
        
        # Close connection
        conn.close()
        print("\nDatabase connection closed.")
        print("Exercise slot name standardization completed successfully!")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Starting exercise slot name standardization...")
    main()
    print("\nPress Enter to exit...")
    input() 