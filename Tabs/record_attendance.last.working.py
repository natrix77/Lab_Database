import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QDialogButtonBox, QInputDialog, QMessageBox, QRadioButton, QButtonGroup,
    QCheckBox, QComboBox)
from PyQt5.QtCore import QDateTime, Qt
from PyQt5 import QtGui

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

        exercise_slot, ok = QInputDialog.getItem(self, "Select Exercise Slot", "Select Exercise Slot:", 
                                                 ["Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Replacement1", "Replacement2", "Exam.Jun", "Exam.Sep"], 0, False)
        if not ok:
            QMessageBox.warning(self, "No Exercise Slot", "No exercise slot selected.")
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
        conn.close()

        attendance_exists = self.check_existing_attendance(lab_slot_id, exercise_slot, academic_year_id)

        students = self.get_students(lab_slot_id, academic_year_id)
        if not students:
            QMessageBox.warning(self, "No Students", "No students found for the selected lab slot.")
            return

        attendance_window = QDialog(self)
        attendance_window.setWindowTitle(f"Record Attendance for {selected_slot} - {exercise_slot}")
        layout = QVBoxLayout(attendance_window)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["#", "Last Name", "First Name", "Present", "Absent", "Timestamp"])

        button_group = []
        self.original_data = []

        def on_status_change(row, status):
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            table.setItem(row, 5, QTableWidgetItem(timestamp))

        for idx, (student_id, last_name, first_name) in enumerate(students):
            table.insertRow(idx)
            table.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            table.setItem(idx, 1, QTableWidgetItem(last_name))
            table.setItem(idx, 2, QTableWidgetItem(first_name))

            present_rb = QRadioButton("Present")
            absent_rb = QRadioButton("Absent")
            group = QButtonGroup(self)
            group.addButton(present_rb)
            group.addButton(absent_rb)
            button_group.append(group)
            table.setCellWidget(idx, 3, present_rb)
            table.setCellWidget(idx, 4, absent_rb)

            self.original_data.append((student_id, present_rb.isChecked(), absent_rb.isChecked()))

            if attendance_exists:
                status, timestamp = self.get_student_attendance(student_id, lab_slot_id, exercise_slot, academic_year_id)
                if status == "Present":
                    present_rb.setChecked(True)
                elif status == "Absent":
                    absent_rb.setChecked(True)
                table.setItem(idx, 5, QTableWidgetItem(timestamp))
                present_rb.setEnabled(False)
                absent_rb.setEnabled(False)

            present_rb.toggled.connect(lambda checked, r=idx: on_status_change(r, "Present"))
            absent_rb.toggled.connect(lambda checked, r=idx: on_status_change(r, "Absent"))

        layout.addWidget(table)

        self.change_button = QPushButton("Make changes?")
        self.change_button.setEnabled(attendance_exists)
        self.change_button.clicked.connect(lambda: self.toggle_editing(button_group))
        layout.addWidget(self.change_button)

        self.complete_button = QPushButton("Save Attendance")
        self.complete_button.clicked.connect(lambda: self.save_attendance(button_group, students, exercise_slot, lab_slot_id, academic_year_id))
        self.complete_button.setEnabled(not attendance_exists)
        layout.addWidget(self.complete_button)

        attendance_window.setLayout(layout)
        attendance_window.exec_()

    def get_students(self, lab_slot_id, academic_year_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.student_id, s.name
            FROM Students s
            INNER JOIN Enrollments e ON s.student_id = e.student_id
            WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
            ORDER BY s.name ASC
        ''', (lab_slot_id, academic_year_id))
        students = cursor.fetchall()
        conn.close()
        return [(student_id, *name.rsplit(' ', 1)) for student_id, name in students]

    def check_existing_attendance(self, lab_slot_id, exercise_slot, academic_year_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM Attendance 
            WHERE lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
        ''', (lab_slot_id, exercise_slot, academic_year_id))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def get_student_attendance(self, student_id, lab_slot_id, exercise_slot, academic_year_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT status, timestamp FROM Attendance
            WHERE student_id = ? AND lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
        ''', (student_id, lab_slot_id, exercise_slot, academic_year_id))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result
        return None, ""

    def toggle_editing(self, button_group):
        for group in button_group:
            for button in group.buttons():
                button.setEnabled(True)

        self.change_button.setText("Editing Enabled")
        self.change_button.setEnabled(False)
        self.complete_button.setEnabled(True)

    def save_attendance(self, button_group, students, exercise_slot, lab_slot_id, academic_year_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")

        for idx, student in enumerate(students):
            present_checked = button_group[idx].buttons()[0].isChecked()
            absent_checked = button_group[idx].buttons()[1].isChecked()

            if not (present_checked or absent_checked):
                QMessageBox.warning(self, "Incomplete Attendance", f"Missing attendance data for student {student[1]} {student[2]}. Please fill all the missing data.")
                return

            status = "Present" if present_checked else "Absent"

            # Check if attendance record exists
            cursor.execute('''
                SELECT * FROM Attendance WHERE student_id = ? AND lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
            ''', (student[0], lab_slot_id, exercise_slot, academic_year_id))
            if cursor.fetchone():
                # Update existing record
                cursor.execute('''
                    UPDATE Attendance SET status = ?, timestamp = ? WHERE student_id = ? AND lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
                ''', (status, timestamp, student[0], lab_slot_id, exercise_slot, academic_year_id))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO Attendance (student_id, lab_slot_id, exercise_slot, status, timestamp, academic_year_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (student[0], lab_slot_id, exercise_slot, status, timestamp, academic_year_id))

        conn.commit()
        conn.close()
        QMessageBox.information(self, "Success", "Attendance saved successfully.")

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
        cursor.execute('''
            SELECT s.student_id, s.name
            FROM Students s
            INNER JOIN Enrollments e ON s.student_id = e.student_id
            WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
            ORDER BY s.name ASC
        ''', (lab_slot_id, academic_year_id))
        students = cursor.fetchall()

        # Fetch attendance data
        attendance_data = {}
        for exercise_slot in exercise_slots:
            cursor.execute('''
                SELECT student_id, status, timestamp
                FROM Attendance
                WHERE lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
            ''', (lab_slot_id, exercise_slot, academic_year_id))
            attendance_data[exercise_slot] = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

        conn.close()

        if not students:
            QMessageBox.information(self, "No Students", f"No students found for lab slot '{selected_slot}'")
            return

        self.show_attendance_window = QWidget()
        self.show_attendance_window.setWindowTitle(f"Attendance for {selected_slot}")
        layout = QVBoxLayout(self.show_attendance_window)

        columns = ["Last Name", "First Name", "Student ID"]
        for slot in exercise_slots:
            columns.append(f"{slot} Status")
            columns.append(f"{slot} Timestamp")

        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        absences_count = {}

        for row_idx, student in enumerate(students):
            student_id, name = student

            table.insertRow(row_idx)
            last_name, first_name = name.rsplit(' ', 1)
            table.setItem(row_idx, 0, QTableWidgetItem(last_name))
            table.setItem(row_idx, 1, QTableWidgetItem(first_name))
            table.setItem(row_idx, 2, QTableWidgetItem(str(student_id)))

            col_idx = 3
            for exercise_slot in exercise_slots:
                status, timestamp = attendance_data.get(exercise_slot, {}).get(student_id, ("Absent", ""))
                status_item = QTableWidgetItem(status)
                if status == "Absent":
                    absences_count[student_id] = absences_count.get(student_id, 0) + 1
                    if absences_count[student_id] == 1:
                        status_item.setForeground(QtGui.QColor('blue'))
                    elif absences_count[student_id] >= 2:
                        status_item.setForeground(QtGui.QColor('red'))
                table.setItem(row_idx, col_idx, status_item)
                table.setItem(row_idx, col_idx + 1, QTableWidgetItem(timestamp))
                col_idx += 2

        layout.addWidget(table)
        self.show_attendance_window.setLayout(layout)
        self.show_attendance_window.show()

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

    def show_absents(self):
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

        exercise_slots = self.select_exercise_slots()
        if not exercise_slots:
            QMessageBox.warning(self, "No Exercise Slot Selected", "No exercise slot selected.")
            return

        absents_data = self.get_absents_data(selected_slots, exercise_slots, semester, year)
        if not absents_data:
            QMessageBox.information(self, "No Absents", "No absents found for the selected slots.")
            return

        self.display_absents(absents_data, exercise_slots)

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

    def display_absents(self, absents_data, exercise_slots):
        absents_window = QDialog(self)
        absents_window.setWindowTitle("Absents Summary")
        layout = QVBoxLayout(absents_window)

        table = QTableWidget()
        table.setColumnCount(3 + len(exercise_slots))
        headers = ["Student Name", "Student ID", "Lab Slot"] + [f"{slot}" for slot in exercise_slots]
        table.setHorizontalHeaderLabels(headers)

        student_absents = {}
        absents_count = {slot: 0 for slot in exercise_slots}

        for row in absents_data:
            student_name = row[0]
            student_id = row[1]
            lab_slot = row[2]
            exercise_slot = row[3]
            if student_id not in student_absents:
                student_absents[student_id] = [student_name, student_id, lab_slot] + [""] * len(exercise_slots)
            idx = exercise_slots.index(exercise_slot) + 3
            student_absents[student_id][idx] = "Absent"
            absents_count[exercise_slot] += 1

        for i, (student_id, details) in enumerate(student_absents.items()):
            table.insertRow(i)
            for j, detail in enumerate(details):
                table.setItem(i, j, QTableWidgetItem(detail))

        # Add a row for the totals
        table.insertRow(table.rowCount())
        table.setItem(table.rowCount() - 1, 0, QTableWidgetItem("Total Absents"))
        for i, slot in enumerate(exercise_slots):
            table.setItem(table.rowCount() - 1, i + 3, QTableWidgetItem(str(absents_count[slot])))

        layout.addWidget(table)
        absents_window.setLayout(layout)
        absents_window.exec_()
