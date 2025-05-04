@echo off
echo Fixing exercise slot names in the database...

REM Check if sqlite3 is available
WHERE sqlite3 >nul 2>nul
IF %ERRORLEVEL% EQU 0 (
    echo Using sqlite3 command...
    echo .read fix_exercises.sql | sqlite3 student_register.db
) ELSE (
    echo sqlite3 command not found, using Python instead...
    echo import sqlite3; conn = sqlite3.connect('student_register.db'); cursor = conn.cursor(); script = open('fix_exercises.sql').read(); cursor.executescript(script); conn.commit(); conn.close(); print('SQL script executed successfully!') > run_sql.py
    python run_sql.py
    if %ERRORLEVEL% NEQ 0 (
        echo Python execution failed, please run fix_exercises.sql manually with SQLite
    )
)

echo Done! 