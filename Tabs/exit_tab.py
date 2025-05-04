# Tabs/exit_tab.py
from PyQt5.QtWidgets import QWidget, QPushButton, QVBoxLayout, QApplication

class ExitTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.exit_app)

        layout = QVBoxLayout()
        layout.addWidget(self.exit_button)
        self.setLayout(layout)

    def exit_app(self):
        QApplication.quit()
