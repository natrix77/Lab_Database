# Tabs/assign_teams.py

import sqlite3
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QMessageBox, QInputDialog,
    QDialog, QLabel, QCheckBox, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QHBoxLayout, QComboBox
)
from PyQt5.QtCore import Qt

class AssignTeamsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.assign_button = QPushButton("Assign Teams to Student Slots")
        self.assign_button.clicked.connect(self.assign_teams)

        self.show_button = QPushButton("Show Teams")
        self.show_button.clicked.connect(self.show_teams)

        layout = QVBoxLayout()
        layout.addWidget(self.assign_button)
        layout.addWidget(self.show_button)
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

            button_box = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)

            if dialog.exec_() == QDialog.Accepted:
                if combo_box.currentIndex() == 0:
                    semesters = ["ΕΑΡΙΝΟ", "ΧΕΙΜΕΡΙΝΟ"]
                    semester, ok1 = QInputDialog.getItem(
                        self, "Input", "Enter Semester:",
                        semesters, 0, False)
                    year, ok2 = QInputDialog.getInt(
                        self, "Input", "Enter Year:", 2023, 2000, 2100, 1)
                    if not ok1 or not ok2:
                        QMessageBox.warning(
                            self, "Input Error",
                            "Semester and Year are required")
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

    def assign_teams(self):
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if the user canceled the selection

        # Fetch academic_year_id
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
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
        conn.close()
        if not lab_slots:
            QMessageBox.warning(
                self, "Warning",
                "No lab slots found for the selected academic year.")
            return

        # Let user select a lab slot
        lab_slot_names = [slot[1] for slot in lab_slots]
        lab_slot_name, ok = QInputDialog.getItem(
            self, "Select Lab Slot",
            "Lab Slot:", lab_slot_names, 0, False)
        if not ok:
            return

        # Get lab_slot_id
        lab_slot_id = None
        for slot in lab_slots:
            if slot[1] == lab_slot_name:
                lab_slot_id = slot[0]
                break

        # Now assign teams to this lab slot
        self.assign_teams_to_lab_slot(
            academic_year_id, lab_slot_id, lab_slot_name)

    def assign_teams_to_lab_slot(
            self, academic_year_id, lab_slot_id, lab_slot_name):
        # Fetch students enrolled in this lab slot
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Students.student_id, Students.name
            FROM Students
            INNER JOIN Enrollments ON Students.student_id = Enrollments.student_id
            WHERE Enrollments.academic_year_id=? AND Enrollments.lab_slot_id=?
        ''', (academic_year_id, lab_slot_id))
        students = cursor.fetchall()
        conn.close()
        if not students:
            QMessageBox.information(
                self, "Info",
                "No students found for the selected lab slot.")
            return

        # Create a dialog to assign teams
        self.team_assignment_dialog = QDialog(self)
        self.team_assignment_dialog.setWindowTitle(
            f"Assign Teams for {lab_slot_name}")
        layout = QVBoxLayout(self.team_assignment_dialog)

        # Create labels to display available and assigned students
        total_students = len(students)
        assigned_students_count = self.get_assigned_students_count(
            lab_slot_id)
        available_students_count = total_students - assigned_students_count

        self.available_students_label = QLabel(
            f"Available Students: {available_students_count}")
        self.assigned_students_label = QLabel(
            f"Assigned Students: {assigned_students_count}")
        layout.addWidget(self.available_students_label)
        layout.addWidget(self.assigned_students_label)

        # Create a list of students with checkboxes
        self.student_checkboxes = {}
        for student_id, name in students:
            assigned_team = self.get_student_team(student_id, lab_slot_id)
            if assigned_team:
                checkbox = QCheckBox(
                    f"{name} ({student_id}) - Team {assigned_team}")
            else:
                checkbox = QCheckBox(f"{name} ({student_id})")
            self.student_checkboxes[student_id] = checkbox
            layout.addWidget(checkbox)

        # Buttons for assignment
        button_layout = QHBoxLayout()

        assign_button = QPushButton("Assign to Team")
        assign_button.clicked.connect(
            lambda: self.assign_selected_students_to_team(
                academic_year_id, lab_slot_id, lab_slot_name))
        button_layout.addWidget(assign_button)

        remove_button = QPushButton("Remove from Team")
        remove_button.clicked.connect(
            lambda: self.remove_students_from_team(lab_slot_id))
        button_layout.addWidget(remove_button)

        complete_button = QPushButton("Complete Assignment")
        complete_button.clicked.connect(self.team_assignment_dialog.accept)
        button_layout.addWidget(complete_button)

        layout.addLayout(button_layout)
        self.team_assignment_dialog.setLayout(layout)
        self.team_assignment_dialog.exec_()

    def get_assigned_students_count(self, lab_slot_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM StudentTeams
            WHERE lab_slot_id=?
        ''', (lab_slot_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_student_team(self, student_id, lab_slot_id):
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT team_number FROM StudentTeams
            WHERE student_id=? AND lab_slot_id=?
        ''', (student_id, lab_slot_id))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        else:
            return None

    def assign_selected_students_to_team(
            self, academic_year_id, lab_slot_id, lab_slot_name):
        # Get selected students
        selected_student_ids = [
            student_id for student_id, checkbox in
            self.student_checkboxes.items() if checkbox.isChecked()]
        if not selected_student_ids:
            QMessageBox.warning(self, "Warning", "No students selected.")
            return

        # Check if number of students is 2 or 3
        if len(selected_student_ids) < 2 or len(selected_student_ids) > 3:
            QMessageBox.warning(
                self, "Warning",
                "You must select 2 or 3 students to form a team.")
            return

        # Fetch existing teams for this lab slot
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT team_number FROM StudentTeams
            WHERE lab_slot_id=?
        ''', (lab_slot_id,))
        existing_teams = cursor.fetchall()
        existing_team_numbers = set([team[0] for team in existing_teams])

        # Determine available team numbers
        max_teams = 9
        all_team_numbers = set(range(1, max_teams + 1))
        available_team_numbers = all_team_numbers - existing_team_numbers

        if not available_team_numbers:
            QMessageBox.warning(self, "Warning", "No available team numbers.")
            conn.close()
            return

        # Let user select a team number
        team_number_strs = [str(num) for num in sorted(available_team_numbers)]
        team_number, ok = QInputDialog.getItem(
            self, "Select Team Number",
            "Available Teams:", team_number_strs, 0, False)
        if not ok:
            conn.close()
            return
        team_number = int(team_number)

        # Check if selected students are already assigned to any team
        students_already_assigned = []
        for student_id in selected_student_ids:
            assigned_team = self.get_student_team(student_id, lab_slot_id)
            if assigned_team:
                students_already_assigned.append((student_id, assigned_team))

        if students_already_assigned:
            overwrite = QMessageBox.question(
                self, "Overwrite Confirmation",
                "Some selected students are already assigned to a team. "
                "Do you want to overwrite their assignments?",
                QMessageBox.Yes | QMessageBox.No)
            if overwrite != QMessageBox.Yes:
                conn.close()
                return
            else:
                # Remove existing assignments for these students
                for student_id, assigned_team in students_already_assigned:
                    cursor.execute('''
                        DELETE FROM StudentTeams
                        WHERE student_id=? AND lab_slot_id=?
                    ''', (student_id, lab_slot_id))

        # Assign students to the selected team number
        for student_id in selected_student_ids:
            cursor.execute('''
                INSERT INTO StudentTeams (team_number, student_id, lab_slot_id)
                VALUES (?, ?, ?)
            ''', (team_number, student_id, lab_slot_id))
            # Update the checkbox label
            self.student_checkboxes[student_id].setText(
                f"{self.student_checkboxes[student_id].text().split(' - Team')[0]}"
                f" - Team {team_number}")
            self.student_checkboxes[student_id].setChecked(False)

        conn.commit()
        conn.close()
        QMessageBox.information(
            self, "Success", "Students assigned to team successfully.")
        # Update the labels
        assigned_students_count = self.get_assigned_students_count(
            lab_slot_id)
        total_students = len(self.student_checkboxes)
        available_students_count = total_students - assigned_students_count
        self.available_students_label.setText(
            f"Available Students: {available_students_count}")
        self.assigned_students_label.setText(
            f"Assigned Students: {assigned_students_count}")

    def remove_students_from_team(self, lab_slot_id):
        # Get selected students
        selected_student_ids = [
            student_id for student_id, checkbox in
            self.student_checkboxes.items() if checkbox.isChecked()]
        if not selected_student_ids:
            QMessageBox.warning(self, "Warning", "No students selected.")
            return

        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        for student_id in selected_student_ids:
            cursor.execute('''
                DELETE FROM StudentTeams
                WHERE student_id=? AND lab_slot_id=?
            ''', (student_id, lab_slot_id))
            # Update the checkbox label
            original_text = self.student_checkboxes[student_id].text().split(
                ' - Team')[0]
            self.student_checkboxes[student_id].setText(original_text)
            self.student_checkboxes[student_id].setChecked(False)
        conn.commit()
        conn.close()
        QMessageBox.information(
            self, "Success", "Selected students removed from their teams.")
        # Update the labels
        assigned_students_count = self.get_assigned_students_count(
            lab_slot_id)
        total_students = len(self.student_checkboxes)
        available_students_count = total_students - assigned_students_count
        self.available_students_label.setText(
            f"Available Students: {available_students_count}")
        self.assigned_students_label.setText(
            f"Assigned Students: {assigned_students_count}")

    def show_teams(self):
        semester, year = self.select_or_add_semester_year()
        if not semester or not year:
            return  # Exit if the user canceled the selection

        # Fetch academic_year_id
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
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
        conn.close()
        if not lab_slots:
            QMessageBox.warning(
                self, "Warning",
                "No lab slots found for the selected academic year.")
            return

        # Let user select a lab slot
        lab_slot_names = [slot[1] for slot in lab_slots]
        lab_slot_name, ok = QInputDialog.getItem(
            self, "Select Lab Slot",
            "Lab Slot:", lab_slot_names, 0, False)
        if not ok:
            return

        # Get lab_slot_id
        lab_slot_id = None
        for slot in lab_slots:
            if slot[1] == lab_slot_name:
                lab_slot_id = slot[0]
                break

        # Fetch teams and students
        conn = sqlite3.connect('student_register.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Students.student_id, Students.name, StudentTeams.team_number
            FROM Students
            INNER JOIN StudentTeams ON Students.student_id = StudentTeams.student_id
            WHERE StudentTeams.lab_slot_id=?
            ORDER BY StudentTeams.team_number, Students.name
        ''', (lab_slot_id,))
        team_data = cursor.fetchall()
        conn.close()
        if not team_data:
            QMessageBox.information(
                self, "Info",
                "No teams assigned for the selected lab slot.")
            return

        # Display teams in a table
        self.show_teams_window = QWidget()
        self.show_teams_window.setWindowTitle(f"Teams for {lab_slot_name}")
        layout = QVBoxLayout(self.show_teams_window)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(
            ["Student ID", "Name", "Team Number"])

        for row_idx, (student_id, name, team_number) in enumerate(team_data):
            table.setRowCount(row_idx + 1)
            table.setItem(
                row_idx, 0, QTableWidgetItem(str(student_id)))
            table.setItem(
                row_idx, 1, QTableWidgetItem(str(name)))
            table.setItem(
                row_idx, 2, QTableWidgetItem(str(team_number)))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        self.show_teams_window.setLayout(layout)
        self.show_teams_window.show()
