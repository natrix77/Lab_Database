# Tabs/help_tab.py
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QMessageBox, QTextEdit

class HelpTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.help_button = QPushButton("Show Help")
        self.help_button.clicked.connect(self.show_help)

        layout = QVBoxLayout()
        layout.addWidget(self.help_button)
        self.setLayout(layout)

    def show_help(self):
        help_text = """
        [Insert the help text describing the functionality of each tab here.]
        """
        help_dialog = QMessageBox(self)
        help_dialog.setWindowTitle("Help")
        help_dialog.setText(help_text)
        help_dialog.exec_()
