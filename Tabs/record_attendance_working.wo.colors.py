import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QDialogButtonBox, QInputDialog, QMessageBox, QRadioButton, QButtonGroup, QCheckBox, QComboBox, QFileDialog)
from PyQt5.QtCore import QDateTime, Qt
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

        self.export_absents_button = QPushButton("Export Absences to Excel")
        self.layout.addWidget(self.export_absents_button)
        self.export_absents_button.clicked.connect(self.export_absents_to_excel)

    def get_existing_semesters_years(self):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT semester, year FROM AcademicYear ORDER BY year, semester')
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

        exercise_slot, ok = QInputDialog.getItem(
            self, "Select Exercise Slot", "Select Exercise Slot:", 
            ["Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Replacement1", "Replacement2", "Exam.Jun", "Exam.Sep"], 0, False
        )
        if not ok:
            QMessageBox.warning(self, "No Exercise Slot", "No exercise slot selected.")
            return

        # Fetch academic_year_id and lab_slot_id
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM AcademicYear WHERE semester = ? AND year = ?', (semester, year))
        academic_year_id = cursor.fetchone()[0]

        cursor.execute('SELECT id FROM LabSlots WHERE name = ? AND academic_year_id = ?', (selected_slot, academic_year_id))
        lab_slot_id = cursor.fetchone()[0]

        students = self.get_students(lab_slot_id, academic_year_id)
        if not students:
            QMessageBox.warning(self, "No Students", "No students found for the selected lab slot.")
            return

        # Open attendance recording dialog
        attendance_window = QDialog(self)
        attendance_window.setWindowTitle(f"Record Attendance for {selected_slot} - {exercise_slot}")
        layout = QVBoxLayout(attendance_window)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Student ID", "Last Name", "First Name", "Present", "Absent"])

        button_group = []
        self.attendance_status = []

        for idx, (student_id, last_name, first_name, _) in enumerate(students):
            table.insertRow(idx)
            table.setItem(idx, 0, QTableWidgetItem(str(student_id)))
            table.setItem(idx, 1, QTableWidgetItem(last_name))
            table.setItem(idx, 2, QTableWidgetItem(first_name))

            # Radio buttons for Present and Absent
            present_rb = QRadioButton("Present")
            absent_rb = QRadioButton("Absent")
            group = QButtonGroup(self)
            group.addButton(present_rb)
            group.addButton(absent_rb)
            button_group.append(group)

            table.setCellWidget(idx, 3, present_rb)
            table.setCellWidget(idx, 4, absent_rb)
            
            # Add default absent status if none selected
            absent_rb.setChecked(True)
            self.attendance_status.append((student_id, "Absent"))

            # Connect the status change
            present_rb.toggled.connect(lambda checked, row=idx: self.update_attendance_status(row, "Present"))
            absent_rb.toggled.connect(lambda checked, row=idx: self.update_attendance_status(row, "Absent"))

        layout.addWidget(table)

        # Save button to confirm attendance
        save_button = QPushButton("Save Attendance")
        save_button.clicked.connect(lambda: self.save_attendance(exercise_slot, lab_slot_id, academic_year_id))
        layout.addWidget(save_button)

        attendance_window.setLayout(layout)
        attendance_window.exec_()

    def update_attendance_status(self, row, status):
        student_id = self.attendance_status[row][0]
        self.attendance_status[row] = (student_id, status)

    def save_attendance(self, exercise_slot, lab_slot_id, academic_year_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        for student_id, status in self.attendance_status:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            cursor.execute('''
                INSERT OR REPLACE INTO Attendance (student_id, lab_slot_id, academic_year_id, exercise_slot, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, lab_slot_id, academic_year_id, exercise_slot, status, timestamp))

        conn.commit()
        conn.close()
        QMessageBox.information(self, "Attendance Recorded", "Attendance has been successfully recorded.")

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
        cursor.execute('SELECT id FROM AcademicYear WHERE semester = ? AND year = ?', (semester, year))
        academic_year_id = cursor.fetchone()[0]

        cursor.execute('SELECT id FROM LabSlots WHERE name = ? AND academic_year_id = ?', (selected_slot, academic_year_id))
        lab_slot_id = cursor.fetchone()[0]

        # Fetch attendance records
        attendance_records = []
        for exercise_slot in exercise_slots:
            cursor.execute('''
                SELECT s.name, a.status, a.timestamp
                FROM Attendance a
                JOIN Students s ON a.student_id = s.student_id
                WHERE a.lab_slot_id = ? AND a.academic_year_id = ? AND a.exercise_slot = ?
            ''', (lab_slot_id, academic_year_id, exercise_slot))
            attendance_records.extend(cursor.fetchall())

        conn.close()

        # Display attendance records in a table
        attendance_window = QDialog(self)
        attendance_window.setWindowTitle(f"Attendance for {selected_slot}")
        layout = QVBoxLayout(attendance_window)

        columns = ["Student Name", "Status", "Timestamp"]
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        for row_idx, (name, status, timestamp) in enumerate(attendance_records):
            table.insertRow(row_idx)
            table.setItem(row_idx, 0, QTableWidgetItem(name))
            table.setItem(row_idx, 1, QTableWidgetItem(status))
            table.setItem(row_idx, 2, QTableWidgetItem(timestamp))

        layout.addWidget(table)
        attendance_window.setLayout(layout)
        attendance_window.exec_()

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

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Absents Excel File", "", "Excel Files (*.xlsx)")
        if save_path:
            if not save_path.endswith('.xlsx'):
                save_path += '.xlsx'

            columns = ["Student Name", "Student ID", "Lab Slot", "Exercise Slot", "Status"]
            df_absents = pd.DataFrame(absents_data, columns=columns)

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
        return [slot[0] for slot in lab_slots]

    def select_lab_slots(self, lab_slots):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Lab Slot(s)")
        layout = QVBoxLayout(dialog)
        
        self.slot_vars = {}
        
        for slot in lab_slots:
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
