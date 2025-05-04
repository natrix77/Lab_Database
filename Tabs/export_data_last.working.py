# Tabs/export_data.py

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog, QComboBox, QDialogButtonBox, QCheckBox, QMessageBox
from PyQt5.QtCore import QDateTime, Qt
import sqlite3
import pandas as pd

class ExportDataTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.export_button = QPushButton("Export Data to Excel")
        self.export_button.clicked.connect(self.export_data_routine)

        layout = QVBoxLayout()
        layout.addWidget(self.export_button)
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
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT semester, year FROM AcademicYear ORDER BY year, semester
        ''')
        results = cursor.fetchall()
        conn.close()
        return results

    def export_data_routine(self):
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

        self.export_to_excel(selected_slots, exercise_slots, semester, year)

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

        select_all_cb = QCheckBox("All")
        select_all_cb.stateChanged.connect(lambda state: self.toggle_select_all(state, self.slot_vars))
        layout.addWidget(select_all_cb)

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

        select_all_cb = QCheckBox("All exercise slots")
        select_all_cb.stateChanged.connect(lambda state: self.toggle_select_all(state, self.slot_vars))
        layout.addWidget(select_all_cb)

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

    def toggle_select_all(self, state, slot_vars):
        for cb in slot_vars.values():
            cb.setChecked(state == Qt.Checked)

    def export_to_excel(self, selected_slots, selected_exercise_slots, semester, year):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        data = []
        columns = ["Student ID", "Student Name", "Lab Slot"]

        for slot in selected_exercise_slots:
            columns.append(f"{slot} Attendance Status")
            columns.append(f"{slot} Attendance Timestamp")
            columns.append(f"{slot} Grade")

        for lab_slot in selected_slots:
            cursor.execute('''
                SELECT s.student_id, s.name, ls.name AS lab_slot,
                       a.exercise_slot, a.status, a.timestamp, g.grade, g.timestamp
                FROM Students s
                INNER JOIN Enrollments e ON s.student_id = e.student_id
                INNER JOIN LabSlots ls ON e.lab_slot_id = ls.id
                LEFT JOIN (
                    SELECT student_id, lab_slot_id, exercise_slot, status, MAX(timestamp) as timestamp
                    FROM Attendance
                    WHERE academic_year_id = (SELECT id FROM AcademicYear WHERE semester = ? AND year = ?)
                    GROUP BY student_id, lab_slot_id, exercise_slot
                ) a ON s.student_id = a.student_id AND e.lab_slot_id = a.lab_slot_id
                LEFT JOIN (
                    SELECT student_id, lab_slot_id, exercise_slot, grade, MAX(timestamp) as timestamp
                    FROM Grades
                    WHERE academic_year_id = (SELECT id FROM AcademicYear WHERE semester = ? AND year = ?)
                    GROUP BY student_id, lab_slot_id, exercise_slot
                ) g ON s.student_id = g.student_id AND e.lab_slot_id = g.lab_slot_id AND a.exercise_slot = g.exercise_slot
                WHERE ls.name = ? AND e.academic_year_id = (SELECT id FROM AcademicYear WHERE semester = ? AND year = ?)
            ''', (semester, year, semester, year, lab_slot, semester, year))

            rows = cursor.fetchall()

            student_data = {}
            for row in rows:
                student_id, student_name, lab_slot, exercise_slot, status, a_timestamp, grade, g_timestamp = row

                if student_id not in student_data:
                    student_data[student_id] = {
                        "Student ID": student_id,
                        "Student Name": student_name,
                        "Lab Slot": lab_slot,
                    }

                if exercise_slot in selected_exercise_slots:
                    student_data[student_id][f"{exercise_slot} Attendance Status"] = status
                    student_data[student_id][f"{exercise_slot} Attendance Timestamp"] = a_timestamp
                    student_data[student_id][f"{exercise_slot} Grade"] = grade

            data.extend(student_data.values())

        # Fetch final grades
        final_grades_data = []
        cursor.execute('''
            SELECT s.student_id, s.name, fg.lab_average, fg.jun_exam_grade, fg.sep_exam_grade, fg.final_grade
            FROM FinalGrades fg
            INNER JOIN Students s ON fg.student_id = s.student_id
            WHERE fg.academic_year_id = (SELECT id FROM AcademicYear WHERE semester = ? AND year = ?)
        ''', (semester, year))

        final_grades = cursor.fetchall()

        for row in final_grades:
            student_id, student_name, lab_average, jun_exam_grade, sep_exam_grade, final_grade = row
            final_grades_data.append({
                "Student ID": student_id,
                "Student Name": student_name,
                "Lab Average": lab_average,
                "Jun Exam Grade": jun_exam_grade,
                "Sep Exam Grade": sep_exam_grade,
                "Final Grade": final_grade
            })

        conn.close()

        if not data and not final_grades_data:
            QMessageBox.warning(self, "No Data", "No data found for the selected lab slots and final grades.")
            return

        # Create DataFrames for the three sheets
        df_per_lab_slot = pd.DataFrame(data, columns=columns)
        df_alphabetically = df_per_lab_slot.sort_values(by=["Student Name"])
        df_final_grades = pd.DataFrame(final_grades_data, columns=["Student ID", "Student Name", "Lab Average", "Jun Exam Grade", "Sep Exam Grade", "Final Grade"])

        # Generate filename
        current_date_time = QDateTime.currentDateTime().toString("yyyy.MM.dd.HH.mm.ss")
        filename = f"{semester}.{year}.{current_date_time}.xlsx"

        # Save Excel file with three sheets
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            if not df_per_lab_slot.empty:
                df_per_lab_slot.to_excel(writer, sheet_name="Per Lab Slot", index=False)
            if not df_alphabetically.empty:
                df_alphabetically.to_excel(writer, sheet_name="Alphabetically", index=False)
            if not df_final_grades.empty:
                df_final_grades.to_excel(writer, sheet_name="Final Grades", index=False)

        QMessageBox.information(self, "Export Success", f"Data successfully exported to {filename}")
