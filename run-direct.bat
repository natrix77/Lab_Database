@echo off
echo Starting Student Register Book Web Application (Direct Mode)...

REM Remove the old SQLAlchemy if it exists
pip uninstall -y sqlalchemy

REM Install a compatible SQLAlchemy version
pip install flask==3.0.2 sqlalchemy==2.0.27 pandas==2.2.3 openpyxl==3.1.5

REM Run the simplified application
echo Running simplified application...
python simple_app.py

pause 