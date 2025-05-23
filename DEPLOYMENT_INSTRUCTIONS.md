# Lab Database Deployment Instructions

## Features Added

1. **Login Security Feature**
   - Username and password protection for all application routes
   - Default credentials: admin/admin123
   - Session management
   - Logout functionality

## How to Deploy to Git

1. **Backup Your Code**
   - A backup of the original application has been created at: `backups/simple_app.pyw.backup_login_feature`

2. **Test the Changes Locally**
   - Run the application using `start_simple.bat`
   - Verify the login functionality works correctly
   - Test that all routes are protected and require authentication

3. **Commit and Push to Git**

   ```bash
   # Make sure you're in the project directory
   cd C:\NewAI\Lab_Database

   # Check which files are modified/added
   git status

   # Stage the modified and new files
   git add simple_app.pyw
   git add templates/login.html
   git add add_login_required.py
   git add start_simple.bat
   git add DEPLOYMENT_INSTRUCTIONS.md
   
   # Add any other new or modified files as needed
   # git add <file_path>

   # Commit the changes with a descriptive message
   git commit -m "Add login security feature to protect application routes"

   # Push the changes to the remote repository
   git push origin main
   ```

4. **Post-Deployment Verification**
   - If you are hosting the application on a server, pull the changes there
   - Verify the login functionality works in the production environment

## Security Notes

1. **Default Credentials**
   - The default username and password (admin/admin123) should be changed immediately after deployment
   - You can modify the credentials directly in the database or add a password change feature
   
2. **Session Security**
   - Sessions are managed using Flask's built-in session capabilities
   - Session data is encrypted using a randomly generated secret key
   - The secret key is regenerated every time the application starts

3. **Protected Routes**
   - All routes now require authentication
   - Unauthorized access attempts are redirected to the login page

## Password Change Instructions

To change the default admin password:

1. Connect to the database:
   ```
   sqlite3 student_register.db
   ```

2. Generate a new password hash (you can use Python):
   ```python
   from werkzeug.security import generate_password_hash
   print(generate_password_hash("your_new_password"))
   # Copy the output hash
   ```

3. Update the password in the database:
   ```sql
   UPDATE Users 
   SET password_hash = 'paste_new_password_hash_here' 
   WHERE username = 'admin';
   ```

4. Exit SQLite:
   ```
   .quit
   ``` 