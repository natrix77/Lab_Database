# Tabs/manage_students.py

import sqlite3
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QInputDialog, QMessageBox, QComboBox, QDialog, QDialogButtonBox
from PyQt5.QtCore import Qt

class ManageStudentsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Search Button
        self.search_button = QPushButton("Search for Student")
        self.search_button.clicked.connect(self.search_student)
        
        # Transfer Button
        self.transfer_button = QPushButton("Transfer Student")
        self.transfer_button.clicked.connect(self.transfer_student)
        
        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.search_button)
        layout.addWidget(self.transfer_button)
        self.setLayout(layout)

    def get_existing_semesters_years(self):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT semester, year FROM AcademicYear
            ORDER BY year, semester
        ''')
        results = cursor.fetchall()
        conn.close()
        return results

    def select_or_add_semester_year(self):
        existing_pairs = self.get_existing_semesters_years()
        if existing_pairs:
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Semester and Year")
            layout = QVBoxLayout(dialog)

            combo_box = QComboBox(dialog)
            combo_box.addItem("Add New Semester/Year")
            for semester, year in existing_pairs:
                combo_box.addItem(f"{semester} {year}")
            layout.addWidget(combo_box)

            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            if dialog.exec_() == QDialog.Accepted:
                if combo_box.currentIndex() == 0:
                    semesters = ["ΕΑΡΙΝΟ", "ΧΕΙΜΕΡΙΝΟ"]
                    semester, ok1 = QInputDialog.getItem(self, "Input", "Enter Semester:", semesters, 0, False)
                    year, ok2 = QInputDialog.getInt(self, "Input", "Enter Year:", 2023, 2000, 2100, 1)
                    if not ok1 or not ok2:
                        QMessageBox.warning(self, "Input Error", "Semester and Year are required")
                        return None, None
                    return semester, year
                else:
                    selected = combo_box.currentText().split()
                    return selected[0], int(selected[1])
            else:
                return None, None  # User canceled the dialog
        else:
            semesters = ["ΕΑΡΙΝΟ", "ΧΕΙΜΕΡΙΝΟ"]
            semester, ok1 = QInputDialog.getItem(self, "Input", "Enter Semester:", semesters, 0, False)
            year, ok2 = QInputDialog.getInt(self, "Input", "Enter Year:", 2023, 2000, 2100, 1)
            if not ok1 or not ok2:
                QMessageBox.warning(self, "Input Error", "Semester and Year are required")
                return None, None
            return semester, year

    def get_lab_slots(self, semester, year):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name FROM LabSlots
            INNER JOIN AcademicYear ON LabSlots.academic_year_id = AcademicYear.id
            WHERE AcademicYear.semester = ? AND AcademicYear.year = ?
        ''', (semester, year))
        lab_slots = cursor.fetchall()
        conn.close()
        return [slot[0] for slot in lab_slots]

    def search_student(self):
        # Ask the user for either Student ID or Last Name
        search_term, ok = QInputDialog.getText(self, "Search Student", "Enter Student ID or Last Name:")
        if not ok or not search_term:
            return  # Exit if the user cancels or enters nothing

        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        # Search by Student ID or Last Name
        cursor.execute('''
            SELECT s.student_id, s.name, ls.name AS lab_slot, st.team_number, ay.year, ay.semester
            FROM Students s
            LEFT JOIN Enrollments e ON s.student_id = e.student_id
            LEFT JOIN LabSlots ls ON e.lab_slot_id = ls.id
            LEFT JOIN AcademicYear ay ON e.academic_year_id = ay.id
            LEFT JOIN StudentTeams st ON s.student_id = st.student_id AND e.lab_slot_id = st.lab_slot_id
            WHERE s.student_id = ? OR s.name LIKE ?
            ORDER BY ay.year DESC, ay.semester DESC
            LIMIT 1
        ''', (search_term, f"%{search_term}%"))

        result = cursor.fetchone()
        conn.close()

        if result:
            student_id, name, lab_slot, team_number, year, semester = result
            QMessageBox.information(self, "Student Info", f"Student ID: {student_id}\nName: {name}\nLab Slot: {lab_slot}\nTeam: {team_number}\nYear: {year} ({semester})")
        else:
            QMessageBox.warning(self, "Not Found", "No student found matching the search term.")

    def transfer_student(self):
        # Ask for the Student ID or Last Name to transfer
        student_id, ok = QInputDialog.getText(self, "Transfer Student", "Enter Student ID or Last Name:")
        if not ok or not student_id:
            return

        # Ask for the academic year and semester
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if no selection is made

        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        # Check if the student exists and is currently enrolled
        cursor.execute('''
            SELECT e.lab_slot_id, e.academic_year_id, ls.name
            FROM Enrollments e
            LEFT JOIN LabSlots ls ON e.lab_slot_id = ls.id
            WHERE e.student_id = ? AND e.academic_year_id = (SELECT id FROM AcademicYear WHERE semester = ? AND year = ?)
        ''', (student_id, semester, year))
        current_enrollment = cursor.fetchone()

        if not current_enrollment:
            QMessageBox.warning(self, "Error", "The student is not currently enrolled in this academic year.")
            conn.close()
            return

        current_lab_slot_id, academic_year_id, current_lab_slot = current_enrollment

        # Fetch all available lab slots for the selected academic year
        available_lab_slots = self.get_lab_slots(semester, year)
        if not available_lab_slots:
            QMessageBox.warning(self, "Error", "No available lab slots for the selected academic year.")
            conn.close()
            return

        # Ask for the new lab slot
        new_lab_slot, ok = QInputDialog.getItem(self, "New Lab Slot", "Select new Lab Slot:", available_lab_slots, 0, False)
        if not ok:
            return

        # Update the student's lab slot enrollment
        cursor.execute('''
            UPDATE Enrollments
            SET lab_slot_id = (SELECT id FROM LabSlots WHERE name = ? AND academic_year_id = ?)
            WHERE student_id = ? AND academic_year_id = ?
        ''', (new_lab_slot, academic_year_id, student_id, academic_year_id))

        # Transfer attendance data to the new lab slot
        cursor.execute('''
            UPDATE Attendance
            SET lab_slot_id = (SELECT id FROM LabSlots WHERE name = ? AND academic_year_id = ?)
            WHERE student_id = ? AND academic_year_id = ?
        ''', (new_lab_slot, academic_year_id, student_id, academic_year_id))

        conn.commit()
        conn.close()

        QMessageBox.information(self, "Success", f"Student {student_id} has been transferred from {current_lab_slot} to {new_lab_slot}.")
