# Lab Database Simple Instructions

This simplified approach focuses only on using `simple_app.py` for the lab management system.

## How to Start the Application

1. Double-click on `start_simple.bat`

This will:
- Fix any exercise slot naming issues in the database (Ε1 → Lab1, etc.)
- Launch the web application
- Open your browser to http://localhost:5000

## If You Have Problems

If you encounter any issues:

1. Make sure Python is installed and available in your PATH
2. Run `simple_launch.py` directly with Python:
   ```
   python simple_launch.py
   ```
3. Check the error messages that appear in the console

## Database Issues

If you're seeing database problems, you can:

1. Run the database fix script separately:
   ```
   python simple_fix.py
   ```

2. Or use the SQL scripts directly:
   ```
   sqlite3 student_register.db < fix_exercises.sql
   ```

## URL Routing Issues

If you encounter "BuildError: Could not build url for endpoint" errors:
- Make sure your templates use the exact endpoint names from simple_app.py
- Use trailing slashes consistently in both route definitions and templates 