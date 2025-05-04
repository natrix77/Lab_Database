import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QDialog, QComboBox, QDialogButtonBox,
    QCheckBox, QMessageBox, QFileDialog, QInputDialog
)
from PyQt5.QtCore import Qt, QDateTime
import pandas as pd

class ExportDataTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        # Buttons for exporting data
        self.export_button = QPushButton("Export General Data to Excel")
        self.export_button.clicked.connect(self.export_data_routine)

        self.export_absents_button = QPushButton("Export Absences to Excel")
        self.export_absents_button.clicked.connect(self.export_absents_to_excel)

        layout = QVBoxLayout()
        layout.addWidget(self.export_button)
        layout.addWidget(self.export_absents_button)
        self.setLayout(layout)

    # Utility to fetch existing semester/year pairs
    def get_existing_semesters_years(self):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT semester, year FROM AcademicYear ORDER BY year, semester")
        results = cursor.fetchall()
        conn.close()
        return results

    # Select or add semester and year
    def select_or_add_semester_year(self):
        existing_pairs = self.get_existing_semesters_years()
        items = ["Add New Semester/Year"]
        items += [f"{sem} {yr}" for sem, yr in existing_pairs]

        item, ok = QInputDialog.getItem(self, "Select Semester and Year", "Choose or add:", items, 0, False)
        if ok and item == "Add New Semester/Year":
            semesters = ["ΕΑΡΙΝΟ", "ΧΕΙΜΕΡΙΝΟ"]
            semester, ok_sem = QInputDialog.getItem(self, "Semester", "Enter Semester:", semesters, 0, False)
            year, ok_year = QInputDialog.getInt(self, "Year", "Enter Year:", 2023, 2000, 2100, 1)
            if ok_sem and ok_year:
                conn = sqlite3.connect('student_register.db')
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO AcademicYear (semester, year) VALUES (?, ?)", (semester, year))
                conn.commit()
                conn.close()
                return semester, year
        elif ok:
            semester, year = item.split()
            return semester, int(year)
        return None, None

    # Get lab slots for a given semester and year
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

    # Select lab slots dialog
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

    # Select exercise slots dialog
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

    # Export general data routine
    def export_data_routine(self):
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

        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()

        data = []
        columns = ["Student ID", "Student Name", "Lab Slot"]

        for slot in exercise_slots:
            columns.append(f"{slot} Attendance Status")
            columns.append(f"{slot} Attendance Timestamp")
            columns.append(f"{slot} Grade")

        for lab_slot in selected_slots:
            cursor.execute('''
                SELECT s.student_id, s.name, ls.name AS lab_slot,
                       a.exercise_slot, a.status, a.timestamp, g.grade
                FROM Students s
                INNER JOIN Enrollments e ON s.student_id = e.student_id
                INNER JOIN LabSlots ls ON e.lab_slot_id = ls.id
                LEFT JOIN Attendance a ON s.student_id = a.student_id AND e.lab_slot_id = a.lab_slot_id
                LEFT JOIN Grades g ON s.student_id = g.student_id AND e.lab_slot_id = g.lab_slot_id AND a.exercise_slot = g.exercise_slot
                WHERE ls.name = ? AND e.academic_year_id = (SELECT id FROM AcademicYear WHERE semester = ? AND year = ?)
            ''', (lab_slot, semester, year))

            rows = cursor.fetchall()
            student_data = {}

            for row in rows:
                student_id, student_name, lab_slot, exercise_slot, status, timestamp, grade = row
                if student_id not in student_data:
                    student_data[student_id] = {
                        "Student ID": student_id,
                        "Student Name": student_name,
                        "Lab Slot": lab_slot
                    }
                if exercise_slot in exercise_slots:
                    student_data[student_id][f"{exercise_slot} Attendance Status"] = status
                    student_data[student_id][f"{exercise_slot} Attendance Timestamp"] = timestamp
                    student_data[student_id][f"{exercise_slot} Grade"] = grade

            data.extend(student_data.values())

        conn.close()

        if not data:
            QMessageBox.warning(self, "No Data", "No data found for the selected lab slots and exercises.")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Exported Data", "", "Excel Files (*.xlsx)")
        if save_path:
            if not save_path.endswith('.xlsx'):
                save_path += '.xlsx'

            df = pd.DataFrame(data, columns=columns)
            df_alphabetical = df.sort_values(by=["Student Name"])

            with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name="Per Lab Slot")
                df_alphabetical.to_excel(writer, index=False, sheet_name="Alphabetically")

            QMessageBox.information(self, "Export Success", f"Data successfully exported to {save_path}")

    # Export absences to Excel
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

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Absences Excel File", "", "Excel Files (*.xlsx)")
        if save_path:
            if not save_path.endswith('.xlsx'):
                save_path += '.xlsx'

            columns = ["Student Name", "Student ID", "Lab Slot", "Exercise Slot", "Status"]
            df_absents = pd.DataFrame(absents_data, columns=columns)

            with pd.ExcelWriter(save_path, engine='xlsxwriter') as writer:
                df_absents.to_excel(writer, index=False, sheet_name="Absents")

            QMessageBox.information(self, "Export Success", f"Absences data successfully exported to {save_path}")

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
            '''.format(seq=','.join(['?'] * len(exercise_slots))),
            (lab_slot, *exercise_slots))
            rows = cursor.fetchall()
            data.extend(rows)

        conn.close()
        return data
