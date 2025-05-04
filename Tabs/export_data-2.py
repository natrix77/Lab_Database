import sqlite3
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog, QComboBox, QDialogButtonBox, QCheckBox, QMessageBox, QFileDialog, QInputDialog
from PyQt5.QtCore import Qt
import pandas as pd

class ExportDataTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        # Button to export general data to Excel
        self.export_button = QPushButton("Export Data to Excel")
        self.export_button.clicked.connect(self.export_data_routine)

        # New button for exporting absences
        self.export_absents_button = QPushButton("Export Absences to Excel")
        self.export_absents_button.clicked.connect(self.export_absents_to_excel)

        layout = QVBoxLayout()
        layout.addWidget(self.export_button)
        layout.addWidget(self.export_absents_button)
        self.setLayout(layout)

    # Routine to export general data
    def export_data_routine(self):
        # Placeholder for the general data export routine
        QMessageBox.information(self, "Export", "General data export functionality.")

    # Method to select or add a semester and year
    def select_or_add_semester_year(self):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT semester, year FROM AcademicYear ORDER BY year, semester")
        semesters_years = cursor.fetchall()
        conn.close()

        items = ["Add New Semester/Year"]
        items += [f"{sem} {yr}" for sem, yr in semesters_years]

        item, ok = QInputDialog.getItem(self, "Select Semester and Year", "Choose or add:", items, 0, False)
        if ok and item == "Add New Semester/Year":
            semester, ok_sem = QInputDialog.getItem(self, "Semester", "Enter Semester:", ["ΕΑΡΙΝΟ", "ΧΕΙΜΕΡΙΝΟ"])
            year, ok_year = QInputDialog.getInt(self, "Year", "Enter Year:", 2023, 2000, 2100, 1)
            if ok_sem and ok_year:
                conn = sqlite3.connect('student_register.db')
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO AcademicYear (semester, year) VALUES (?, ?)", (semester, year))
                conn.commit()
                conn.close()
                return semester, year
        elif ok and item != "Add New Semester/Year":
            semester, year = item.split()
            return semester, int(year)
        return None, None

    # Fetches lab slots based on semester and year
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

    # Dialog to select lab slots
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

    # Dialog to select exercise slots
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

    # New method to export absences to Excel
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

    # Helper function to get absents data
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
