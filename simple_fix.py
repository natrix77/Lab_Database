import sqlite3

try:
    # Connect to the database
    print("Connecting to database...")
    conn = sqlite3.connect('student_register.db')
    cursor = conn.cursor()
    
    # Define the mapping from old to new values
    mappings = {
        'Άσκηση 1': 'Lab1',
        'Άσκηση 2': 'Lab2',
        'Άσκηση 3': 'Lab3',
        'Ε1': 'Lab1',
        'Ε2': 'Lab2',
        'Ε3': 'Lab3',
        'Ε4': 'Lab4',
        'Ε5': 'Lab5'
    }
    
    # Update Attendance table
    for old_value, new_value in mappings.items():
        cursor.execute(
            'UPDATE Attendance SET exercise_slot = ? WHERE exercise_slot = ?',
            (new_value, old_value)
        )
    
    # Update Grades table
    for old_value, new_value in mappings.items():
        cursor.execute(
            'UPDATE Grades SET exercise_slot = ? WHERE exercise_slot = ?',
            (new_value, old_value)
        )
    
    # Commit the changes and close
    conn.commit()
    print("Database updated successfully!")
    conn.close()
    
except Exception as e:
    print(f"Error: {e}") 