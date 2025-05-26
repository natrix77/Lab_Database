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
app.config['DATABASE'] = os.environ.get('DATABASE_PATH', 'student_register.db')

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
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
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
def init_users_table():
    try:
        db = sqlite3.connect(app.config['DATABASE'])
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
            conn = sqlite3.connect(app.config['DATABASE'])
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM users WHERE username = ?', [username])
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                session['logged_in'] = True
                session['username'] = username
                session['is_admin'] = user['is_admin']
                
                next_page = request.args.get('next')
                flash('Login successful', 'success')
                conn.close()
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
            
            conn.close()
        except Exception as e:
            flash(f'Login error: {str(e)}', 'danger')
            print(f"Login error: {e}")
    
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
    return jsonify({'status': 'ok', 'version': '1.0.0'})

# Initialize database when the app is loaded
with app.app_context():
    try:
        # Ensure database file exists
        if not os.path.exists(app.config['DATABASE']):
            open(app.config['DATABASE'], 'a').close()
            print(f"Created empty database file: {app.config['DATABASE']}")
        
        # Initialize tables
        init_users_table()
    except Exception as e:
        print(f"Error during app initialization: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050) 