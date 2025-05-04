from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, 
    QDialog, QInputDialog, QMessageBox, QDialogButtonBox, QCheckBox, QHBoxLayout, QComboBox, QProgressDialog
)
from PyQt5.QtCore import QDateTime, Qt, QThread, pyqtSignal
import sqlite3
import time
from sqlite3 import OperationalError

class GradeProcessingThread(QThread):
    processing_complete = pyqtSignal()

    def __init__(self, table, students, exercise_slot, lab_slot_id, academic_year_id, parent=None):
        super().__init__(parent)
        self.table = table
        self.students = students
        self.exercise_slot = exercise_slot
        self.lab_slot_id = lab_slot_id
        self.academic_year_id = academic_year_id
        self.parent = parent

    def run(self):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                with sqlite3.connect('student_register.db', timeout=20) as conn:
                    cursor = conn.cursor()

                    for idx, student in enumerate(self.students):
                        student_id = student[0]
                        attendance_status = self.table.item(idx, 4).text()
                        grade_item = self.table.item(idx, 5)
                        timestamp_item = self.table.item(idx, 6)
                        confirm_checkbox = self.table.cellWidget(idx, 7)

                        if attendance_status == "Present" and confirm_checkbox.isChecked():
                            grade = float(grade_item.text())
                            timestamp = timestamp_item.text()

                            cursor.execute('''
                                INSERT OR REPLACE INTO Grades (student_id, lab_slot_id, exercise_slot, grade, timestamp, academic_year_id) 
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (student_id, self.lab_slot_id, self.exercise_slot, grade, timestamp, self.academic_year_id))

                            # Calculate and update final grades
                            self.parent.calculate_and_update_final_grades(student_id, self.academic_year_id, cursor)

                    conn.commit()
                break  # Break out of the loop if the operation is successful
            except OperationalError:
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait for 1 second before retrying
                else:
                    raise

        self.processing_complete.emit()

class InsertGradesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        # Initialize UI components
        self.record_grade_button = QPushButton("Record Student Grade")
        self.record_grade_button.clicked.connect(self.record_grade_routine)
        self.show_grades_button = QPushButton("Show Grades")
        self.show_grades_button.clicked.connect(self.show_grades)

        layout = QVBoxLayout()
        layout.addWidget(self.record_grade_button)
        layout.addWidget(self.show_grades_button)
        self.setLayout(layout)

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

    def get_existing_semesters_years(self):
        with sqlite3.connect('student_register.db', timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT semester, year FROM AcademicYear ORDER BY year, semester
            ''')
            return cursor.fetchall()

    def record_grade_routine(self):
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if the user canceled the selection

        lab_slots = self.get_lab_slots(semester, year)
        if not lab_slots:
            return

        selected_slots = self.select_lab_slots(lab_slots)
        if not selected_slots:
            return

        selected_slot = selected_slots[0]

        exercise_slot, ok = QInputDialog.getItem(self, "Select Exercise Slot", "Select Exercise Slot:", 
                                                 ["Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Replacement1", "Replacement2", "Exam.Jun", "Exam.Sep"], 0, False)
        if not ok:
            return

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

        students = self.get_students(lab_slot_id, academic_year_id)
        if not students:
            return

        grade_window = QDialog(self)
        grade_window.setWindowTitle(f"Record Grades for {selected_slot} - {exercise_slot}")
        layout = QVBoxLayout(grade_window)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(["#", "Last Name", "First Name", "Student ID", "Attendance Status", "Grade", "Timestamp", "Confirm"])

        self.checkbox_group = []

        for idx, (student_id, last_name, first_name) in enumerate(students):
            table.insertRow(idx)
            table.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            table.setItem(idx, 1, QTableWidgetItem(last_name))
            table.setItem(idx, 2, QTableWidgetItem(first_name))
            table.setItem(idx, 3, QTableWidgetItem(str(student_id)))

            attendance_status, _ = self.get_student_attendance(student_id, lab_slot_id, exercise_slot, academic_year_id)
            grade, timestamp = self.get_student_grade(student_id, lab_slot_id, exercise_slot, academic_year_id)

            table.setItem(idx, 4, QTableWidgetItem(attendance_status))
            grade_item = QTableWidgetItem("")

            # Display the previously saved grade if it exists
            if grade is not None:
                grade_item.setText(str(grade))
                table.setItem(idx, 6, QTableWidgetItem(str(timestamp)))

            grade_item.setFlags(grade_item.flags() | Qt.ItemIsEditable)

            confirm_checkbox = QCheckBox()
            confirm_checkbox.stateChanged.connect(lambda state, r=idx: self.update_timestamp(r, table))
            self.checkbox_group.append(confirm_checkbox)

            if attendance_status == "Absent" or not attendance_status:
                grade_item.setFlags(grade_item.flags() & ~Qt.ItemIsEditable)
                confirm_checkbox.setEnabled(False)
            else:
                if grade is not None:
                    confirm_checkbox.setChecked(True)
                    confirm_checkbox.setEnabled(False)
                    grade_item.setFlags(grade_item.flags() & ~Qt.ItemIsEditable)

            table.setItem(idx, 5, grade_item)
            table.setCellWidget(idx, 7, confirm_checkbox)

        layout.addWidget(table)

        self.change_button = QPushButton("Make changes?")
        self.change_button.clicked.connect(lambda: self.toggle_grade_editing(table, students, lab_slot_id, exercise_slot, academic_year_id))
        layout.addWidget(self.change_button)

        self.complete_button = QPushButton("Save Grades")
        self.complete_button.clicked.connect(lambda: self.save_grades(table, students, exercise_slot, lab_slot_id, academic_year_id))
        layout.addWidget(self.complete_button)

        grade_window.setLayout(layout)
        grade_window.exec_()

    def update_timestamp(self, row, table):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        table.setItem(row, 6, QTableWidgetItem(timestamp))

    def save_grades(self, table, students, exercise_slot, lab_slot_id, academic_year_id):
        self.progress_dialog = QProgressDialog("Processing grades...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Please Wait")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)

        # Start the background processing thread
        self.thread = GradeProcessingThread(table, students, exercise_slot, lab_slot_id, academic_year_id, self)
        self.thread.processing_complete.connect(self.on_processing_complete)
        self.thread.start()

    def on_processing_complete(self):
        self.progress_dialog.setValue(100)
        QMessageBox.information(self, "Success", "Grades saved successfully")

    def toggle_grade_editing(self, table, students, lab_slot_id, exercise_slot, academic_year_id):
        for idx, student in enumerate(students):
            student_id = student[0]
            attendance_status, _ = self.get_student_attendance(student_id, lab_slot_id, exercise_slot, academic_year_id)
            grade_item = table.item(idx, 5)
            confirm_checkbox = table.cellWidget(idx, 7)

            if attendance_status == "Present":
                grade_item.setFlags(grade_item.flags() | Qt.ItemIsEditable)
                confirm_checkbox.setEnabled(True)
            else:
                grade_item.setFlags(grade_item.flags() & ~Qt.ItemIsEditable)
                confirm_checkbox.setEnabled(False)

        self.change_button.setText("Editing Enabled")
        self.change_button.setEnabled(False)
        self.complete_button.setEnabled(True)

    def show_grades(self):
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if the user canceled the selection

        lab_slots = self.get_lab_slots(semester, year)
        if not lab_slots:
            return

        selected_slots = self.select_lab_slots(lab_slots)
        if not selected_slots:
            return

        selected_slot = selected_slots[0]

        exercise_slots = self.select_exercise_slots()
        if not exercise_slots:
            return

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
            ORDER BY s.name
        ''', (lab_slot_id, academic_year_id))
        students = cursor.fetchall()

        if not students:
            QMessageBox.information(self, "No Students", f"No students found for lab slot '{selected_slot}'")
            conn.close()
            return

        # Fetch grade and attendance data
        grade_data = {}
        attendance_data = {}
        for exercise_slot in exercise_slots:
            cursor.execute('''
                SELECT g.student_id, g.grade, a.status
                FROM Grades g
                LEFT JOIN Attendance a ON g.student_id = a.student_id AND g.lab_slot_id = a.lab_slot_id AND g.exercise_slot = a.exercise_slot
                WHERE g.lab_slot_id = ? AND g.exercise_slot = ? AND g.academic_year_id = ?
            ''', (lab_slot_id, exercise_slot, academic_year_id))
            for row in cursor.fetchall():
                grade_data.setdefault(exercise_slot, {})[row[0]] = row[1]
                attendance_data.setdefault(exercise_slot, {})[row[0]] = row[2]

        conn.close()

        self.show_grades_window = QWidget()
        self.show_grades_window.setWindowTitle(f"Grades for {selected_slot}")
        layout = QVBoxLayout(self.show_grades_window)

        # Build table headers with attendance and grade columns
        columns = ["Last Name", "First Name", "Student ID"]
        for slot in exercise_slots:
            columns.append(f"{slot} Attendance")
            columns.append(f"{slot} Grade")

        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        for row_idx, student in enumerate(students):
            student_id, name = student
            last_name, first_name = name.rsplit(' ', 1)

            table.insertRow(row_idx)
            table.setItem(row_idx, 0, QTableWidgetItem(last_name))
            table.setItem(row_idx, 1, QTableWidgetItem(first_name))
            table.setItem(row_idx, 2, QTableWidgetItem(str(student_id)))

            col_idx = 3
            for exercise_slot in exercise_slots:
                attendance_status = attendance_data.get(exercise_slot, {}).get(student_id, "")
                grade = grade_data.get(exercise_slot, {}).get(student_id, "")
                attendance_item = QTableWidgetItem(attendance_status)
                grade_item = QTableWidgetItem(str(grade))

                table.setItem(row_idx, col_idx, attendance_item)
                table.setItem(row_idx, col_idx + 1, grade_item)
                col_idx += 2

        layout.addWidget(table)
        self.show_grades_window.setLayout(layout)
        self.show_grades_window.show()

    def get_lab_slots(self, semester, year):
        with sqlite3.connect('student_register.db', timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT name FROM LabSlots
                INNER JOIN AcademicYear ON LabSlots.academic_year_id = AcademicYear.id
                WHERE AcademicYear.semester = ? AND AcademicYear.year = ?
            ''', (semester, year))
            return [row[0] for row in cursor.fetchall()]

    def select_lab_slots(self, lab_slots):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Lab Slot")
        layout = QVBoxLayout(dialog)
        
        self.slot_vars = {}
        for slot in lab_slots:
            cb = QCheckBox(slot)
            layout.addWidget(cb)
            self.slot_vars[slot] = cb

        button_box = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        button_box.addWidget(ok_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_box.addWidget(cancel_button)
        layout.addLayout(button_box)

        if dialog.exec_() == QDialog.Accepted:
            return [slot for slot, cb in self.slot_vars.items() if cb.isChecked()]
        return []

    def get_students(self, lab_slot_id, academic_year_id):
        with sqlite3.connect('student_register.db', timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.student_id, s.name
                FROM Students s
                INNER JOIN Enrollments e ON s.student_id = e.student_id
                WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
                ORDER BY s.name
            ''', (lab_slot_id, academic_year_id))
            return [(student_id, *name.rsplit(' ', 1)) for student_id, name in cursor.fetchall()]

    def get_student_attendance(self, student_id, lab_slot_id, exercise_slot, academic_year_id):
        with sqlite3.connect('student_register.db', timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status, timestamp FROM Attendance WHERE student_id = ? AND lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
            ''', (student_id, lab_slot_id, exercise_slot, academic_year_id))
            result = cursor.fetchone()
        return result if result else (None, "")

    def get_student_grade(self, student_id, lab_slot_id, exercise_slot, academic_year_id):
        with sqlite3.connect('student_register.db', timeout=20) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT grade, timestamp FROM Grades 
                WHERE student_id = ? AND lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
            ''', (student_id, lab_slot_id, exercise_slot, academic_year_id))
            result = cursor.fetchone()
        return result if result else (None, "")

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

    def calculate_and_update_final_grades(self, student_id, academic_year_id, cursor):
        # Calculate lab average for the latest lab grades
        cursor.execute('''
        SELECT grade FROM Grades
        WHERE student_id = ? AND exercise_slot IN ("Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Replacement1", "Replacement2")
        AND academic_year_id = ?
        ''', (student_id, academic_year_id))
        lab_grades = cursor.fetchall()

        lab_average = sum(grade[0] for grade in lab_grades) / len(lab_grades) if lab_grades else None

        # Retrieve exam grades
        cursor.execute('''
        SELECT grade FROM Grades WHERE student_id = ? AND exercise_slot = "Exam.Sep" AND academic_year_id = ?
        ''', (student_id, academic_year_id))
        sep_exam = cursor.fetchone()

        cursor.execute('''
        SELECT grade FROM Grades WHERE student_id = ? AND exercise_slot = "Exam.Jun" AND academic_year_id = ?
        ''', (student_id, academic_year_id))
        jun_exam = cursor.fetchone()

        sep_exam_grade = sep_exam[0] if sep_exam else None
        jun_exam_grade = jun_exam[0] if jun_exam else None

        # Apply the correct rule for the final exam grade
        if sep_exam_grade is not None:
            final_exam_grade = sep_exam_grade
        elif jun_exam_grade is not None:
            final_exam_grade = jun_exam_grade
        else:
            final_exam_grade = None

        # Determine the final grade
        if final_exam_grade is None or lab_average is None:
            final_grade = None
        else:
            final_grade = 0.25 * lab_average + 0.75 * final_exam_grade

        # Delete any existing entry for this student, academic year
        cursor.execute('''
        DELETE FROM FinalGrades WHERE student_id = ? AND academic_year_id = ?
        ''', (student_id, academic_year_id))

        # Insert the new entry in the FinalGrades table for this student
        cursor.execute('''
        INSERT INTO FinalGrades (student_id, lab_average, jun_exam_grade, sep_exam_grade, final_grade, academic_year_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, lab_average, jun_exam_grade, sep_exam_grade, final_grade, academic_year_id))

