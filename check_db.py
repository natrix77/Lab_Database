import sqlite3

# Connect to the database
conn = sqlite3.connect('student_register.db')
cursor = conn.cursor()

# Show all tables
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
print("=== Tables in database ===")
tables = cursor.fetchall()
for table in tables:
    print(f"- {table[0]}")

# Check the structure of Attendance and Grades tables
print("\n=== Structure of Attendance table ===")
cursor.execute('PRAGMA table_info(Attendance)')
for col in cursor.fetchall():
    print(f"- {col[1]} ({col[2]})")

print("\n=== Structure of Grades table ===")
cursor.execute('PRAGMA table_info(Grades)')
for col in cursor.fetchall():
    print(f"- {col[1]} ({col[2]})")

# Get unique exercise slot values from Attendance and Grades
print("\n=== Unique exercise_slot values in Attendance ===")
cursor.execute('SELECT DISTINCT exercise_slot FROM Attendance')
for row in cursor.fetchall():
    print(f"- '{row[0]}'")

print("\n=== Unique exercise_slot values in Grades ===")
cursor.execute('SELECT DISTINCT exercise_slot FROM Grades')
for row in cursor.fetchall():
    print(f"- '{row[0]}'")

# Close connection
conn.close() 