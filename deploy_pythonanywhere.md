# Deploying to PythonAnywhere (Free Tier)

PythonAnywhere offers a free tier that includes:
- A web app with your own domain (yourusername.pythonanywhere.com)
- 512MB of storage
- Support for Flask applications
- Free CPU quota sufficient for testing

## Step 1: Create a PythonAnywhere Account

1. Go to [PythonAnywhere](https://www.pythonanywhere.com/) and sign up for a free account

## Step 2: Set Up Your Web App

1. After logging in, go to the **Web** tab
2. Click on **Add a new web app**
3. Choose your domain name (it will be `yourusername.pythonanywhere.com`)
4. Select **Flask** as your web framework
5. Choose **Python 3.8** or newer

## Step 3: Upload Your Code

### Option 1: Upload Using Git
1. Go to the **Consoles** tab
2. Start a new Bash console
3. Clone your repository:
   ```
   git clone https://github.com/natrix77/Lab_Database.git
   ```

### Option 2: Upload Using File Manager
1. Go to the **Files** tab
2. Navigate to your home directory
3. Create a folder called `Lab_Database`
4. Upload your files using the PythonAnywhere file manager

## Step 4: Set Up Your Virtual Environment

1. In a Bash console, create a virtual environment:
   ```
   mkvirtualenv --python=python3.8 lab_env
   ```

2. Activate the virtual environment (if not already activated):
   ```
   workon lab_env
   ```

3. Navigate to your project directory:
   ```
   cd ~/Lab_Database
   ```

4. Install dependencies:
   ```
   pip install -r requirements-web.txt
   ```

## Step 5: Configure Your Web App

1. Go back to the **Web** tab
2. Click on your web app

3. In the **Code** section:
   - Set **Source code** to `/home/yourusername/Lab_Database`
   - Set **Working directory** to `/home/yourusername/Lab_Database`

4. In the **WSGI configuration file** section, click on the link to edit the WSGI file
5. Replace the content with:
   ```python
   import sys
   import os

   # Add your project directory to the Python path
   path = '/home/yourusername/Lab_Database'
   if path not in sys.path:
       sys.path.append(path)

   # Set environment variables
   os.environ['FLASK_ENV'] = 'production'
   os.environ['SECRET_KEY'] = 'your-secret-key-here'

   # Import your Flask app
   from app import app as application
   ```

6. Save the WSGI file

7. In the **Virtualenv** section:
   - Enter the path to your virtual environment: `/home/yourusername/.virtualenvs/lab_env`

8. In the **Static Files** section:
   - Add an entry for URL `/static/` to point to `/home/yourusername/Lab_Database/static`

## Step 6: Initialize the Database

1. Go to the **Consoles** tab
2. Start a new Bash console
3. Activate your virtual environment:
   ```
   workon lab_env
   ```
4. Navigate to your project:
   ```
   cd ~/Lab_Database
   ```
5. Open a Python console:
   ```
   python
   ```
6. Initialize the database:
   ```python
   from app import app, db, init_db
   with app.app_context():
       init_db()
       db.create_all()
   ```
7. Exit the Python console:
   ```python
   exit()
   ```

## Step 7: Reload Your Web App

1. Go back to the **Web** tab
2. Click the green **Reload** button for your web app

## Step 8: Access Your Application

Your app should now be available at:
```
https://yourusername.pythonanywhere.com
```

## Limitations of the Free Tier

- Your app will be put to sleep after a period of inactivity (around 3 months)
- CPU time is limited (but sufficient for testing)
- You can only have one web app
- The domain name is provided by PythonAnywhere
- SQLite usage is allowed, but PostgreSQL requires a paid account

## Troubleshooting

1. **Check Error Logs**: If your app doesn't work, check the error logs in the **Web** tab
2. **Reload After Changes**: Always reload your web app after making changes
3. **Check File Permissions**: Ensure your files have the correct permissions
4. **Database Path**: Make sure the SQLite database path is absolute in your app configuration 