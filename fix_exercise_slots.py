import sqlite3
import sys

def main():
    try:
        # Connect to the database
        print("Connecting to database...")
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='Attendance' OR name='Grades')")
        tables = cursor.fetchall()
        if not tables:
            print("Tables not found. Please make sure the database is initialized.")
            conn.close()
            return
            
        print(f"Found {len(tables)} relevant tables.")
        
        # Get current exercise slot values
        print("\nChecking current exercise slot values:")
        
        cursor.execute('SELECT DISTINCT exercise_slot FROM Attendance')
        attendance_slots = cursor.fetchall()
        print(f"Attendance slots: {[slot[0] for slot in attendance_slots]}")
        
        cursor.execute('SELECT DISTINCT exercise_slot FROM Grades')
        grades_slots = cursor.fetchall()
        print(f"Grades slots: {[slot[0] for slot in grades_slots]}")
        
        # Define the mapping from old to new values
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
        
        print("\nBeginning database update...")
        
        # Update Attendance table
        for old_value, new_value in mappings.items():
            cursor.execute(
                'UPDATE Attendance SET exercise_slot = ? WHERE exercise_slot = ?',
                (new_value, old_value)
            )
            rows_updated = cursor.rowcount
            if rows_updated > 0:
                print(f"Updated {rows_updated} records in Attendance: '{old_value}' -> '{new_value}'")
        
        # Update Grades table
        for old_value, new_value in mappings.items():
            cursor.execute(
                'UPDATE Grades SET exercise_slot = ? WHERE exercise_slot = ?',
                (new_value, old_value)
            )
            rows_updated = cursor.rowcount
            if rows_updated > 0:
                print(f"Updated {rows_updated} records in Grades: '{old_value}' -> '{new_value}'")
        
        # Commit the changes and close
        conn.commit()
        
        # Verify the changes
        print("\nVerifying updated exercise slot values:")
        
        cursor.execute('SELECT DISTINCT exercise_slot FROM Attendance')
        attendance_slots = cursor.fetchall()
        print(f"Updated Attendance slots: {[slot[0] for slot in attendance_slots]}")
        
        cursor.execute('SELECT DISTINCT exercise_slot FROM Grades')
        grades_slots = cursor.fetchall()
        print(f"Updated Grades slots: {[slot[0] for slot in grades_slots]}")
        
        print("\nDatabase update completed successfully!")
        conn.close()
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")
        
if __name__ == "__main__":
    print("Starting exercise slot name correction script...")
    main()
    print("Done.") 