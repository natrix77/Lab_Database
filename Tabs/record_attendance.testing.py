import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QDialogButtonBox, QInputDialog, QMessageBox, QRadioButton, QButtonGroup,
    QCheckBox, QComboBox, QFileDialog)
from PyQt5.QtCore import QDateTime, Qt
from PyQt5 import QtGui
import pandas as pd

class RecordAttendanceTab(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.record_attendance_button = QPushButton("Record Attendance")
        self.layout.addWidget(self.record_attendance_button)
        self.record_attendance_button.clicked.connect(self.record_attendance_routine)

        self.show_attendance_button = QPushButton("Show Attendance")
        self.layout.addWidget(self.show_attendance_button)
        self.show_attendance_button.clicked.connect(self.show_attendance)

        self.show_absents_button = QPushButton("Show Absents")
        self.layout.addWidget(self.show_absents_button)
        self.show_absents_button.clicked.connect(self.show_absents)

        self.export_absents_button = QPushButton("Export Absences to Excel")
        self.layout.addWidget(self.export_absents_button)
        self.export_absents_button.clicked.connect(self.export_absents_to_excel)

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

    def record_attendance_routine(self):
        # Implementation of attendance recording
        pass

    def get_students(self, lab_slot_id, academic_year_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        # Check if there are any team assignments for the students in the selected lab slot
        cursor.execute('''
            SELECT COUNT(*)
            FROM StudentTeams st
            INNER JOIN Enrollments e ON st.student_id = e.student_id
            WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
        ''', (lab_slot_id, academic_year_id))
        teams_exist = cursor.fetchone()[0] > 0

        if teams_exist:
            # If teams exist, order by team number first, then student name
            cursor.execute('''
                SELECT s.student_id, s.name, st.team_number
                FROM Students s
                INNER JOIN Enrollments e ON s.student_id = e.student_id
                LEFT JOIN StudentTeams st ON s.student_id = st.student_id
                WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
                ORDER BY st.team_number, s.name
            ''', (lab_slot_id, academic_year_id))
        else:
            # If no teams, order by student name only
            cursor.execute('''
                SELECT s.student_id, s.name, NULL AS team_number
                FROM Students s
                INNER JOIN Enrollments e ON s.student_id = e.student_id
                WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
                ORDER BY s.name
            ''', (lab_slot_id, academic_year_id))

        students = cursor.fetchall()
        conn.close()
        
        return [(student_id, *name.rsplit(' ', 1), team_number) for student_id, name, team_number in students]

    def show_attendance(self):
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if the user canceled the selection

        lab_slots = self.get_lab_slots(semester, year)
        if not lab_slots:
            QMessageBox.warning(self, "No Lab Slots", "No lab slots found for the given semester and year.")
            return

        selected_slots = self.select_lab_slots(lab_slots)
        if not selected_slots:
            QMessageBox.warning(self, "No Slot Selected", "No lab slot selected.")
            return

        selected_slot = selected_slots[0]  # Assuming a single slot selection for simplicity

        exercise_slots = self.select_exercise_slots()
        if not exercise_slots:
            QMessageBox.warning(self, "No Exercise Slot Selected", "No exercise slot selected.")
            return

        # Fetch academic_year_id and lab_slot_id
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM AcademicYear WHERE semester = ? AND year = ?
        ''', (semester, year))
        academic_year_id = cursor.fetchone()[0]

        cursor.execute('''
            SELECT id FROM LabSlots WHERE name = ? AND academic_year_id = ?
        ''', (selected_slot, academic_year_id))
        lab_slot_id = cursor.fetchone()[0]

        # Fetch students
        students = self.get_students(lab_slot_id, academic_year_id)

        if not students:
            QMessageBox.information(self, "No Students", f"No students found for lab slot '{selected_slot}'")
            return

        attendance_data = {}  # Placeholder to represent attendance data

        self.show_attendance_window = QWidget()
        self.show_attendance_window.setWindowTitle(f"Attendance for {selected_slot}")
        layout = QVBoxLayout(self.show_attendance_window)

        columns = ["Last Name", "First Name", "Student ID", "Team"]
        for slot in exercise_slots:
            columns.append(f"{slot} Status")
            columns.append(f"{slot} Timestamp")

        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        for row_idx, (student_id, last_name, first_name, team_number) in enumerate(students):
            table.insertRow(row_idx)
            table.setItem(row_idx, 0, QTableWidgetItem(last_name))
            table.setItem(row_idx, 1, QTableWidgetItem(first_name))
            table.setItem(row_idx, 2, QTableWidgetItem(str(student_id)))
            table.setItem(row_idx, 3, QTableWidgetItem(str(team_number) if team_number is not None else ""))

            col_idx = 4
            for exercise_slot in exercise_slots:
                status, timestamp = attendance_data.get(exercise_slot, {}).get(student_id, ("Absent", ""))
                table.setItem(row_idx, col_idx, QTableWidgetItem(status))
                table.setItem(row_idx, col_idx + 1, QTableWidgetItem(timestamp))
                col_idx += 2

        layout.addWidget(table)
        self.show_attendance_window.setLayout(layout)
        self.show_attendance_window.show()

    def show_absents(self):
        # Implementation for showing absents
        pass

    def export_absents_to_excel(self):
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return

        lab_slots = self.get_lab_slots(semester, year)
        if not lab_slots:
            QMessageBox.warning(self, "No Lab Slots", "No lab slots found for the given semester and year.")
            return

        selected_slots = self.select_lab_slots(lab_slots)
        if not selected_slots:
            QMessageBox.warning(self, "No Slot Selected", "No lab slot selected.")
            return

        exercise_slots = self.select_exercise_slots()
        if not exercise_slots:
            QMessageBox.warning(self, "No Exercise Slot Selected", "No exercise slot selected.")
            return

        absents_data = self.get_absents_data(selected_slots, exercise_slots, semester, year)
        if not absents_data:
            QMessageBox.information(self, "No Absents", "No absents found for the selected slots.")
            return

        # Exporting absents data to Excel
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Absents Excel File", "", "Excel Files (*.xlsx)")
        if save_path:
            if not save_path.endswith('.xlsx'):
                save_path += '.xlsx'

            # Convert absents data to DataFrame
            columns = ["Student Name", "Student ID", "Lab Slot", "Exercise Slot", "Status"]
            df_absents = pd.DataFrame(absents_data, columns=columns)

            # Write to Excel
            with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
                df_absents.to_excel(writer, index=False, sheet_name="Absents")

            QMessageBox.information(self, "Export Success", f"Absents data successfully exported to {save_path}")

    def get_lab_slots(self, semester, year):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT name FROM LabSlots
            INNER JOIN AcademicYear ON LabSlots.academic_year_id = AcademicYear.id
            WHERE AcademicYear.semester = ? AND AcademicYear.year = ?
        ''', (semester, year))
        lab_slots = cursor.fetchall()
        conn.close()
        return lab_slots

    def select_lab_slots(self, lab_slots):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Lab Slot(s)")
        layout = QVBoxLayout(dialog)
        
        self.slot_vars = {}
        
        for slot in lab_slots:
            cb = QCheckBox(slot[0])  # Assuming slot[0] is the label for the slot
            layout.addWidget(cb)
            self.slot_vars[slot[0]] = cb

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            return [slot for slot, cb in self.slot_vars.items() if cb.isChecked()]
        return []

    def select_exercise_slots(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Exercise Slot(s)")
        layout = QVBoxLayout(dialog)
        
        self.exercise_slots = ["Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Replacement1", "Replacement2", "Exam.Jun", "Exam.Sep"]
        self.slot_vars = {}
        
        for slot in self.exercise_slots:
            cb = QCheckBox(slot)
            layout.addWidget(cb)
            self.slot_vars[slot] = cb

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            return [slot for slot, cb in self.slot_vars.items() if cb.isChecked()]
        return []

    def get_absents_data(self, selected_slots, exercise_slots, semester, year):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        data = []

        for lab_slot in selected_slots:
            cursor.execute('''
                SELECT s.name, s.student_id, ls.name as lab_slot, a.exercise_slot, a.status
                FROM Students s
                INNER JOIN Enrollments e ON s.student_id = e.student_id
                INNER JOIN LabSlots ls ON e.lab_slot_id = ls.id
                LEFT JOIN Attendance a ON s.student_id = a.student_id
                WHERE ls.name = ? AND a.status = "Absent" AND a.exercise_slot IN ({seq})
            '''.format(seq=','.join(['?']*len(exercise_slots))),
            (lab_slot, *exercise_slots))

            rows = cursor.fetchall()
            for row in rows:
                data.append(row)

        conn.close()
        return data
