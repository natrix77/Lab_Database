import os
import sqlite3

def upgrade_database():
    print("Checking database for upgrades...")
    
    # Connect to database
    conn = sqlite3.connect('student_register.db')
    cursor = conn.cursor()
    
    # Check if replenishment_note column exists in Attendance table
    column_exists = False
    try:
        cursor.execute('SELECT replenishment_note FROM Attendance LIMIT 1')
        column_exists = True
        print("Column 'replenishment_note' already exists in Attendance table.")
    except sqlite3.OperationalError:
        column_exists = False
        print("Column 'replenishment_note' does not exist in Attendance table.")
    
    # Add replenishment_note column if it doesn't exist
    if not column_exists:
        try:
            cursor.execute('ALTER TABLE Attendance ADD COLUMN replenishment_note TEXT')
            conn.commit()
            print("Successfully added 'replenishment_note' column to Attendance table.")
        except sqlite3.OperationalError as e:
            print(f"Error adding replenishment_note column: {e}")
    
    conn.close()
    print("Database upgrade completed.")

if __name__ == "__main__":
    upgrade_database() 