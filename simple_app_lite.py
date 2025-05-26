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

# FORCE in-memory database regardless of environment settings
# This is a hard override to fix deployment issues
print("NOTICE: Forcing in-memory database usage for reliability")
app.config['DATABASE'] = ":memory:"

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
            # Always connect to in-memory database
            db = g._database = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
            
            # Always initialize tables for in-memory DB
            init_tables(db)
            print("Connected to in-memory database with initialized tables")
            
            return db
        except Exception as e:
            print(f"Database connection error: {e}")
            raise
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

# Initialize all database tables
def init_tables(conn=None):
    try:
        if conn is None:
            db = get_db()
        else:
            db = conn
            
        cursor = db.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        # Check if default admin exists
        cursor.execute('SELECT * FROM users WHERE username = ?', [DEFAULT_USERNAME])
        admin = cursor.fetchone()
        
        if not admin:
            # Add default admin user
            hashed_password = generate_password_hash(DEFAULT_PASSWORD)
            cursor.execute(
                'INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)',
                [DEFAULT_USERNAME, hashed_password]
            )
            print("Added default admin user")
        
        # Commit changes
        if conn is None:
            db.commit()
            
        print("Database tables initialized")
        return True
    except Exception as e:
        print(f"Error initializing tables: {e}")
        return False

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
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
    
    # If there's a database error, provide simplified login page
    if error and "database" in error.lower():
        return f"""
        <html>
        <head>
            <title>Lab Database - Login</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .container {{ max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
                h1 {{ color: #2c3e50; }}
                .error {{ background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
                .form-group {{ margin-bottom: 15px; }}
                label {{ display: block; margin-bottom: 5px; }}
                input[type="text"], input[type="password"] {{ width: 100%; padding: 8px; box-sizing: border-box; }}
                button {{ background-color: #007bff; color: white; border: none; padding: 10px 15px; cursor: pointer; }}
                .debug {{ margin-top: 20px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Student Register Book</h1>
                
                <div class="error">
                    <p><strong>Database Error:</strong> {error}</p>
                    <p>Using in-memory database mode. Any changes will be lost when the application restarts.</p>
                </div>
                
                <form method="post">
                    <div class="form-group">
                        <label>Username:</label>
                        <input type="text" name="username" value="admin">
                    </div>
                    <div class="form-group">
                        <label>Password:</label>
                        <input type="password" name="password" value="admin123">
                    </div>
                    <button type="submit">Login</button>
                </form>
                
                <div class="debug">
                    <p>Current database: {app.config['DATABASE']}</p>
                    <p><a href="/debug/database">View Database Debug Info</a></p>
                </div>
            </div>
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
            'in_memory': app.config['DATABASE'] == ':memory:',
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
    info = {
        'database_path': app.config['DATABASE'],
        'in_memory': app.config['DATABASE'] == ':memory:',
        'environment': dict([(k,v) for k,v in os.environ.items() if 'PATH' in k or 'DATABASE' in k or 'RENDER' in k or 'PYTHON' in k]),
        'current_directory': os.getcwd(),
    }
    
    # If not in-memory, check file access
    if app.config['DATABASE'] != ':memory:':
        info['path_exists'] = os.path.exists(app.config['DATABASE'])
        info['directory'] = os.path.dirname(app.config['DATABASE'])
        info['directory_exists'] = os.path.exists(os.path.dirname(app.config['DATABASE']) or '.')
        
        # List directory contents
        try:
            dir_to_check = os.path.dirname(app.config['DATABASE']) or '.'
            if os.path.exists(dir_to_check):
                info['directory_contents'] = os.listdir(dir_to_check)
        except Exception as e:
            info['directory_error'] = str(e)
    
    # Check database connection
    try:
        user_count = query_db('SELECT COUNT(*) as count FROM users', one=True)
        info['connection_test'] = 'success'
        info['user_count'] = user_count['count'] if user_count else 0
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
    html = f"""
    <html>
    <head>
        <title>Database Debug Info</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
            h1, h2 {{ color: #2c3e50; }}
            pre {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; overflow: auto; }}
            .actions {{ margin: 20px 0; }}
            button {{ background-color: #007bff; color: white; border: none; padding: 10px 15px; cursor: pointer; margin-right: 10px; }}
            .memory-notice {{ background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h1>Database Debug Info</h1>
        
        {'''<div class="memory-notice">
            <strong>Notice:</strong> Using in-memory database. All data will be lost when the application restarts.
        </div>''' if app.config['DATABASE'] == ':memory:' else ''}
        
        <pre>{json.dumps(info, indent=2)}</pre>
        
        <div class="actions">
            <form action="/debug/create_test_table" method="post" style="display: inline;">
                <button type="submit">Create Test Table</button>
            </form>
            
            <form action="/debug/add_test_user" method="post" style="display: inline;">
                <button type="submit">Add Test User</button>
            </form>
            
            <a href="/"><button type="button">Go to App</button></a>
        </div>
    </body>
    </html>
    """
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
        flash("Test table created successfully", "success")
        return redirect('/debug/database')
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/debug/add_test_user', methods=['POST'])
def add_test_user():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Create a test user
        test_username = f"test_user_{datetime.now().strftime('%H%M%S')}"
        hashed_password = generate_password_hash("password123")
        
        cursor.execute(
            'INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)',
            [test_username, hashed_password]
        )
        
        conn.commit()
        flash(f"Test user '{test_username}' created with password 'password123'", "success")
        return redirect('/debug/database')
    except Exception as e:
        return f"Error: {str(e)}"

# Initialize app when loaded - IMPORTANT: This is where things were failing
with app.app_context():
    print("Initializing application database...")
    # Always use in-memory database
    try:
        # Initialize in-memory database
        init_tables()
        print("Successfully initialized in-memory database")
    except Exception as e:
        print(f"ERROR during app initialization: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050) 