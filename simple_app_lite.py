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

# Database path with fallback and debug info
DB_PATH = os.environ.get('DATABASE_PATH', 'student_register.db')
print(f"Using database path: {DB_PATH}")
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
            # Ensure directory exists
            db_dir = os.path.dirname(app.config['DATABASE'])
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"Created database directory: {db_dir}")
                
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
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def modify_db(query, args=()):
    db = get_db()
    db.execute(query, args)
    db.commit()

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
                flash('Invalid username or password', 'danger')
        except Exception as e:
            error_msg = f'Login error: {str(e)}'
            flash(error_msg, 'danger')
            print(error_msg)
    
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
        }
    })

# Debug route to check database access
@app.route('/debug/database')
def debug_database():
    # Only allow in development
    if not app.debug and not os.environ.get('RENDER_DEBUG', '0') == '1':
        return "Debug endpoints disabled in production", 403
    
    info = {
        'database_path': app.config['DATABASE'],
        'path_exists': os.path.exists(app.config['DATABASE']),
        'directory': os.path.dirname(app.config['DATABASE']),
        'directory_exists': os.path.exists(os.path.dirname(app.config['DATABASE']) or '.'),
        'environment': dict(os.environ),
        'current_directory': os.getcwd(),
        'directory_contents': []
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
    
    return jsonify(info)

# Initialize database when the app is loaded
with app.app_context():
    try:
        # Ensure database directory exists
        db_path = app.config['DATABASE']
        db_dir = os.path.dirname(db_path)
        
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                print(f"Created database directory: {db_dir}")
            except Exception as e:
                print(f"Error creating database directory: {e}")
        
        # Ensure database file exists
        if not os.path.exists(db_path):
            open(db_path, 'a').close()
            print(f"Created empty database file: {db_path}")
        
        # Initialize tables
        init_users_table()
    except Exception as e:
        print(f"Error during app initialization: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050) 