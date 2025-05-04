# Tabs/import_students.py
import sqlite3
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QMessageBox,
    QInputDialog, QTableWidget, QTableWidgetItem, QLabel, QDialog,
    QCheckBox, QDialogButtonBox, QComboBox
)
from PyQt5.QtCore import Qt

class ImportStudentsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.import_button = QPushButton("Import Students from File")
        self.import_button.clicked.connect(self.import_students)

        self.show_button = QPushButton("Show Imported Students")
        self.show_button.clicked.connect(self.show_students)

        layout = QVBoxLayout()
        layout.addWidget(self.import_button)
        layout.addWidget(self.show_button)
        self.setLayout(layout)

    def get_existing_semesters_years(self):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT semester, year FROM AcademicYear ORDER BY year, semester
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
                    semester, ok1 = QInputDialog.getItem(
                        self, "Input", "Enter Semester:", semesters, 0, False)
                    year, ok2 = QInputDialog.getInt(
                        self, "Input", "Enter Year:", 2023, 2000, 2100, 1)
                    if not ok1 or not ok2:
                        QMessageBox.warning(
                            self, "Input Error", "Semester and Year are required")
                        return None, None
                    return semester, year
                else:
                    selected = combo_box.currentText().split()
                    return selected[0], int(selected[1])
            else:
                return None, None  # User canceled the dialog
        else:
            semesters = ["ΕΑΡΙΝΟ", "ΧΕΙΜΕΡΙΝΟ"]
            semester, ok1 = QInputDialog.getItem(
                self, "Input", "Enter Semester:", semesters, 0, False)
            year, ok2 = QInputDialog.getInt(
                self, "Input", "Enter Year:", 2023, 2000, 2100, 1)
            if not ok1 or not ok2:
                QMessageBox.warning(
                    self, "Input Error", "Semester and Year are required")
                return None, None
            return semester, year

    def import_students(self):
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if the user canceled the selection

        # Now, get or insert the academic_year_id
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM AcademicYear WHERE semester=? AND year=?",
            (semester, year))
        result = cursor.fetchone()
        if result:
            academic_year_id = result[0]
        else:
            cursor.execute(
                "INSERT INTO AcademicYear (semester, year) VALUES (?, ?)",
                (semester, year))
            academic_year_id = cursor.lastrowid
            conn.commit()
        conn.close()

        while True:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open Excel File", "", "Excel files (*.xlsx *.xls)")
            if file_path:
                self.import_data(file_path, academic_year_id)
                reply = QMessageBox.question(
                    self, "Import Another?",
                    "Do you want to import another file?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    break
            else:
                break

    def import_data(self, file_path, academic_year_id):
        try:
            df = pd.read_excel(file_path, header=None)
            # Extract lab slot name from cell A1
            lab_slot_name = df.iloc[0, 0]
            # Set column names from row 3 (index 2)
            df.columns = df.iloc[2]
            # Drop first three rows (indices 0, 1, 2)
            df = df.drop([0, 1, 2]).reset_index(drop=True)
            # Create 'Student_Name' by combining 'Επώνυμο' and 'Όνομα'
            df['Student_Name'] = df['Επώνυμο'] + ' ' + df['Όνομα']

            conn = sqlite3.connect('student_register.db')
            cursor = conn.cursor()
            # Check if lab slot exists
            cursor.execute(
                "SELECT id FROM LabSlots WHERE name=? AND academic_year_id=?",
                (lab_slot_name, academic_year_id))
            result = cursor.fetchone()
            if result:
                lab_slot_id = result[0]
                # Ask if user wants to replace data
                reply = QMessageBox.question(
                    self, "Lab Slot Exists",
                    f"The lab slot '{lab_slot_name}' already exists. "
                    "Do you want to replace it?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    conn.close()
                    return
                else:
                    # Delete existing data
                    cursor.execute("DELETE FROM LabSlots WHERE id=?",
                                   (lab_slot_id,))
                    cursor.execute("DELETE FROM Enrollments WHERE lab_slot_id=?",
                                   (lab_slot_id,))
                    conn.commit()
                    # Re-insert LabSlot
                    cursor.execute(
                        "INSERT INTO LabSlots (name, academic_year_id) "
                        "VALUES (?, ?)",
                        (lab_slot_name, academic_year_id))
                    lab_slot_id = cursor.lastrowid
            else:
                cursor.execute(
                    "INSERT INTO LabSlots (name, academic_year_id) VALUES (?, ?)",
                    (lab_slot_name, academic_year_id))
                lab_slot_id = cursor.lastrowid

            # Insert Students and Enrollments
            for index, row in df.iterrows():
                student_id = str(row['Αριθμός μητρώου'])
                name = row['Student_Name']
                email = row['E-mail']
                username = row['Όνομα χρήστη (username)']

                # Insert student if not exists
                cursor.execute(
                    "SELECT * FROM Students WHERE student_id=?", (student_id,))
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO Students (student_id, name, email, username) "
                        "VALUES (?, ?, ?, ?)",
                        (student_id, name, email, username))
                else:
                    # Check if student is already enrolled in this academic year
                    cursor.execute(
                        "SELECT * FROM Enrollments WHERE student_id=? AND "
                        "academic_year_id=?",
                        (student_id, academic_year_id))
                    if cursor.fetchone():
                        QMessageBox.warning(
                            self, "Warning",
                            f"Student ID {student_id} is already enrolled "
                            "in this academic year.")
                        continue

                # Insert Enrollment
                cursor.execute(
                    "INSERT INTO Enrollments (student_id, academic_year_id, "
                    "lab_slot_id) VALUES (?, ?, ?)",
                    (student_id, academic_year_id, lab_slot_id))

            conn.commit()
            QMessageBox.information(
                self, "Success",
                f"Students data for lab slot '{lab_slot_name}' imported successfully")
        except Exception as e:
            QMessageBox.critical(
                self, "Import Error",
                f"An error occurred while importing data: {e}")
        finally:
            conn.close()

    def show_students(self):
        # Prompt for semester and year
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if the user canceled the selection

        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        # Fetch academic_year_id
        cursor.execute(
            "SELECT id FROM AcademicYear WHERE semester=? AND year=?",
            (semester, year))
        result = cursor.fetchone()
        if not result:
            QMessageBox.warning(
                self, "Warning",
                "No data found for the selected semester and year.")
            conn.close()
            return
        academic_year_id = result[0]

        # Fetch lab slots
        cursor.execute(
            "SELECT id, name FROM LabSlots WHERE academic_year_id=?",
            (academic_year_id,))
        lab_slots = cursor.fetchall()
        if not lab_slots:
            QMessageBox.warning(
                self, "Warning",
                "No lab slots found for the selected academic year.")
            conn.close()
            return

        # Let user select lab slots
        lab_slot_names = [slot[1] for slot in lab_slots]
        selected_slots = self.select_lab_slots(lab_slot_names)
        if not selected_slots:
            conn.close()
            return

        # Get lab_slot_ids for selected lab slots
        selected_lab_slot_ids = []
        lab_slot_name_id_map = {}
        for slot in lab_slots:
            if slot[1] in selected_slots:
                selected_lab_slot_ids.append(slot[0])
                lab_slot_name_id_map[slot[0]] = slot[1]

        # Fetch students in the selected lab slots, ordered by lab slot
        placeholders = ', '.join(['?'] * len(selected_lab_slot_ids))
        query = f"""
            SELECT Students.student_id, Students.name, Students.email,
                   Students.username, LabSlots.name
            FROM Students
            INNER JOIN Enrollments ON Students.student_id = Enrollments.student_id
            INNER JOIN LabSlots ON Enrollments.lab_slot_id = LabSlots.id
            WHERE Enrollments.lab_slot_id IN ({placeholders})
            ORDER BY LabSlots.name, Students.name
        """
        cursor.execute(query, selected_lab_slot_ids)
        students = cursor.fetchall()

        if not students:
            QMessageBox.information(
                self, "Info",
                "No students found for the selected lab slots.")
            conn.close()
            return

        conn.close()

        # Display students in a table
        self.show_students_window = QWidget()
        self.show_students_window.setWindowTitle("Imported Students")
        layout = QVBoxLayout(self.show_students_window)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["#", "Student ID", "Name", "Email", "Username", "Lab Slot"])

        row_idx = 0
        total_students = 0
        slot_counts = {}
        current_lab_slot = None
        student_number = 0

        for student in students:
            lab_slot_name = student[4]
            if current_lab_slot != lab_slot_name:
                # If not the first lab slot, add a separator row
                if current_lab_slot is not None:
                    # Add a blank row to separate lab slots
                    table.setRowCount(row_idx + 1)
                    for col in range(6):
                        item = QTableWidgetItem("")
                        item.setFlags(Qt.ItemIsEnabled)
                        table.setItem(row_idx, col, item)
                    row_idx += 1

                current_lab_slot = lab_slot_name
                student_number = 1  # Reset student number for new lab slot
            else:
                student_number += 1

            table.setRowCount(row_idx + 1)
            # Set the student number
            table.setItem(row_idx, 0, QTableWidgetItem(str(student_number)))
            # Set the student data
            table.setItem(row_idx, 1, QTableWidgetItem(str(student[0])))  # Student ID
            table.setItem(row_idx, 2, QTableWidgetItem(str(student[1])))  # Name
            table.setItem(row_idx, 3, QTableWidgetItem(str(student[2])))  # Email
            table.setItem(row_idx, 4, QTableWidgetItem(str(student[3])))  # Username
            table.setItem(row_idx, 5, QTableWidgetItem(str(lab_slot_name)))  # Lab Slot

            total_students += 1
            if lab_slot_name in slot_counts:
                slot_counts[lab_slot_name] += 1
            else:
                slot_counts[lab_slot_name] = 1

            row_idx += 1

        table.resizeColumnsToContents()
        layout.addWidget(table)

        totals_label = QLabel(f"Total Students: {total_students}")
        layout.addWidget(totals_label)

        for slot, count in slot_counts.items():
            slot_label = QLabel(f"Total Students in {slot}: {count}")
            layout.addWidget(slot_label)

        self.show_students_window.setLayout(layout)
        self.show_students_window.show()

    def select_lab_slots(self, lab_slots):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Lab Slots")
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
