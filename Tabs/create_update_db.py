# Tabs/create_update_db.py

import sqlite3
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QMessageBox

class CreateUpdateDBTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.create_db_button = QPushButton("Create or Update Database")
        self.create_db_button.clicked.connect(self.create_update_db)
        layout = QVBoxLayout()
        layout.addWidget(self.create_db_button)
        self.setLayout(layout)

    def create_update_db(self):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        # Create AcademicYear table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS AcademicYear (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester TEXT,
                year INTEGER
            )
        ''')

        # Create LabSlots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS LabSlots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                academic_year_id INTEGER,
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create Students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Students (
                student_id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                registration_number TEXT,
                username TEXT
            )
        ''')

        # Create Enrollments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_slot_id INTEGER,
                academic_year_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create StudentTeams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS StudentTeams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_number INTEGER,
                student_id TEXT,
                lab_slot_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id)
            )
        ''')

        # Create Attendance table with lab_slot_id column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_slot_id INTEGER,
                exercise_slot TEXT,
                status TEXT,
                timestamp TEXT,
                academic_year_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create Grades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_slot_id INTEGER,
                exercise_slot TEXT,
                grade REAL,
                timestamp TEXT,
                academic_year_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create FinalGrades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS FinalGrades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_average REAL,
                jun_exam_grade REAL,
                sep_exam_grade REAL,
                final_grade REAL,
                academic_year_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", "Database created or updated successfully.")
