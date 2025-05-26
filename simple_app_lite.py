# Lightweight version without pandas dependency
import os
import sqlite3
import json
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, g, send_file, session
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')

# Try multiple database locations
if os.environ.get('RENDER'):
    # For Render.com deployment
    DB_LOCATIONS = [
        os.environ.get('DATABASE_PATH', '/data/student_register.db'),  # Disk mount location
        '/tmp/student_register.db',  # Temp directory (always writable)
        'student_register.db'  # Local to app directory
    ]
else:
    # For local development
    DB_LOCATIONS = [
        os.environ.get('DATABASE_PATH', 'student_register.db')
    ]

# Try each location until one works
DB_PATH = None
for location in DB_LOCATIONS:
    try:
        print(f"Trying database location: {location}")
        db_dir = os.path.dirname(location)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"Created directory: {db_dir}")
        
        # Test if we can write to this location
        with open(location, 'a') as f:
            pass
        
        # Location works, use it
        DB_PATH = location
        print(f"Using database path: {DB_PATH}")
        break
    except Exception as e:
        print(f"Location {location} not usable: {e}")

# If no location works, fall back to in-memory
if not DB_PATH:
    print("WARNING: No writable database location found, using in-memory database")
    DB_PATH = ":memory:"

app.config['DATABASE'] = DB_PATH

# Default admin credentials
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin123'

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Database helper functions
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        try:
            db = g._database = sqlite3.connect(app.config['DATABASE'])
            db.row_factory = sqlite3.Row
            print(f"Successfully connected to database: {app.config['DATABASE']}")
        except Exception as e:
            print(f"Database connection error: {e}")
            # Fallback to in-memory database in case of issues
            print("Falling back to in-memory database")
            db = g._database = sqlite3.connect(':memory:')
            db.row_factory = sqlite3.Row
            # Initialize in-memory DB
            init_users_table(db)
    return db

def query_db(query, args=(), one=False):
    try:
        cur = get_db().execute(query, args)
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"Query error: {e}")
        return None if one else []

def modify_db(query, args=()):
    try:
        db = get_db()
        db.execute(query, args)
        db.commit()
        return True
    except Exception as e:
        print(f"Modify error: {e}")
        return False

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Initialize the users table
def init_users_table(conn=None):
    try:
        if conn is None:
            db_path = app.config['DATABASE']
            print(f"Initializing users table in {db_path}")
            db = sqlite3.connect(db_path)
        else:
            db = conn
            
        cursor = db.cursor()
        
        # Check if the Users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        
        if not result:
            # Create the Users table
            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0
                )
            ''')
            
            # Add default admin user
            hashed_password = generate_password_hash(DEFAULT_PASSWORD)
            cursor.execute(
                'INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)',
                [DEFAULT_USERNAME, hashed_password]
            )
            print("Users table created with default admin user")
        
        if conn is None:
            db.commit()
            db.close()
    except Exception as e:
        print(f"Error initializing users table: {e}")

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            # Use get_db() to ensure consistency and fallback capability
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE username = ?', [username])
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                session['logged_in'] = True
                session['username'] = username
                session['is_admin'] = user['is_admin']
                
                next_page = request.args.get('next')
                flash('Login successful', 'success')
                return redirect(next_page or url_for('dashboard'))
            else:
                error = 'Invalid username or password'
                flash(error, 'danger')
        except Exception as e:
            error = f'Login error: {str(e)}'
            flash(error, 'danger')
            print(error)
    
    # Simplified login page if there's an error
    if error and "unable to open database" in error.lower():
        return f"""
        <html>
        <body>
            <h1>Database Access Error</h1>
            <p>{error}</p>
            <p>Current database path: {app.config['DATABASE']}</p>
            <p>This is likely a temporary issue with the database storage.</p>
            <p><a href="/debug/database">View Database Debug Info</a></p>
            <form method="post">
                <h2>Login</h2>
                <p>Username: <input type="text" name="username" value="admin"></p>
                <p>Password: <input type="password" name="password" value="admin123"></p>
                <p><input type="submit" value="Login"></p>
            </form>
        </body>
        </html>
        """
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Home route
@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard/index.html', stats={}, academic_years=[])

# Health check API
@app.route('/api/health')
def health_check():
    # Report database status in health check
    db_status = 'ok'
    db_error = None
    try:
        # Test database connection
        query_db('SELECT 1', one=True)
    except Exception as e:
        db_status = 'error'
        db_error = str(e)
    
    return jsonify({
        'status': 'ok', 
        'version': '1.0.0',
        'database': {
            'status': db_status,
            'path': app.config['DATABASE'],
            'error': db_error
        },
        'environment': {
            'render': os.environ.get('RENDER', 'Not set'),
            'tmp_dir_exists': os.path.exists('/tmp'),
            'data_dir_exists': os.path.exists('/data'),
            'current_dir': os.getcwd()
        }
    })

# Debug route to check database access
@app.route('/debug/database')
def debug_database():
    # Debug endpoints available in all environments now
    info = {
        'database_path': app.config['DATABASE'],
        'path_exists': os.path.exists(app.config['DATABASE']),
        'directory': os.path.dirname(app.config['DATABASE']),
        'directory_exists': os.path.exists(os.path.dirname(app.config['DATABASE']) or '.'),
        'environment': dict([(k,v) for k,v in os.environ.items() if 'PATH' in k or 'DATABASE' in k or 'RENDER' in k or 'PYTHON' in k]),
        'current_directory': os.getcwd(),
        'directory_contents': [],
        'tried_paths': DB_LOCATIONS
    }
    
    # List directory contents
    try:
        dir_to_check = os.path.dirname(app.config['DATABASE']) or '.'
        if os.path.exists(dir_to_check):
            info['directory_contents'] = os.listdir(dir_to_check)
    except Exception as e:
        info['directory_error'] = str(e)
    
    # Check database connection
    try:
        query_db('SELECT 1', one=True)
        info['connection_test'] = 'success'
    except Exception as e:
        info['connection_test'] = f'error: {str(e)}'
    
    # Check common directories
    for test_dir in ['/tmp', '/data', '/app']:
        try:
            if os.path.exists(test_dir):
                info[f'{test_dir}_exists'] = True
                info[f'{test_dir}_writable'] = os.access(test_dir, os.W_OK)
                info[f'{test_dir}_contents'] = os.listdir(test_dir)
            else:
                info[f'{test_dir}_exists'] = False
        except Exception as e:
            info[f'{test_dir}_error'] = str(e)
    
    # Return HTML for easier viewing
    html = "<html><body><h1>Database Debug Info</h1><pre>"
    html += json.dumps(info, indent=2)
    html += "</pre>"
    
    # Add test create button
    html += """
    <h2>Actions</h2>
    <form action="/debug/create_test_table" method="post">
        <button type="submit">Create Test Table</button>
    </form>
    """
    
    html += "</body></html>"
    return html

@app.route('/debug/create_test_table', methods=['POST'])
def create_test_table():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Create a test table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                message TEXT
            )
        ''')
        
        # Add a test row
        cursor.execute(
            'INSERT INTO test_table (timestamp, message) VALUES (?, ?)',
            [datetime.now().isoformat(), f"Test entry from {os.environ.get('RENDER', 'local')}"]
        )
        
        conn.commit()
        return redirect('/debug/database')
    except Exception as e:
        return f"Error: {str(e)}"

# Initialize database when the app is loaded
with app.app_context():
    try:
        # Initialize tables
        init_users_table()
    except Exception as e:
        print(f"Error during app initialization: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050) 