# main.py

import sys
from PyQt5.QtWidgets import QApplication, QTabWidget, QWidget, QVBoxLayout, QPushButton
from Tabs.create_update_db import CreateUpdateDBTab
from Tabs.import_students import ImportStudentsTab
from Tabs.assign_teams import AssignTeamsTab
from Tabs.record_attendance import RecordAttendanceTab
from Tabs.insert_grades import InsertGradesTab
from Tabs.export_data import ExportDataTab
from Tabs.help_tab import HelpTab
from Tabs.manage_students import ManageStudentsTab  # Import the new Manage Students tab
from Tabs.exit_tab import ExitTab


class MainApp(QTabWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Student Register Book")

        # Add tabs to the application
        self.addTab(CreateUpdateDBTab(), "Create/Update DB")
        self.addTab(ImportStudentsTab(), "Import Students")
        self.addTab(AssignTeamsTab(), "Assign Teams")
        self.addTab(RecordAttendanceTab(), "Record Attendance")
        self.addTab(InsertGradesTab(), "Insert Grades")
        self.addTab(ExportDataTab(), "Export Data")
        self.addTab(ManageStudentsTab(), "Manage Students")  # Add the new tab here
        self.addTab(HelpTab(), "Help")
        self.addTab(ExitTab(), "Exit")


def main():
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
