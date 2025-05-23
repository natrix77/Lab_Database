import os
import sqlite3
import pandas as pd
import webbrowser
import threading
import time
import json
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, g, send_file, session
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from create_grade_template import create_grade_template

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['DATABASE'] = 'student_register.db'

# Default admin credentials (you should change these)
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
        
        # Check if the Users table exists - using lowercase 'users' to match the error message
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        result = cursor.fetchone()
        
        if not result:
            # Create the Users table - use lowercase 'users' for consistency
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

# Call this function when the app starts
init_users_table()

# Login routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            # Direct database connection to avoid context issues
            conn = sqlite3.connect(app.config['DATABASE'])
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query using lowercase table name
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
    """Redirect the root URL to the dashboard page."""
    print("Root URL accessed, redirecting to dashboard")
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

# Dashboard route
@app.route('/dashboard')
@login_required
@login_required
def dashboard():
    """Dashboard route that displays statistics and charts."""
    # Log that we've entered the dashboard route
    print("Dashboard route accessed")
    
    # Get filter parameters
    academic_year_id = request.args.get('academic_year_id', type=int)
    print(f"academic_year_id: {academic_year_id}")
    
    # Get basic statistics
    stats = {}
    
    # Initialize variables that might not be set in all code paths
    avg_grades_by_exercise = []
    team_counts = []
    absences_by_lab = []
    lab_slots_by_year = {}
    exam_slots_by_year = {}
    
    # Apply filters to database queries if academic_year_id is provided
    if academic_year_id:
        # Get the selected academic year
        selected_academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                                        [academic_year_id], one=True)
        
        # Count students, lab slots, and absences for the selected academic year
        stats['total_students'] = query_db(
            'SELECT COUNT(DISTINCT s.student_id) as count FROM Students s JOIN Enrollments e ON s.student_id = e.student_id WHERE e.academic_year_id = ?', 
            [academic_year_id], 
            one=True
        )['count']
        
        stats['total_lab_slots'] = query_db(
            'SELECT COUNT(*) as count FROM LabSlots WHERE academic_year_id = ?', 
            [academic_year_id], 
            one=True
        )['count']
        
        stats['total_exam_slots'] = query_db(
            'SELECT COUNT(*) as count FROM ExamSlots WHERE academic_year_id = ?', 
            [academic_year_id], 
            one=True
        )['count']
        
        stats['absences'] = query_db(
            'SELECT COUNT(*) as count FROM Attendance WHERE status = "Absent" AND academic_year_id = ?', 
            [academic_year_id], 
            one=True
        )['count']
        
        # Get lab slots for the selected academic year
        lab_slots = query_db('''
            SELECT 
                LabSlots.id, 
                LabSlots.name, 
                (SELECT COUNT(*) FROM Enrollments WHERE Enrollments.lab_slot_id = LabSlots.id) as student_count,
                (SELECT COUNT(*) FROM Attendance WHERE Attendance.lab_slot_id = LabSlots.id AND Attendance.status = 'Absent') as absences_count
            FROM LabSlots
            WHERE LabSlots.academic_year_id = ?
        ''', [academic_year_id])
        
        # Get exam slots for the selected academic year
        exam_slots = query_db('''
            SELECT 
                ExamSlots.id, 
                ExamSlots.name,
                ExamSlots.date,
                ExamSlots.time,
                ExamSlots.location,
                (SELECT COUNT(*) FROM ExamEnrollments WHERE ExamEnrollments.exam_slot_id = ExamSlots.id) as student_count
            FROM ExamSlots
            WHERE ExamSlots.academic_year_id = ?
        ''', [academic_year_id])
        
        year_key = f"{selected_academic_year['semester']} {selected_academic_year['year']}"
        lab_slots_by_year = {year_key: lab_slots}
        exam_slots_by_year = {year_key: exam_slots}
        
        # Get final grades distribution for the selected academic year
        final_grades_stats = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'average': 0,
            'distribution': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 0-1, 1-2, ..., 9-10
        }
        
        # Get students with their enrollment info
        students = query_db('''
            SELECT DISTINCT
                s.student_id, 
                s.name
            FROM 
                Students s
            JOIN 
                Enrollments e ON s.student_id = e.student_id
            WHERE 
                e.academic_year_id = ?
            ORDER BY 
                s.name
        ''', [academic_year_id])
        
        total_final_grade = 0
        failed_students = set()  # Track students who have failed
        
        for student in students:
            student_id = student['student_id']
            
            # Get exercise grades
            exercise_grades = query_db('''
                SELECT grade, exercise_slot
                FROM Grades
                WHERE student_id = ? AND academic_year_id = ?
            ''', [student_id, academic_year_id])
            
            # Calculate average of exercise grades
            avg_exercise_grade = 0
            if exercise_grades:
                total = sum(grade['grade'] for grade in exercise_grades)
                avg_exercise_grade = round(total / len(exercise_grades), 2)
            
            # Get exam grades
            exam_grade = query_db('''
                SELECT eg.grade
                FROM ExamGrades eg
                JOIN ExamSlots es ON eg.exam_slot_id = es.id
                WHERE eg.student_id = ? AND es.academic_year_id = ?
            ''', [student_id, academic_year_id], one=True)
            
            exam_grade_value = exam_grade['grade'] if exam_grade else 0
            
            # Calculate final grade according to the formula
            final_grade = 0
            if exam_grade_value >= 5:
                # If exam grade is >= 5, final grade is 25% exercises + 75% exam
                final_grade = round(0.25 * avg_exercise_grade + 0.75 * exam_grade_value, 2)
            else:
                # If exam grade is < 5, final grade is 25% of exercises only
                final_grade = round(0.25 * avg_exercise_grade, 2)
            
            # Update statistics
            final_grades_stats['total'] += 1
            total_final_grade += final_grade
            
            if final_grade >= 5:
                final_grades_stats['passed'] += 1
            else:
                final_grades_stats['failed'] += 1
                failed_students.add(student_id)  # Add to failed students set
            
            # Update distribution
            bin_index = min(int(final_grade), 9)
            final_grades_stats['distribution'][bin_index] += 1
        
        # Calculate average final grade
        if final_grades_stats['total'] > 0:
            final_grades_stats['average'] = total_final_grade / final_grades_stats['total']
        
        # Get absences by lab slot for chart for the selected academic year
        absences_by_lab = query_db('''
            SELECT 
                l.name as lab_name, 
                COUNT(*) as absent_count
            FROM 
                Attendance a
            JOIN 
                LabSlots l ON a.lab_slot_id = l.id
            WHERE 
                a.status = 'Absent'
                AND a.academic_year_id = ?
            GROUP BY 
                l.id
            ORDER BY 
                absent_count DESC
            LIMIT 10
        ''', [academic_year_id])
        
        # Get average grades by exercise for the selected academic year
        avg_grades_by_exercise = query_db('''
            SELECT 
                exercise_slot as exercise_name, 
                ROUND(CAST(AVG(grade) AS REAL), 2) as avg_grade
            FROM 
                Grades
            WHERE 
                academic_year_id = ?
            GROUP BY 
                exercise_slot
            ORDER BY 
                exercise_slot
        ''', [academic_year_id])
        
        # Debug print the grades
        print(f"Average grades for academic year {academic_year_id}:")
        for grade in avg_grades_by_exercise:
            print(f"  {grade['exercise_name']}: {grade['avg_grade']}")
    else:
        # No filter, get all statistics
        selected_academic_year = None
        
        # Count students, lab slots, and absences
        stats['total_students'] = query_db('SELECT COUNT(*) as count FROM Students', one=True)['count']
        stats['total_lab_slots'] = query_db('SELECT COUNT(*) as count FROM LabSlots', one=True)['count']
        stats['total_exam_slots'] = query_db('SELECT COUNT(*) as count FROM ExamSlots', one=True)['count']
        stats['absences'] = query_db('SELECT COUNT(*) as count FROM Attendance WHERE status = "Absent"', one=True)['count']
        
        # Initialize final grades stats
        final_grades_stats = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'average': 0,
            'distribution': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 0-1, 1-2, ..., 9-10
        }
        
        # Get academic years
        academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
        
        # Get lab slots by academic year
        lab_slots_by_year = {}
        exam_slots_by_year = {}
        for year in academic_years:
            lab_slots = query_db('''
                SELECT 
                    LabSlots.id, 
                    LabSlots.name, 
                    (SELECT COUNT(*) FROM Enrollments WHERE Enrollments.lab_slot_id = LabSlots.id) as student_count,
                    (SELECT COUNT(*) FROM Attendance WHERE Attendance.lab_slot_id = LabSlots.id AND Attendance.status = 'Absent') as absences_count
                FROM LabSlots
                WHERE LabSlots.academic_year_id = ?
            ''', [year['id']])
            
            # Get exam slots for this academic year
            exam_slots = query_db('''
                SELECT 
                    ExamSlots.id, 
                    ExamSlots.name,
                    ExamSlots.date,
                    ExamSlots.time,
                    ExamSlots.location,
                    (SELECT COUNT(*) FROM ExamEnrollments WHERE ExamEnrollments.exam_slot_id = ExamSlots.id) as student_count
                FROM ExamSlots
                WHERE ExamSlots.academic_year_id = ?
            ''', [year['id']])
            
            year_key = f"{year['semester']} {year['year']}"
            lab_slots_by_year[year_key] = lab_slots
            exam_slots_by_year[year_key] = exam_slots
        
        # Get team distribution
        team_counts = query_db('''
            SELECT LabSlots.name, COUNT(DISTINCT StudentTeams.team_number) as count
            FROM StudentTeams
            JOIN LabSlots ON StudentTeams.lab_slot_id = LabSlots.id
            GROUP BY LabSlots.name
        ''')
        
        # Get absences by lab slot for chart
        absences_by_lab = query_db('''
            SELECT 
                l.name as lab_name, 
                COUNT(*) as absent_count
            FROM 
                Attendance a
            JOIN 
                LabSlots l ON a.lab_slot_id = l.id
            WHERE 
                a.status = 'Absent'
            GROUP BY 
                l.id
            ORDER BY 
                absent_count DESC
            LIMIT 10
        ''')
    
    # Get all academic years for the filter dropdown
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    
    return render_template(
        'dashboard/index.html',
        academic_years=academic_years,
        selected_academic_year=selected_academic_year,
        total_students=stats['total_students'],
        total_lab_slots=stats['total_lab_slots'],
        total_exam_slots=stats['total_exam_slots'],
        absences=stats['absences'],
        lab_slots_by_academic_year=lab_slots_by_year,
        exam_slots_by_academic_year=exam_slots_by_year,
        absences_by_lab=absences_by_lab,
        avg_grades_by_exercise=avg_grades_by_exercise,
        final_grades_stats=final_grades_stats
    )

# Update the URL routes for dashboard in base.html
@app.context_processor
def inject_globals():
    return {
        'request': request
    }

# Academic Year routes
@app.route('/academic/')
@login_required
def academic_year_index():
    # Get all academic years
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    return render_template('academic/index.html', academic_years=academic_years)

@app.route('/academic/create/', methods=['GET', 'POST'])
@login_required
def academic_year_create():
    if request.method == 'POST':
        semester = request.form.get('semester')
        year = request.form.get('year')
        
        # Validate inputs
        if not semester or not year:
            flash('Please provide both semester and year', 'danger')
            return redirect(url_for('academic_year_create'))
        
        # Check if already exists
        existing = query_db(
            'SELECT id FROM AcademicYear WHERE semester=? AND year=?', 
            [semester, int(year)], 
            one=True
        )
        
        if existing:
            flash(f'Academic year {semester} {year} already exists', 'warning')
            return redirect(url_for('academic_year_index'))
            
        # Create new academic year
        modify_db(
            'INSERT INTO AcademicYear (semester, year) VALUES (?, ?)',
            [semester, int(year)]
        )
        
        flash(f'Academic year {semester} {year} created successfully', 'success')
        return redirect(url_for('academic_year_index'))
        
    return render_template('academic/create.html')

# Students routes
@app.route('/students/')
@login_required
def students_index():
    # Get all students with counts of enrollments and teams
    students = query_db('''
        SELECT 
            s.student_id, 
            s.name, 
            s.email, 
            s.username,
            COUNT(DISTINCT e.academic_year_id) as enrolled_years_count,
            COUNT(DISTINCT st.team_number) as teams_count
        FROM 
            Students s
        LEFT JOIN 
            Enrollments e ON s.student_id = e.student_id
        LEFT JOIN 
            StudentTeams st ON s.student_id = st.student_id
        GROUP BY 
            s.student_id
        ORDER BY s.name
    ''')
    
    return render_template('students/index.html', students=students)

@app.route('/students/import/', methods=['GET', 'POST'])
@login_required
def students_import():
    if request.method == 'POST':
        # Check if a file was submitted
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
            
        academic_year_id = request.form.get('academic_year_id')
        if not academic_year_id:
            flash('Please select an academic year', 'danger')
            return redirect(request.url)
            
        try:
            # Read Excel file
            df = pd.read_excel(file, header=None)
            
            # Extract lab slot name from cell A1
            lab_slot_name = df.iloc[0, 0]
            
            # Set column names from row 3 (index 2)
            df.columns = df.iloc[2]
            
            # Drop first three rows (indices 0, 1, 2)
            df = df.drop([0, 1, 2]).reset_index(drop=True)
            
            # Create 'Student_Name' by combining 'Επώνυμο' and 'Όνομα'
            df['Student_Name'] = df['Επώνυμο'] + ' ' + df['Όνομα']
            
            # Check if lab slot exists
            lab_slot = query_db(
                'SELECT id FROM LabSlots WHERE name=? AND academic_year_id=?',
                [lab_slot_name, academic_year_id],
                one=True
            )
            
            if lab_slot:
                # Ask if user wants to replace data
                replace = request.form.get('replace_data') == 'on'
                
                if replace:
                    # Delete existing enrollments for this lab slot
                    modify_db('DELETE FROM Enrollments WHERE lab_slot_id=?', [lab_slot['id']])
                    
                    # Delete the lab slot
                    modify_db('DELETE FROM LabSlots WHERE id=?', [lab_slot['id']])
                    
                    # Create new lab slot
                    modify_db(
                        'INSERT INTO LabSlots (name, academic_year_id) VALUES (?, ?)',
                        [lab_slot_name, academic_year_id]
                    )
                    lab_slot_id = query_db(
                        'SELECT last_insert_rowid() as id', one=True
                    )['id']
                else:
                    flash(f'Lab slot {lab_slot_name} already exists. Please check "Replace existing data" if you want to replace it.', 'warning')
                    return redirect(request.url)
            else:
                # Create new lab slot
                modify_db(
                    'INSERT INTO LabSlots (name, academic_year_id) VALUES (?, ?)',
                    [lab_slot_name, academic_year_id]
                )
                lab_slot_id = query_db(
                    'SELECT last_insert_rowid() as id', one=True
                )['id']
            
            # Insert students and enrollments
            for index, row in df.iterrows():
                student_id = str(row['Αριθμός μητρώου'])
                name = row['Student_Name']
                email = row['E-mail']
                username = row['Όνομα χρήστη (username)']
                
                # Insert student if not exists
                student = query_db(
                    'SELECT student_id FROM Students WHERE student_id=?',
                    [student_id],
                    one=True
                )
                
                if not student:
                    modify_db(
                        'INSERT INTO Students (student_id, name, email, username) VALUES (?, ?, ?, ?)',
                        [student_id, name, email, username]
                    )
                else:
                    # Check if student is already enrolled in this academic year
                    enrollment = query_db(
                        'SELECT id FROM Enrollments WHERE student_id=? AND academic_year_id=?',
                        [student_id, academic_year_id],
                        one=True
                    )
                    
                    if enrollment:
                        flash(f'Student ID {student_id} is already enrolled in this academic year.', 'warning')
                        continue
                
                # Insert enrollment
                modify_db(
                    'INSERT INTO Enrollments (student_id, lab_slot_id, academic_year_id) VALUES (?, ?, ?)',
                    [student_id, lab_slot_id, academic_year_id]
                )
            
            flash(f'Successfully imported {len(df)} students to lab slot {lab_slot_name}', 'success')
            return redirect(url_for('students_show', academic_year_id=academic_year_id))
            
        except Exception as e:
            flash(f'Error importing students: {str(e)}', 'danger')
            return redirect(request.url)
    
    # Get all academic years for the form
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    
    return render_template('students/import.html', academic_years=academic_years)

@app.route('/students/show/<int:academic_year_id>/')
@login_required
def students_show(academic_year_id):
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id=?',
        [academic_year_id],
        one=True
    )
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('students_index'))
    
    # Get all lab slots for this academic year
    lab_slots = query_db(
        'SELECT id, name FROM LabSlots WHERE academic_year_id=?',
        [academic_year_id]
    )
    
    # Get selected lab slots (or all if none selected)
    selected_lab_ids = request.args.getlist('lab_slot_id')
    selected_lab_ids = [int(id) for id in selected_lab_ids if id.isdigit()]
    
    if selected_lab_ids:
        # Build query with placeholders for each lab slot ID
        placeholders = ','.join(['?' for _ in selected_lab_ids])
        students = query_db(f'''
            SELECT s.*, l.name as lab_slot_name
            FROM Students s
            JOIN Enrollments e ON s.student_id = e.student_id
            JOIN LabSlots l ON e.lab_slot_id = l.id
            WHERE e.academic_year_id = ? AND l.id IN ({placeholders})
            ORDER BY l.name, s.name
        ''', [academic_year_id] + selected_lab_ids)
    else:
        students = query_db('''
            SELECT s.*, l.name as lab_slot_name
            FROM Students s
            JOIN Enrollments e ON s.student_id = e.student_id
            JOIN LabSlots l ON e.lab_slot_id = l.id
            WHERE e.academic_year_id = ?
            ORDER BY l.name, s.name
        ''', [academic_year_id])
    
    return render_template(
        'students/show.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        students=students,
        selected_lab_ids=selected_lab_ids
    )

# Export data function
@app.route('/export/<int:academic_year_id>/<int:lab_slot_id>/')
@login_required
def export_data(academic_year_id, lab_slot_id):
    # Get academic year and lab slot
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id=?',
        [academic_year_id],
        one=True
    )
    
    lab_slot = query_db(
        'SELECT id, name FROM LabSlots WHERE id=?',
        [lab_slot_id],
        one=True
    )
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('academic_year_index'))
    
    try:
        # Get students with their team numbers and attendance
        students = query_db('''
            SELECT 
                s.student_id, 
                s.name, 
                s.email, 
                s.username,
                st.team_number,
                (SELECT COUNT(*) FROM Attendance a 
                WHERE a.student_id = s.student_id 
                AND a.lab_slot_id = ? 
                AND a.academic_year_id = ? 
                AND a.status = 'Absent') as absences
            FROM 
                Students s
            INNER JOIN 
                Enrollments e ON s.student_id = e.student_id
            LEFT JOIN 
                StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
            WHERE 
                e.lab_slot_id = ? AND e.academic_year_id = ?
            ORDER BY 
                st.team_number, s.name
        ''', [lab_slot_id, academic_year_id, lab_slot_id, lab_slot_id, academic_year_id])
        
        # Convert to pandas DataFrame
        data = []
        for student in students:
            student_dict = dict(student)
            data.append(student_dict)
        
        if not data:
            flash('No student data found for this lab slot', 'warning')
            return redirect(url_for('students_show', academic_year_id=academic_year_id))
            
        df = pd.DataFrame(data)
        
        # Get grades for each student
        grades = query_db('''
            SELECT 
                g.student_id,
                g.exercise_slot,
                g.grade
            FROM 
                Grades g
            WHERE 
                g.lab_slot_id = ? AND g.academic_year_id = ?
        ''', [lab_slot_id, academic_year_id])
        
        # Create a pivot table for grades
        if grades:
            grades_data = []
            for grade in grades:
                grades_data.append(dict(grade))
            
            grades_df = pd.DataFrame(grades_data)
            if not grades_df.empty:
                grades_pivot = pd.pivot_table(
                    grades_df, 
                    values='grade', 
                    index='student_id',
                    columns='exercise_slot', 
                    aggfunc='first'
                )
                
                # Merge with the main DataFrame
                df = pd.merge(
                    df, 
                    grades_pivot, 
                    left_on='student_id', 
                    right_index=True, 
                    how='left'
                )
        
        # Generate filename and export to Excel
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"{academic_year['semester']}.{academic_year['year']}.{lab_slot['name']}.{timestamp}.xlsx"
        
        # Ensure the filename is valid for Windows systems
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_')
        
        df.to_excel(filename, index=False)
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'danger')
        print(f"Error exporting data: {str(e)}")
        return redirect(url_for('students_show', academic_year_id=academic_year_id))

# API Endpoints
@app.route('/api/lab_slots/')
@login_required
def api_lab_slots():
    academic_year_id = request.args.get('academic_year_id', type=int)
    if not academic_year_id:
        return jsonify({'error': 'Academic year ID is required'}), 400
    
    lab_slots = query_db(
        'SELECT id, name FROM LabSlots WHERE academic_year_id = ? ORDER BY name',
        [academic_year_id]
    )
    
    lab_slots_data = []
    for slot in lab_slots:
        lab_slots_data.append({
            'id': slot['id'],
            'name': slot['name']
        })
    
    return jsonify({'lab_slots': lab_slots_data})

@app.route('/api/lab_slots_for_transfer/')
@login_required
def api_lab_slots_for_transfer():
    academic_year_id = request.args.get('academic_year_id', type=int)
    student_id = request.args.get('student_id')
    
    if not academic_year_id or not student_id:
        return jsonify({'error': 'Academic year ID and student ID are required'}), 400
    
    # Get the student's current lab slot ID for this academic year
    current_enrollment = query_db(
        'SELECT lab_slot_id FROM Enrollments WHERE student_id = ? AND academic_year_id = ?',
        [student_id, academic_year_id],
        one=True
    )
    
    if not current_enrollment:
        return jsonify({'error': 'Student is not enrolled in the selected academic year'}), 404
    
    current_lab_slot_id = current_enrollment['lab_slot_id']
    
    # Get all lab slots for this academic year except the current one
    lab_slots = query_db(
        'SELECT id, name FROM LabSlots WHERE academic_year_id = ? AND id != ? ORDER BY name',
        [academic_year_id, current_lab_slot_id]
    )
    
    lab_slots_data = []
    for slot in lab_slots:
        lab_slots_data.append({
            'id': slot['id'],
            'name': slot['name']
        })
    
    return jsonify({'lab_slots': lab_slots_data})

# Teams management routes
@app.route('/teams/')
@login_required
def teams_index():
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    
    # Get lab slots with team info
    lab_slots_with_teams = query_db('''
        SELECT 
            l.id, 
            l.name, 
            l.academic_year_id,
            a.semester as academic_year_semester,
            a.year as academic_year_year,
            COUNT(DISTINCT st.team_number) as team_count,
            COUNT(DISTINCT st.student_id) as student_count
        FROM 
            LabSlots l
        LEFT JOIN 
            StudentTeams st ON l.id = st.lab_slot_id
        JOIN 
            AcademicYear a ON l.academic_year_id = a.id
        GROUP BY 
            l.id
        ORDER BY 
            a.year DESC, a.semester, l.name
    ''')
    
    return render_template('teams/index.html', 
                          academic_years=academic_years,
                          lab_slots_with_teams=lab_slots_with_teams)

@app.route('/teams/assign/')
@login_required
def teams_assign():
    academic_year_id = request.args.get('academic_year_id', type=int)
    lab_slot_id = request.args.get('lab_slot_id', type=int)
    
    if not academic_year_id or not lab_slot_id:
        flash('Please select an academic year and lab slot', 'danger')
        return redirect(url_for('teams_index'))
    
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    lab_slot = query_db('SELECT id, name FROM LabSlots WHERE id = ?', 
                      [lab_slot_id], one=True)
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('teams_index'))
    
    # Get students with their team assignments (if any)
    students = query_db('''
        SELECT 
            s.student_id, 
            s.name, 
            s.email,
            st.team_number
        FROM 
            Students s
        JOIN 
            Enrollments e ON s.student_id = e.student_id
        LEFT JOIN 
            StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
        WHERE 
            e.lab_slot_id = ? AND e.academic_year_id = ?
        ORDER BY 
            s.name
    ''', [lab_slot_id, lab_slot_id, academic_year_id])
    
    # Count existing teams
    teams_count = query_db('''
        SELECT COUNT(DISTINCT team_number) as count
        FROM StudentTeams
        WHERE lab_slot_id = ?
    ''', [lab_slot_id], one=True)
    
    teams_count = teams_count['count'] if teams_count and teams_count['count'] else 5
    
    return render_template('teams/assign.html',
                          academic_year=academic_year,
                          lab_slot=lab_slot,
                          students=students,
                          teams_count=teams_count)

@app.route('/teams/assign/process/', methods=['POST'])
@login_required
def teams_assign_process():
    academic_year_id = request.form.get('academic_year_id', type=int)
    lab_slot_id = request.form.get('lab_slot_id', type=int)
    num_teams = request.form.get('num_teams', type=int, default=5)
    assignment_method = request.form.get('assignment_method', 'auto')
    
    if not academic_year_id or not lab_slot_id:
        flash('Invalid request parameters', 'danger')
        return redirect(url_for('teams_index'))
    
    # Delete existing team assignments for this lab slot
    modify_db('DELETE FROM StudentTeams WHERE lab_slot_id = ?', [lab_slot_id])
    
    # Get students for this lab slot
    students = query_db('''
        SELECT s.student_id
        FROM Students s
        JOIN Enrollments e ON s.student_id = e.student_id
        WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
        ORDER BY s.name
    ''', [lab_slot_id, academic_year_id])
    
    if assignment_method == 'auto':
        # Randomly assign students to teams
        import random
        student_ids = [s['student_id'] for s in students]
        random.shuffle(student_ids)
        
        total_students = len(student_ids)
        if total_students == 0:
            flash('No students to assign', 'warning')
            return redirect(url_for('teams_show', 
                                  academic_year_id=academic_year_id, 
                                  lab_slot_id=lab_slot_id))
        
        # Calculate students per team
        students_per_team = total_students // num_teams if num_teams > 0 else 0
        extra_students = total_students % num_teams if num_teams > 0 else 0
        
        # Assign teams
        current_index = 0
        for team_num in range(1, num_teams+1):
            # If there are extra students, add one more to the first 'extra_students' teams
            team_size = students_per_team + (1 if team_num <= extra_students else 0)
            
            for i in range(team_size):
                if current_index < total_students:
                    try:
                        modify_db(
                            'INSERT INTO StudentTeams (team_number, student_id, lab_slot_id) VALUES (?, ?, ?)',
                            [team_num, student_ids[current_index], lab_slot_id]
                        )
                        current_index += 1
                    except Exception as e:
                        print(f"Error assigning student {student_ids[current_index]} to team {team_num}: {e}")
                        flash(f"Error assigning some students to teams: {e}", "danger")
        
        flash(f'Successfully assigned {total_students} students to {num_teams} teams', 'success')
    else:
        # For manual assignment, just set up for manual assignment in the next page
        flash('Please assign students to teams manually', 'info')
    
    return redirect(url_for('teams_show', 
                          academic_year_id=academic_year_id, 
                          lab_slot_id=lab_slot_id))

@app.route('/teams/show/')
@login_required
def teams_show():
    academic_year_id = request.args.get('academic_year_id', type=int)
    lab_slot_id = request.args.get('lab_slot_id', type=int)
    
    if not academic_year_id or not lab_slot_id:
        flash('Please select an academic year and lab slot', 'danger')
        return redirect(url_for('teams_index'))
    
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    lab_slot = query_db('SELECT id, name FROM LabSlots WHERE id = ?', 
                      [lab_slot_id], one=True)
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('teams_index'))
    
    # Get students with their teams
    students = query_db('''
        SELECT 
            s.student_id, 
            s.name,
            st.team_number
        FROM 
            Students s
        JOIN 
            Enrollments e ON s.student_id = e.student_id
        LEFT JOIN 
            StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
        WHERE 
            e.lab_slot_id = ? AND e.academic_year_id = ?
        ORDER BY 
            st.team_number, s.name
    ''', [lab_slot_id, lab_slot_id, academic_year_id])
    
    # Organize students by team
    teams = {}
    for student in students:
        team_number = student['team_number']
        if team_number:
            if team_number not in teams:
                teams[team_number] = []
            teams[team_number].append(student)
    
    # Determine the maximum team number for the manual assignment dropdown
    max_teams = 10  # Default
    if teams:
        max_teams = max(teams.keys()) + 5  # Add a few more options
    
    return render_template('teams/show.html',
                          academic_year=academic_year,
                          lab_slot=lab_slot,
                          teams=teams,
                          all_students=students,
                          max_teams=max_teams)

@app.route('/teams/manual-assign/', methods=['POST'])
@login_required
def teams_manual_assign():
    academic_year_id = request.form.get('academic_year_id', type=int)
    lab_slot_id = request.form.get('lab_slot_id', type=int)
    
    if not academic_year_id or not lab_slot_id:
        flash('Invalid request parameters', 'danger')
        return redirect(url_for('teams_index'))
    
    # Get all students for this lab slot
    students = query_db('''
        SELECT s.student_id
        FROM Students s
        JOIN Enrollments e ON s.student_id = e.student_id
        WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
    ''', [lab_slot_id, academic_year_id])
    
    # Delete existing team assignments for this lab slot
    modify_db('DELETE FROM StudentTeams WHERE lab_slot_id = ?', [lab_slot_id])
    
    # Insert new team assignments
    for student in students:
        student_id = student['student_id']
        team_num = request.form.get(f'team_{student_id}', '')
        
        if team_num.strip():
            modify_db(
                'INSERT INTO StudentTeams (team_number, student_id, lab_slot_id) VALUES (?, ?, ?)',
                [int(team_num), student_id, lab_slot_id]
            )
    
    flash('Team assignments saved successfully', 'success')
    return redirect(url_for('teams_show', 
                          academic_year_id=academic_year_id, 
                          lab_slot_id=lab_slot_id))

# Update base.html links
@app.before_request
def update_base_links():
    g.active_features = {
        'teams': True,
        'attendance': True,
        'grades': True
    }

# Attendance management routes
@app.route('/attendance/')
@login_required
def attendance_index():
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    
    # Get recent attendance records
    recent_records = query_db('''
        SELECT 
            a.academic_year_id,
            a.lab_slot_id,
            a.exercise_slot,
            MAX(a.timestamp) as timestamp,
            ac.semester || ' ' || ac.year as academic_year_name,
            l.name as lab_slot_name,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count
        FROM 
            Attendance a
        JOIN 
            AcademicYear ac ON a.academic_year_id = ac.id
        JOIN 
            LabSlots l ON a.lab_slot_id = l.id
        GROUP BY 
            a.academic_year_id, a.lab_slot_id, a.exercise_slot
        ORDER BY 
            timestamp DESC
        LIMIT 10
    ''')
    
    return render_template('attendance/index.html', 
                          academic_years=academic_years,
                          recent_records=recent_records)

@app.route('/attendance/record/')
@login_required
def attendance_record():
    academic_year_id = request.args.get('academic_year_id', type=int)
    lab_slot_id = request.args.get('lab_slot_id', type=int)
    exercise_slot = request.args.get('exercise_slot')
    
    if not academic_year_id or not lab_slot_id or not exercise_slot:
        flash('Please provide all required parameters', 'danger')
        return redirect(url_for('attendance_index'))
    
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    lab_slot = query_db('SELECT id, name FROM LabSlots WHERE id = ?', 
                      [lab_slot_id], one=True)
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('attendance_index'))
    
    # Get students with their status (if recorded before)
    students = query_db('''
        SELECT 
            s.student_id, 
            s.name,
            st.team_number,
            COALESCE(a.status, 'Present') as status
        FROM 
            Students s
        JOIN 
            Enrollments e ON s.student_id = e.student_id
        LEFT JOIN 
            StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
        LEFT JOIN 
            Attendance a ON s.student_id = a.student_id AND a.lab_slot_id = ? AND a.exercise_slot = ? AND a.academic_year_id = ?
        WHERE 
            e.lab_slot_id = ? AND e.academic_year_id = ?
        ORDER BY 
            st.team_number, s.name
    ''', [lab_slot_id, lab_slot_id, exercise_slot, academic_year_id, lab_slot_id, academic_year_id])
    
    return render_template('attendance/record.html',
                          academic_year=academic_year,
                          lab_slot=lab_slot,
                          exercise_slot=exercise_slot,
                          students=students)

@app.route('/attendance/save/', methods=['POST'])
@login_required
def attendance_save():
    academic_year_id = request.form.get('academic_year_id', type=int)
    lab_slot_id = request.form.get('lab_slot_id', type=int)
    exercise_slot = request.form.get('exercise_slot')
    
    if not academic_year_id or not lab_slot_id or not exercise_slot:
        flash('Invalid request parameters', 'danger')
        return redirect(url_for('attendance_index'))
    
    # Get all students for this lab slot
    students = query_db('''
        SELECT s.student_id
        FROM Students s
        JOIN Enrollments e ON s.student_id = e.student_id
        WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
    ''', [lab_slot_id, academic_year_id])
    
    # Delete existing attendance records for this slot and exercise
    try:
        modify_db('''
            DELETE FROM Attendance 
            WHERE lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
        ''', [lab_slot_id, exercise_slot, academic_year_id])
        
        # Insert new attendance records
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = 0
        
        for student in students:
            student_id = student['student_id']
            status = request.form.get(f'status_{student_id}', 'Absent')  # Default to absent if not specified
            
            modify_db(
                '''INSERT INTO Attendance 
                (student_id, lab_slot_id, exercise_slot, status, timestamp, academic_year_id) 
                VALUES (?, ?, ?, ?, ?, ?)''',
                [student_id, lab_slot_id, exercise_slot, status, timestamp, academic_year_id]
            )
            count += 1
        
        flash(f'Attendance recorded for {count} students', 'success')
    except Exception as e:
        flash(f'Error saving attendance: {str(e)}', 'danger')
        print(f"Error saving attendance: {str(e)}")
    
    return redirect(url_for('attendance_view', 
                          academic_year_id=academic_year_id, 
                          lab_slot_id=lab_slot_id,
                          exercise_slot=exercise_slot))

@app.route('/attendance/view/')
@login_required
def attendance_view():
    academic_year_id = request.args.get('academic_year_id', type=int)
    lab_slot_id = request.args.get('lab_slot_id', type=int)
    exercise_slot = request.args.get('exercise_slot')
    
    if not academic_year_id or not lab_slot_id or not exercise_slot:
        flash('Please provide all required parameters', 'danger')
        return redirect(url_for('attendance_index'))
    
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    lab_slot = query_db('SELECT id, name FROM LabSlots WHERE id = ?', 
                      [lab_slot_id], one=True)
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('attendance_index'))
    
    # Check if replenishment_note column exists
    column_exists = True
    try:
        # Try a test query
        get_db().execute('SELECT replenishment_note FROM Attendance LIMIT 1')
    except sqlite3.OperationalError:
        column_exists = False
    
    # Get attendance records with student details
    if column_exists:
        # Use query with replenishment_note
        attendance_records = query_db('''
            SELECT 
                s.student_id, 
                s.name,
                st.team_number,
                a.status,
                a.timestamp,
                a.replenishment_note
            FROM 
                Attendance a
            JOIN 
                Students s ON a.student_id = s.student_id
            LEFT JOIN 
                StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
            WHERE 
                a.lab_slot_id = ? AND a.exercise_slot = ? AND a.academic_year_id = ?
            ORDER BY 
                st.team_number, s.name
        ''', [lab_slot_id, lab_slot_id, exercise_slot, academic_year_id])
    else:
        # Use query without replenishment_note
        attendance_basic = query_db('''
            SELECT 
                s.student_id, 
                s.name,
                st.team_number,
                a.status,
                a.timestamp
            FROM 
                Attendance a
            JOIN 
                Students s ON a.student_id = s.student_id
            LEFT JOIN 
                StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
            WHERE 
                a.lab_slot_id = ? AND a.exercise_slot = ? AND a.academic_year_id = ?
            ORDER BY 
                st.team_number, s.name
        ''', [lab_slot_id, lab_slot_id, exercise_slot, academic_year_id])
        
        # Convert Row objects to dictionaries first
        attendance_basic = [dict(record) for record in attendance_basic]
        
        # Add empty replenishment_note field
        attendance_records = []
        for record in attendance_basic:
            record['replenishment_note'] = None
            attendance_records.append(record)
    
    # Calculate attendance statistics
    total_students = len(attendance_records)
    present_count = sum(1 for record in attendance_records if record['status'] == 'Present')
    absent_count = total_students - present_count
    
    attendance_stats = {
        'total': total_students,
        'present': present_count,
        'absent': absent_count
    }
    
    return render_template('attendance/view.html',
                          academic_year=academic_year,
                          lab_slot=lab_slot,
                          exercise_slot=exercise_slot,
                          attendance_records=attendance_records,
                          attendance_stats=attendance_stats)

# Grades management routes
@app.route('/grades/')
@login_required
def grades_index():
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    
    # Get grade statistics
    grade_records = query_db('''
        SELECT 
            g.academic_year_id,
            g.lab_slot_id,
            g.exercise_slot,
            MAX(g.timestamp) as timestamp,
            ac.semester || ' ' || ac.year as academic_year_name,
            l.name as lab_slot_name,
            COUNT(g.id) as students_count,
            AVG(g.grade) as average_grade
        FROM 
            Grades g
        JOIN 
            AcademicYear ac ON g.academic_year_id = ac.id
        JOIN 
            LabSlots l ON g.lab_slot_id = l.id
        GROUP BY 
            g.academic_year_id, g.lab_slot_id, g.exercise_slot
        ORDER BY 
            timestamp DESC
    ''')
    
    return render_template('grades/index.html', 
                          academic_years=academic_years,
                          grade_records=grade_records)

@app.route('/grades/insert/')
@login_required
def grades_insert():
    academic_year_id = request.args.get('academic_year_id', type=int)
    lab_slot_id = request.args.get('lab_slot_id', type=int)
    exercise_slot = request.args.get('exercise_slot')
    
    if not academic_year_id or not lab_slot_id or not exercise_slot:
        flash('Please provide all required parameters', 'danger')
        return redirect(url_for('grades_index'))
    
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    lab_slot = query_db('SELECT id, name FROM LabSlots WHERE id = ?', 
                      [lab_slot_id], one=True)
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('grades_index'))
    
    # Get students with their grades (if entered before)
    students = query_db('''
        SELECT 
            s.student_id, 
            s.name,
            st.team_number,
            g.grade
        FROM 
            Students s
        JOIN 
            Enrollments e ON s.student_id = e.student_id
        LEFT JOIN 
            StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
        LEFT JOIN 
            Grades g ON s.student_id = g.student_id AND g.lab_slot_id = ? AND g.exercise_slot = ? AND g.academic_year_id = ?
        WHERE 
            e.lab_slot_id = ? AND e.academic_year_id = ?
        ORDER BY 
            st.team_number, s.name
    ''', [lab_slot_id, lab_slot_id, exercise_slot, academic_year_id, lab_slot_id, academic_year_id])
    
    return render_template('grades/insert.html',
                          academic_year=academic_year,
                          lab_slot=lab_slot,
                          exercise_slot=exercise_slot,
                          students=students)

@app.route('/grades/save/', methods=['POST'])
@login_required
def grades_save():
    academic_year_id = request.form.get('academic_year_id', type=int)
    lab_slot_id = request.form.get('lab_slot_id', type=int)
    exercise_slot = request.form.get('exercise_slot')
    
    if not academic_year_id or not lab_slot_id or not exercise_slot:
        flash('Invalid request parameters', 'danger')
        return redirect(url_for('grades_index'))
    
    # Get all students for this lab slot
    students = query_db('''
        SELECT s.student_id
        FROM Students s
        JOIN Enrollments e ON s.student_id = e.student_id
        WHERE e.lab_slot_id = ? AND e.academic_year_id = ?
    ''', [lab_slot_id, academic_year_id])
    
    try:
        # Delete existing grade records for this slot and exercise
        modify_db('''
            DELETE FROM Grades 
            WHERE lab_slot_id = ? AND exercise_slot = ? AND academic_year_id = ?
        ''', [lab_slot_id, exercise_slot, academic_year_id])
        
        # Insert new grade records
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = 0
        
        for student in students:
            student_id = student['student_id']
            grade_value = request.form.get(f'grade_{student_id}', '')
            
            if grade_value.strip():
                try:
                    grade = float(grade_value)
                    modify_db(
                        '''INSERT INTO Grades 
                        (student_id, lab_slot_id, exercise_slot, grade, timestamp, academic_year_id) 
                        VALUES (?, ?, ?, ?, ?, ?)''',
                        [student_id, lab_slot_id, exercise_slot, grade, timestamp, academic_year_id]
                    )
                    count += 1
                except ValueError:
                    flash(f'Invalid grade value for student {student_id}', 'warning')
        
        flash(f'Grades recorded for {count} students', 'success')
    except Exception as e:
        flash(f'Error saving grades: {str(e)}', 'danger')
        print(f"Error saving grades: {str(e)}")
    
    return redirect(url_for('grades_view', 
                          academic_year_id=academic_year_id, 
                          lab_slot_id=lab_slot_id,
                          exercise_slot=exercise_slot))

@app.route('/grades/view/')
@login_required
def grades_view():
    academic_year_id = request.args.get('academic_year_id', type=int)
    lab_slot_id = request.args.get('lab_slot_id', type=int)
    exercise_slot = request.args.get('exercise_slot')
    
    if not academic_year_id or not lab_slot_id or not exercise_slot:
        flash('Please provide all required parameters', 'danger')
        return redirect(url_for('grades_index'))
    
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    lab_slot = query_db('SELECT id, name FROM LabSlots WHERE id = ?', 
                      [lab_slot_id], one=True)
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('grades_index'))
    
    # Get grade records with student details
    grade_records = query_db('''
        SELECT 
            s.student_id, 
            s.name,
            st.team_number,
            g.grade,
            g.timestamp
        FROM 
            Grades g
        JOIN 
            Students s ON g.student_id = s.student_id
        LEFT JOIN 
            StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
        WHERE 
            g.lab_slot_id = ? AND g.exercise_slot = ? AND g.academic_year_id = ?
        ORDER BY 
            st.team_number, s.name
    ''', [lab_slot_id, lab_slot_id, exercise_slot, academic_year_id])
    
    # Calculate grade statistics
    total_students = len(grade_records)
    if total_students > 0:
        total_grade = sum(record['grade'] for record in grade_records if record['grade'] is not None)
        average_grade = total_grade / total_students
        max_grade = max((record['grade'] for record in grade_records if record['grade'] is not None), default=0)
        min_grade = min((record['grade'] for record in grade_records if record['grade'] is not None), default=0)
        
        # Calculate grade distribution
        distribution = [0] * 10  # 10 bins for grades 0-10
        for record in grade_records:
            if record['grade'] is not None:
                bin_index = min(int(record['grade']), 9)  # Grade 10 goes in bin 9
                distribution[bin_index] += 1
    else:
        average_grade = 0
        max_grade = 0
        min_grade = 0
        distribution = [0] * 10  # Empty distribution
    
    grade_stats = {
        'total': total_students,
        'average': average_grade,
        'max': max_grade,
        'min': min_grade,
        'distribution': distribution
    }
    
    return render_template('grades/view.html',
                          academic_year=academic_year,
                          lab_slot=lab_slot,
                          exercise_slot=exercise_slot,
                          grade_records=grade_records,
                          grade_stats=grade_stats)

@app.route('/grades/final/')
@login_required
def grades_final():
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    selected_year_id = request.args.get('academic_year_id', type=int)
    
    if not selected_year_id and academic_years:
        # Default to the first academic year if none selected
        selected_year_id = academic_years[0]['id']
    
    if not selected_year_id:
        flash('No academic years found. Please create one first.', 'warning')
        return redirect(url_for('academic_year_index'))
    
    selected_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [selected_year_id], one=True)
    
    if not selected_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('grades_index'))
    
    # Get all lab slots for this academic year
    lab_slots = query_db('''
        SELECT id, name 
        FROM LabSlots 
        WHERE academic_year_id = ?
        ORDER BY name
    ''', [selected_year_id])
    
    # Get students with their enrollment info
    students = query_db('''
        SELECT DISTINCT
            s.student_id, 
            s.name
        FROM 
            Students s
        JOIN 
            Enrollments e ON s.student_id = e.student_id
        WHERE 
            e.academic_year_id = ?
        ORDER BY 
            s.name
    ''', [selected_year_id])
    
    final_grades = []
    grade_stats = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'average': 0,
        'distribution': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 0-1, 1-2, ..., 9-10
    }
    
    total_final_grade = 0
    
    for student in students:
        student_id = student['student_id']
        
        # Get exercise grades
        exercise_grades = query_db('''
            SELECT grade, exercise_slot
            FROM Grades
            WHERE student_id = ? AND academic_year_id = ?
        ''', [student_id, selected_year_id])
        
        # Calculate average of exercise grades
        avg_exercise_grade = 0
        if exercise_grades:
            total = sum(grade['grade'] for grade in exercise_grades)
            avg_exercise_grade = round(total / len(exercise_grades), 2)
        
        # Get all exam grades for this student in this academic year
        all_exam_grades = query_db('''
            SELECT 
                eg.grade,
                eg.timestamp,
                es.name as exam_name,
                es.date
            FROM 
                ExamGrades eg
            JOIN 
                ExamSlots es ON eg.exam_slot_id = es.id
            WHERE 
                eg.student_id = ? 
                AND es.academic_year_id = ?
            ORDER BY 
                es.date DESC, eg.timestamp DESC
        ''', [student_id, selected_year_id])
        
        # Process exam grades to find June and September exams
        june_exam = None
        september_exam = None
        latest_exam = None
        
        for exam in all_exam_grades:
            exam_name = exam['exam_name'].lower()
            
            # Check if this is a June or September exam by name
            if 'june' in exam_name or 'jun' in exam_name:
                if not june_exam or exam['timestamp'] > june_exam['timestamp']:
                    june_exam = exam
            elif 'september' in exam_name or 'sep' in exam_name:
                if not september_exam or exam['timestamp'] > september_exam['timestamp']:
                    september_exam = exam
            
            # Keep track of the latest exam taken
            if not latest_exam or exam['timestamp'] > latest_exam['timestamp']:
                latest_exam = exam
        
        # Extract the grades
        june_grade = june_exam['grade'] if june_exam else 0
        september_grade = september_exam['grade'] if september_exam else 0
        
        # Use the latest exam for final grade calculation
        latest_exam_grade = latest_exam['grade'] if latest_exam else 0
        exam_name = latest_exam['exam_name'] if latest_exam else 'None'
        
        # Calculate final grade according to the formula
        final_grade = 0
        if latest_exam_grade >= 5:
            # If exam grade is >= 5, final grade is 25% exercises + 75% exam
            final_grade = round(0.25 * avg_exercise_grade + 0.75 * latest_exam_grade, 2)
        else:
            # If exam grade is < 5, final grade is 25% of exercises only
            final_grade = round(0.25 * avg_exercise_grade, 2)
        
        # Update statistics
        grade_stats['total'] += 1
        total_final_grade += final_grade
        
        if final_grade >= 5:
            grade_stats['passed'] += 1
        else:
            grade_stats['failed'] += 1
        
        # Update distribution
        bin_index = min(int(final_grade), 9)
        grade_stats['distribution'][bin_index] += 1
        
        # Store student details with grades
        final_grades.append({
            'student_id': student_id,
            'name': student['name'],
            'exercise_grades': exercise_grades,
            'avg_exercise_grade': avg_exercise_grade,
            'jun_exam_grade': june_grade,
            'sep_exam_grade': september_grade,
            'latest_exam': exam_name,
            'latest_exam_grade': latest_exam_grade,
            'final_grade': final_grade
        })
    
    # Calculate average final grade
    if grade_stats['total'] > 0:
        grade_stats['average'] = total_final_grade / grade_stats['total']
    
    return render_template('grades/final.html',
                          academic_years=academic_years,
                          selected_year_id=selected_year_id,
                          selected_year=selected_year,
                          lab_slots=lab_slots,
                          final_grades=final_grades,
                          grade_stats=grade_stats)

@app.route('/grades/final/export/<int:academic_year_id>/')
@login_required
def export_final_grades(academic_year_id):
    # Get academic year
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('grades_index'))
    
    # Get all students with their enrollment info
    students = query_db('''
        SELECT DISTINCT
            s.student_id, 
            s.name,
            l.name as lab_slot_name
        FROM 
            Students s
        JOIN 
            Enrollments e ON s.student_id = e.student_id
        JOIN
            LabSlots l ON e.lab_slot_id = l.id
        WHERE 
            e.academic_year_id = ?
        ORDER BY 
            s.name
    ''', [academic_year_id])
    
    # Prepare data for Excel
    data = []
    
    for student in students:
        student_id = student['student_id']
        
        # Get exercise grades
        exercise_grades = query_db('''
            SELECT grade, exercise_slot
            FROM Grades
            WHERE student_id = ? AND academic_year_id = ?
            ORDER BY exercise_slot
        ''', [student_id, academic_year_id])
        
        # Calculate average of exercise grades
        avg_exercise_grade = 0
        if exercise_grades:
            total = sum(grade['grade'] for grade in exercise_grades)
            avg_exercise_grade = round(total / len(exercise_grades), 2)
        
        # Get all exam grades for this student in this academic year
        all_exam_grades = query_db('''
            SELECT 
                eg.grade,
                eg.timestamp,
                es.name as exam_name,
                es.date
            FROM 
                ExamGrades eg
            JOIN 
                ExamSlots es ON eg.exam_slot_id = es.id
            WHERE 
                eg.student_id = ? 
                AND es.academic_year_id = ?
            ORDER BY 
                es.date DESC, eg.timestamp DESC
        ''', [student_id, academic_year_id])
        
        # Process exam grades to find June and September exams
        june_exam = None
        september_exam = None
        latest_exam = None
        
        for exam in all_exam_grades:
            exam_name = exam['exam_name'].lower()
            
            # Check if this is a June or September exam by name
            if 'june' in exam_name or 'jun' in exam_name:
                if not june_exam or exam['timestamp'] > june_exam['timestamp']:
                    june_exam = exam
            elif 'september' in exam_name or 'sep' in exam_name:
                if not september_exam or exam['timestamp'] > september_exam['timestamp']:
                    september_exam = exam
            
            # Keep track of the latest exam taken
            if not latest_exam or exam['timestamp'] > latest_exam['timestamp']:
                latest_exam = exam
        
        # Extract the grades
        june_grade = june_exam['grade'] if june_exam else 0
        september_grade = september_exam['grade'] if september_exam else 0
        
        # Use the latest exam for final grade calculation
        latest_exam_grade = latest_exam['grade'] if latest_exam else 0
        exam_name = latest_exam['exam_name'] if latest_exam else 'None'
        
        # Calculate final grade according to the formula
        final_grade = 0
        if latest_exam_grade >= 5:
            # If exam grade is >= 5, final grade is 25% exercises + 75% exam
            final_grade = round(0.25 * avg_exercise_grade + 0.75 * latest_exam_grade, 2)
        else:
            # If exam grade is < 5, final grade is 25% of exercises only
            final_grade = round(0.25 * avg_exercise_grade, 2)
        
        # Create row with student basic info
        row = {
            'Student ID': student_id,
            'Name': student['name'],
            'Lab Group': student['lab_slot_name'],
            'Exercises Avg': avg_exercise_grade,
            'June Exam Grade': june_grade,
            'September Exam Grade': september_grade,
            'Latest Exam': exam_name,
            'Latest Exam Grade': latest_exam_grade,
            'Final Grade': final_grade
        }
        
        # Add individual exercise grades
        for grade in exercise_grades:
            exercise_name = grade['exercise_slot']
            row[f"Exercise {exercise_name}"] = grade['grade']
        
        data.append(row)
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file
    filename = f"final_grades_{academic_year['semester']}_{academic_year['year']}.xlsx"
    filepath = os.path.join(os.getcwd(), filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Final Grades', index=False)
        
        # Auto-adjust columns' width
        worksheet = writer.sheets['Final Grades']
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + i)].width = max_length
    
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/grades/final/save/', methods=['POST'])
@login_required
def grades_final_save():
    academic_year_id = request.form.get('academic_year_id', type=int)
    
    if not academic_year_id:
        flash('Invalid request parameters', 'danger')
        return redirect(url_for('grades_index'))
    
    # Get all students for this academic year
    students = query_db('''
        SELECT DISTINCT s.student_id
        FROM Students s
        JOIN Enrollments e ON s.student_id = e.student_id
        WHERE e.academic_year_id = ?
    ''', [academic_year_id])
    
    try:
        count = 0
        for student in students:
            student_id = student['student_id']
            
            lab_average = request.form.get(f'lab_average_{student_id}', '')
            jun_exam = request.form.get(f'jun_exam_{student_id}', '')
            sep_exam = request.form.get(f'sep_exam_{student_id}', '')
            
            # Calculate final grade - take best of Jun or Sep exam
            try:
                lab_avg = float(lab_average) if lab_average.strip() else 0
                jun_grade = float(jun_exam) if jun_exam.strip() else 0
                sep_grade = float(sep_exam) if sep_exam.strip() else 0
                
                best_exam = max(jun_grade, sep_grade)
                final_grade = 0.5 * lab_avg + 0.5 * best_exam if best_exam > 0 else 0
            except ValueError:
                flash(f'Invalid grade value for student {student_id}', 'warning')
                continue
            
            # Check if record exists
            existing = query_db('''
                SELECT id FROM FinalGrades
                WHERE student_id = ? AND academic_year_id = ?
            ''', [student_id, academic_year_id], one=True)
            
            if existing:
                # Update existing record
                modify_db('''
                    UPDATE FinalGrades
                    SET lab_average = ?, jun_exam_grade = ?, sep_exam_grade = ?, final_grade = ?
                    WHERE student_id = ? AND academic_year_id = ?
                ''', [lab_avg, jun_grade, sep_grade, final_grade, student_id, academic_year_id])
            else:
                # Insert new record
                modify_db('''
                    INSERT INTO FinalGrades
                    (student_id, lab_average, jun_exam_grade, sep_exam_grade, final_grade, academic_year_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', [student_id, lab_avg, jun_grade, sep_grade, final_grade, academic_year_id])
            
            count += 1
        
        flash(f'Final grades saved for {count} students', 'success')
    except Exception as e:
        flash(f'Error saving final grades: {str(e)}', 'danger')
        print(f"Error saving final grades: {str(e)}")
    
    return redirect(url_for('grades_final', academic_year_id=academic_year_id))

# Enhanced student management
@app.route('/students/detail/<string:student_id>/')
@login_required
def student_detail(student_id):
    # Get student info
    student = query_db('SELECT * FROM Students WHERE student_id = ?', [student_id], one=True)
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('students_index'))
    
    # Get enrollments
    enrollments = query_db("""
        SELECT 
            e.id,
            a.id as academic_year_id,
            a.semester,
            a.year,
            l.name as lab_slot_name
        FROM 
            Enrollments e
        JOIN 
            AcademicYear a ON e.academic_year_id = a.id
        JOIN 
            LabSlots l ON e.lab_slot_id = l.id
        WHERE 
            e.student_id = ?
        ORDER BY 
            a.year DESC, a.semester
    """, [student_id])
    
    # Get team assignments
    teams = query_db("""
        SELECT 
            st.team_number,
            l.name as lab_slot_name,
            a.semester,
            a.year
        FROM 
            StudentTeams st
        JOIN 
            LabSlots l ON st.lab_slot_id = l.id
        JOIN 
            AcademicYear a ON l.academic_year_id = a.id
        WHERE 
            st.student_id = ?
        ORDER BY 
            a.year DESC, a.semester
    """, [student_id])
    
    # Get attendance records
    attendance = query_db("""
        SELECT 
            a.exercise_slot,
            a.status,
            a.timestamp,
            l.name as lab_slot_name,
            ac.semester,
            ac.year
        FROM 
            Attendance a
        JOIN 
            LabSlots l ON a.lab_slot_id = l.id
        JOIN 
            AcademicYear ac ON a.academic_year_id = ac.id
        WHERE 
            a.student_id = ?
        ORDER BY 
            a.timestamp DESC
    """, [student_id])
    
    # Get grades
    grades = query_db("""
        SELECT 
            g.exercise_slot,
            g.grade,
            g.timestamp,
            l.name as lab_slot_name,
            ac.semester,
            ac.year
        FROM 
            Grades g
        JOIN 
            LabSlots l ON g.lab_slot_id = l.id
        JOIN 
            AcademicYear ac ON g.academic_year_id = ac.id
        WHERE 
            g.student_id = ?
        ORDER BY 
            g.timestamp DESC
    """, [student_id])
    
    # Get exam grades - handle case where attendance column might not exist
    try:
        # First try with attendance column
        exam_grades = query_db("""
            SELECT 
                eg.id,
                eg.grade,
                eg.attendance,
                eg.notes,
                eg.timestamp,
                es.id as exam_slot_id,
                es.name as exam_name,
                es.date as exam_date,
                es.exam_period,
                ac.id as academic_year_id,
                ac.semester,
                ac.year
            FROM 
                ExamGrades eg
            JOIN 
                ExamSlots es ON eg.exam_slot_id = es.id
            JOIN 
                AcademicYear ac ON es.academic_year_id = ac.id
            WHERE 
                eg.student_id = ?
            ORDER BY 
                es.date DESC, eg.timestamp DESC
        """, [student_id])
    except sqlite3.OperationalError:
        # Fallback query without attendance column
        exam_grades = query_db("""
            SELECT 
                eg.id,
                eg.grade,
                1 as attendance, -- Default value for attendance (1 = Present)
                eg.notes,
                eg.timestamp,
                es.id as exam_slot_id,
                es.name as exam_name,
                es.date as exam_date,
                es.exam_period,
                ac.id as academic_year_id,
                ac.semester,
                ac.year
            FROM 
                ExamGrades eg
            JOIN 
                ExamSlots es ON eg.exam_slot_id = es.id
            JOIN 
                AcademicYear ac ON es.academic_year_id = ac.id
            WHERE 
                eg.student_id = ?
            ORDER BY 
                es.date DESC, eg.timestamp DESC
        """, [student_id])
        # Log that the attendance column is missing - it should be added at application startup
        print("WARNING: attendance column is missing in ExamGrades table. Run the database upgrade script.")
    
    # Calculate final grades for each academic year
    final_grades = []
    
    # Group enrollments by academic year
    academic_years = {}
    for enrollment in enrollments:
        academic_year_id = enrollment['academic_year_id']
        if academic_year_id not in academic_years:
            academic_years[academic_year_id] = {
                'id': academic_year_id,
                'semester': enrollment['semester'],
                'year': enrollment['year']
            }
    
    for academic_year_id, academic_year in academic_years.items():
        # Calculate average of exercise grades for this academic year
        exercise_grades = query_db("""
            SELECT grade
            FROM Grades
            WHERE student_id = ? AND academic_year_id = ?
        """, [student_id, academic_year_id])
        
        avg_exercise_grade = 0
        if exercise_grades:
            total = sum(grade['grade'] for grade in exercise_grades)
            avg_exercise_grade = round(total / len(exercise_grades), 2)
        
        # Get June and September exam grades for this academic year
        june_exam = None
        september_exam = None
        latest_exam = None
        
        for exam in exam_grades:
            if exam['academic_year_id'] == academic_year_id:
                # First check exam_period if available
                if 'exam_period' in exam and exam['exam_period']:
                    if exam['exam_period'] == 'June':
                        if not june_exam or exam['timestamp'] > june_exam['timestamp']:
                            june_exam = exam
                    elif exam['exam_period'] == 'September':
                        if not september_exam or exam['timestamp'] > september_exam['timestamp']:
                            september_exam = exam
                else:
                    # Fallback to name-based check for legacy data without exam_period
                    exam_name = exam['exam_name'].lower()
                    if 'june' in exam_name or 'jun' in exam_name:
                        if not june_exam or exam['timestamp'] > june_exam['timestamp']:
                            june_exam = exam
                    elif 'september' in exam_name or 'sep' in exam_name:
                        if not september_exam or exam['timestamp'] > september_exam['timestamp']:
                            september_exam = exam
                
                # Keep track of the latest exam taken
                if not latest_exam or exam['timestamp'] > latest_exam['timestamp']:
                    latest_exam = exam
        
        # Extract the grades
        june_grade = june_exam['grade'] if june_exam else 0
        september_grade = september_exam['grade'] if september_exam else 0
        
        # Use the latest exam for final grade calculation
        final_exam_grade = latest_exam['grade'] if latest_exam else 0
        
        # Calculate final grade according to the formula
        final_grade = 0
        if final_exam_grade >= 5:
            # If exam grade is >= 5, final grade is 25% exercises + 75% exam
            final_grade = round(0.25 * avg_exercise_grade + 0.75 * final_exam_grade, 2)
        else:
            # If exam grade is < 5, final grade is 25% of exercises only
            final_grade = round(0.25 * avg_exercise_grade, 2)
        
        # Add to final grades
        final_grades.append({
            'academic_year_id': academic_year_id,
            'semester': academic_year['semester'],
            'year': academic_year['year'],
            'lab_average': avg_exercise_grade,
            'jun_exam_grade': june_grade,
            'sep_exam_grade': september_grade,
            'latest_exam': latest_exam['exam_name'] if latest_exam else 'None',
            'latest_exam_period': latest_exam['exam_period'] if latest_exam and 'exam_period' in latest_exam else None,
            'latest_exam_grade': final_exam_grade,
            'final_grade': final_grade
        })
    
    # Sort final grades by year and semester (descending)
    final_grades.sort(key=lambda x: (x['year'], x['semester']), reverse=True)
    
    return render_template('students/detail.html',
                         student=student,
                         enrollments=enrollments,
                         teams=teams,
                         attendance=attendance,
                         grades=grades,
                         exam_grades=exam_grades,
                         final_grades=final_grades)

@app.route('/students/edit/<string:student_id>/', methods=['GET', 'POST'])
@login_required
def student_edit(student_id):
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        username = request.form.get('username')
        
        if not name or not email:
            flash('Name and email are required', 'danger')
            return redirect(url_for('student_edit', student_id=student_id))
        
        # Update student
        modify_db(
            'UPDATE Students SET name = ?, email = ?, username = ? WHERE student_id = ?',
            [name, email, username, student_id]
        )
        
        flash('Student updated successfully', 'success')
        return redirect(url_for('student_detail', student_id=student_id))
    
    # Get student info for the form
    student = query_db('SELECT * FROM Students WHERE student_id = ?', [student_id], one=True)
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('students_index'))
    
    return render_template('students/edit.html', student=student)

@app.route('/students/delete/<string:student_id>/', methods=['POST'])
@login_required
def student_delete(student_id):
    # Get student to confirm they exist
    student = query_db('SELECT * FROM Students WHERE student_id = ?', [student_id], one=True)
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('students_index'))
    
    try:
        # Delete related records first
        modify_db('DELETE FROM Enrollments WHERE student_id = ?', [student_id])
        modify_db('DELETE FROM StudentTeams WHERE student_id = ?', [student_id])
        modify_db('DELETE FROM Attendance WHERE student_id = ?', [student_id])
        modify_db('DELETE FROM Grades WHERE student_id = ?', [student_id])
        modify_db('DELETE FROM FinalGrades WHERE student_id = ?', [student_id])
        
        # Delete student
        modify_db('DELETE FROM Students WHERE student_id = ?', [student_id])
        
        flash('Student and all related records deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting student: {str(e)}', 'danger')
    
    return redirect(url_for('students_index'))

@app.route('/students/add/', methods=['GET', 'POST'])
@login_required
def student_add():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        email = request.form.get('email')
        username = request.form.get('username')
        
        if not student_id or not name or not email:
            flash('Student ID, name, and email are required', 'danger')
            return redirect(url_for('student_add'))
        
        # Check if student already exists
        existing = query_db('SELECT student_id FROM Students WHERE student_id = ?', [student_id], one=True)
        if existing:
            flash(f'Student with ID {student_id} already exists', 'warning')
            return redirect(url_for('student_add'))
        
        # Add new student
        modify_db(
            'INSERT INTO Students (student_id, name, email, username) VALUES (?, ?, ?, ?)',
            [student_id, name, email, username]
        )
        
        flash('Student added successfully', 'success')
        return redirect(url_for('students_index'))
    
    return render_template('students/add.html')

@app.route('/students/transfer/<string:student_id>/', methods=['GET', 'POST'])
@login_required
def transfer_student(student_id):
    # Get student info
    student = query_db(
        'SELECT * FROM Students WHERE student_id = ?',
        [student_id],
        one=True
    )
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('students_index'))
    
    # Get all academic years
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year DESC, semester')
    
    if request.method == 'POST':
        academic_year_id = request.form.get('academic_year_id', type=int)
        new_lab_slot_id = request.form.get('new_lab_slot_id', type=int)
        
        if not academic_year_id or not new_lab_slot_id:
            flash('Please select an academic year and a new lab slot', 'danger')
            return redirect(url_for('transfer_student', student_id=student_id))
        
        # Check if the student is enrolled in the selected academic year
        enrollment = query_db(
            'SELECT e.*, l.name AS lab_slot_name FROM Enrollments e JOIN LabSlots l ON e.lab_slot_id = l.id WHERE e.student_id = ? AND e.academic_year_id = ?',
            [student_id, academic_year_id],
            one=True
        )
        
        if not enrollment:
            flash('Student is not enrolled in the selected academic year', 'danger')
            return redirect(url_for('transfer_student', student_id=student_id))
        
        # Update enrollment with the new lab slot
        modify_db(
            'UPDATE Enrollments SET lab_slot_id = ? WHERE student_id = ? AND academic_year_id = ?',
            [new_lab_slot_id, student_id, academic_year_id]
        )
        
        # Update attendance records to the new lab slot
        modify_db(
            'UPDATE Attendance SET lab_slot_id = ? WHERE student_id = ? AND academic_year_id = ?',
            [new_lab_slot_id, student_id, academic_year_id]
        )
        
        # Update grades to the new lab slot
        modify_db(
            'UPDATE Grades SET lab_slot_id = ? WHERE student_id = ? AND academic_year_id = ?',
            [new_lab_slot_id, student_id, academic_year_id]
        )
        
        # Get the new lab slot name
        new_lab_slot = query_db(
            'SELECT name FROM LabSlots WHERE id = ?',
            [new_lab_slot_id],
            one=True
        )
        
        flash(f'Student {student["name"]} has been transferred from {enrollment["lab_slot_name"]} to {new_lab_slot["name"]}', 'success')
        return redirect(url_for('student_detail', student_id=student_id))
    
    # Get current enrollments for this student
    enrollments = query_db('''
        SELECT e.*, a.semester, a.year, l.name AS lab_slot_name
        FROM Enrollments e
        JOIN AcademicYear a ON e.academic_year_id = a.id
        JOIN LabSlots l ON e.lab_slot_id = l.id
        WHERE e.student_id = ?
        ORDER BY a.year DESC, a.semester
    ''', [student_id])
    
    # Get lab slots for the first academic year in the list (for initial display)
    selected_academic_year_id = academic_years[0]['id'] if academic_years else None
    lab_slots = []
    
    if selected_academic_year_id:
        lab_slots = query_db(
            'SELECT id, name FROM LabSlots WHERE academic_year_id = ? ORDER BY name',
            [selected_academic_year_id]
        )
    
    return render_template(
        'students/transfer.html',
        student=student,
        enrollments=enrollments,
        academic_years=academic_years,
        lab_slots=lab_slots,
        selected_academic_year_id=selected_academic_year_id
    )

# Initialize database with test data
def init_test_data():
    with app.app_context():
        # Check if academic years already exist
        academic_years = query_db('SELECT COUNT(*) as count FROM AcademicYear', one=True)
        if academic_years['count'] > 0:
            print("Test data already exists, skipping initialization")
            return
            
        # Add academic years
        modify_db('INSERT INTO AcademicYear (semester, year) VALUES (?, ?)', ['EARINO', 2024])
        modify_db('INSERT INTO AcademicYear (semester, year) VALUES (?, ?)', ['EARINO', 2025])
        
        # Get academic year IDs
        academic_year_2024 = query_db('SELECT id FROM AcademicYear WHERE semester = ? AND year = ?', 
                                    ['EARINO', 2024], one=True)['id']
        academic_year_2025 = query_db('SELECT id FROM AcademicYear WHERE semester = ? AND year = ?', 
                                    ['EARINO', 2025], one=True)['id']
        
        # Add lab slots for 2024
        lab_slots_2024 = [
            "ΠΕΜΠΤΗ 15:00-17:00 (A)",
            "ΠΕΜΠΤΗ 17:00-19:00 (A)",
            "ΠΑΡΑΣΚΕΥΗ 15:00-17:00 (A)",
            "ΠΕΜΠΤΗ 15:00-17:00 (B)",
            "ΠΑΡΑΣΚΕΥΗ 13:00-15:00 (A)",
            "ΠΕΜΠΤΗ 17:00-19:00 (B)",
            "ΠΑΡΑΣΚΕΥΗ 13:00-15:00 (B)"
        ]
        
        for slot in lab_slots_2024:
            modify_db('INSERT INTO LabSlots (name, academic_year_id) VALUES (?, ?)', 
                     [slot, academic_year_2024])
        
        # Add lab slots for 2025
        lab_slots_2025 = [
            "ΠΕΜΠΤΗ 15:00-17:00 (A)",
            "ΠΕΜΠΤΗ 17:00-19:00 (A)",
            "ΠΑΡΑΣΚΕΥΗ 15:00-17:00 (A)",
            "ΠΕΜΠΤΗ 15:00-17:00 (B)",
            "ΠΑΡΑΣΚΕΥΗ 13:00-15:00 (A)",
            "ΠΕΜΠΤΗ 17:00-19:00 (B)",
            "ΠΑΡΑΣΚΕΥΗ 13:00-15:00 (B)"
        ]
        
        for slot in lab_slots_2025:
            modify_db('INSERT INTO LabSlots (name, academic_year_id) VALUES (?, ?)', 
                     [slot, academic_year_2025])
        
        # Add exam slots for 2024
        exam_slots_2024 = [
            {"name": "MIDTERM - ΠΕΜΠΤΗ", "date": "2024-05-15", "time": "09:00-11:00", "location": "Main Auditorium"},
            {"name": "FINAL - ΠΑΡΑΣΚΕΥΗ", "date": "2024-06-20", "time": "13:00-15:00", "location": "Room A101"}
        ]
        
        for slot in exam_slots_2024:
            modify_db(
                'INSERT INTO ExamSlots (name, date, time, location, academic_year_id) VALUES (?, ?, ?, ?, ?)', 
                [slot["name"], slot["date"], slot["time"], slot["location"], academic_year_2024]
            )
        
        # Add exam slots for 2025
        exam_slots_2025 = [
            {"name": "MIDTERM - ΠΕΜΠΤΗ", "date": "2025-05-15", "time": "09:00-11:00", "location": "Main Auditorium"},
            {"name": "FINAL - ΠΑΡΑΣΚΕΥΗ", "date": "2025-06-20", "time": "13:00-15:00", "location": "Room A101"}
        ]
        
        for slot in exam_slots_2025:
            modify_db(
                'INSERT INTO ExamSlots (name, date, time, location, academic_year_id) VALUES (?, ?, ?, ?, ?)', 
                [slot["name"], slot["date"], slot["time"], slot["location"], academic_year_2025]
            )
        
        # Get lab slot IDs for 2024
        lab_slot_2024_1 = query_db('SELECT id FROM LabSlots WHERE name = ? AND academic_year_id = ?', 
                                 ["ΠΕΜΠΤΗ 15:00-17:00 (A)", academic_year_2024], one=True)['id']
        
        # Get exam slot ID for 2024
        exam_slot_2024_1 = query_db('SELECT id FROM ExamSlots WHERE name = ? AND academic_year_id = ?', 
                                  ["MIDTERM - ΠΕΜΠΤΗ", academic_year_2024], one=True)['id']
        
        # Add some test students
        test_students = [
            {'id': 'CSD4350', 'name': 'Παπαδόπουλος Γιάννης', 'email': 'papadopoulos@csd.uoc.gr', 'username': 'csd4350'},
            {'id': 'CSD4351', 'name': 'Αντωνίου Μαρία', 'email': 'antoniou@csd.uoc.gr', 'username': 'csd4351'},
            {'id': 'CSD4352', 'name': 'Δημητρίου Νίκος', 'email': 'dimitriou@csd.uoc.gr', 'username': 'csd4352'},
            {'id': 'CSD4353', 'name': 'Γεωργίου Ελένη', 'email': 'georgiou@csd.uoc.gr', 'username': 'csd4353'},
            {'id': 'CSD4354', 'name': 'Αποστόλου Κώστας', 'email': 'apostolou@csd.uoc.gr', 'username': 'csd4354'},
        ]
        
        for student in test_students:
            try:
                # Insert student
                modify_db('INSERT INTO Students (student_id, name, email, username) VALUES (?, ?, ?, ?)',
                        [student['id'], student['name'], student['email'], student['username']])
                
                # Enroll in the 2024 lab slot
                modify_db('INSERT INTO Enrollments (student_id, lab_slot_id, academic_year_id) VALUES (?, ?, ?)',
                        [student['id'], lab_slot_2024_1, academic_year_2024])
                
                # Enroll first three students in the 2024 exam slot
                if student['id'] in ['CSD4350', 'CSD4351', 'CSD4352']:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    modify_db('INSERT INTO ExamEnrollments (student_id, exam_slot_id, academic_year_id, timestamp) VALUES (?, ?, ?, ?)',
                            [student['id'], exam_slot_2024_1, academic_year_2024, timestamp])
            except Exception as e:
                print(f"Error adding student {student['id']}: {e}")
        
        # Assign students to teams
        for i, student in enumerate(test_students):
            team_number = (i % 2) + 1  # Assign to team 1 or 2
            modify_db('INSERT INTO StudentTeams (team_number, student_id, lab_slot_id) VALUES (?, ?, ?)',
                     [team_number, student['id'], lab_slot_2024_1])
        
        # Record attendance for Lab1
        exercise_slot = "Lab1"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for i, student in enumerate(test_students):
            status = "Present" if i < 4 else "Absent"  # Make one student absent
            modify_db(
                '''INSERT INTO Attendance 
                (student_id, lab_slot_id, exercise_slot, status, timestamp, academic_year_id) 
                VALUES (?, ?, ?, ?, ?, ?)''',
                [student['id'], lab_slot_2024_1, exercise_slot, status, timestamp, academic_year_2024]
            )
        
        # Add grades for Lab1
        for i, student in enumerate(test_students):
            grade = 8.5 + (i * 0.3)  # Different grades
            modify_db(
                '''INSERT INTO Grades 
                (student_id, lab_slot_id, exercise_slot, grade, timestamp, academic_year_id) 
                VALUES (?, ?, ?, ?, ?, ?)''',
                [student['id'], lab_slot_2024_1, exercise_slot, grade, timestamp, academic_year_2024]
            )
            
        print("Test data initialized successfully")

# Route to initialize test data
@app.route('/init-test-data/')
@login_required
def init_test_data_route():
    init_test_data()
    flash("Test data has been initialized!", "success")
    return redirect(url_for('dashboard'))

# Helper function to initialize the database if it doesn't exist
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Create AcademicYear table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS AcademicYear (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester TEXT,
                year INTEGER
            )
        ''')

        # Create LabSlots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS LabSlots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                academic_year_id INTEGER,
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create ExamSlots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ExamSlots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                date TEXT,
                time TEXT,
                location TEXT,
                academic_year_id INTEGER,
                exam_period TEXT,
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create Students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Students (
                student_id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                registration_number TEXT,
                username TEXT
            )
        ''')

        # Create Enrollments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_slot_id INTEGER,
                academic_year_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create ExamEnrollments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ExamEnrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                exam_slot_id INTEGER,
                academic_year_id INTEGER,
                timestamp TEXT,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(exam_slot_id) REFERENCES ExamSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create StudentTeams table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS StudentTeams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_number INTEGER,
                student_id TEXT,
                lab_slot_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id)
            )
        ''')

        # Create Attendance table with lab_slot_id column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_slot_id INTEGER,
                exercise_slot TEXT,
                status TEXT,
                timestamp TEXT,
                academic_year_id INTEGER,
                replenishment_note TEXT,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Check if replenishment_note column exists in Attendance table
        column_exists = False
        try:
            cursor.execute('SELECT replenishment_note FROM Attendance LIMIT 1')
            column_exists = True
        except sqlite3.OperationalError:
            column_exists = False
        
        # Add replenishment_note column if it doesn't exist
        if not column_exists:
            try:
                cursor.execute('ALTER TABLE Attendance ADD COLUMN replenishment_note TEXT')
                print("Added replenishment_note column to Attendance table")
            except sqlite3.OperationalError as e:
                print(f"Error adding replenishment_note column: {e}")

        # Create Grades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_slot_id INTEGER,
                exercise_slot TEXT,
                grade REAL,
                timestamp TEXT,
                academic_year_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(lab_slot_id) REFERENCES LabSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create FinalGrades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS FinalGrades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                lab_average REAL,
                jun_exam_grade REAL,
                sep_exam_grade REAL,
                final_grade REAL,
                academic_year_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        # Create ExamGrades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ExamGrades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                exam_slot_id INTEGER,
                grade REAL,
                timestamp TEXT,
                academic_year_id INTEGER,
                notes TEXT,
                FOREIGN KEY(student_id) REFERENCES Students(student_id),
                FOREIGN KEY(exam_slot_id) REFERENCES ExamSlots(id),
                FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
            )
        ''')

        db.commit()
        print("Database schema initialized successfully.")

@app.route('/export_all_data/<int:academic_year_id>/')
@login_required
def export_all_data(academic_year_id):
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id=?',
        [academic_year_id],
        one=True
    )
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('academic_year_index'))
    
    # Get selected lab slots (or all if none selected)
    selected_lab_ids = request.args.getlist('lab_slot_id')
    selected_lab_ids = [int(id) for id in selected_lab_ids if id.isdigit()]
    
    if not selected_lab_ids:
        flash('No lab slots selected', 'warning')
        return redirect(url_for('students_show', academic_year_id=academic_year_id))
    
    try:
        # Get lab slot names
        lab_slots_info = {}
        for lab_slot_id in selected_lab_ids:
            lab_slot = query_db(
                'SELECT id, name FROM LabSlots WHERE id=?',
                [lab_slot_id],
                one=True
            )
            if lab_slot:
                lab_slots_info[lab_slot_id] = lab_slot['name']
        
        # Get all students data for selected lab slots
        placeholders = ','.join(['?' for _ in selected_lab_ids])
        students = query_db(f'''
            SELECT 
                s.student_id, 
                s.name, 
                s.email, 
                s.username,
                l.name as lab_slot_name,
                l.id as lab_slot_id,
                st.team_number,
                (SELECT COUNT(*) FROM Attendance a 
                WHERE a.student_id = s.student_id 
                AND a.lab_slot_id = l.id
                AND a.academic_year_id = ? 
                AND a.status = 'Absent') as absences
            FROM 
                Students s
            INNER JOIN 
                Enrollments e ON s.student_id = e.student_id
            INNER JOIN 
                LabSlots l ON e.lab_slot_id = l.id
            LEFT JOIN 
                StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = l.id
            WHERE 
                e.academic_year_id = ? AND l.id IN ({placeholders})
            ORDER BY 
                l.name, st.team_number, s.name
        ''', [academic_year_id, academic_year_id] + selected_lab_ids)
        
        if not students:
            flash('No student data found for selected lab slots', 'warning')
            return redirect(url_for('students_show', academic_year_id=academic_year_id))
        
        # Get all grades for all selected lab slots
        all_grades = query_db(f'''
            SELECT 
                g.student_id,
                g.lab_slot_id,
                l.name as lab_slot_name,
                g.exercise_slot,
                g.grade
            FROM 
                Grades g
            INNER JOIN
                LabSlots l ON g.lab_slot_id = l.id
            WHERE 
                g.academic_year_id = ? AND g.lab_slot_id IN ({placeholders})
        ''', [academic_year_id] + selected_lab_ids)
        
        # Get all final grades
        all_final_grades = query_db('''
            SELECT 
                fg.student_id,
                s.name as student_name,
                l.name as lab_slot_name,
                l.id as lab_slot_id,
                st.team_number,
                fg.lab_average,
                fg.jun_exam_grade,
                fg.sep_exam_grade,
                fg.final_grade
            FROM 
                FinalGrades fg
            INNER JOIN
                Students s ON fg.student_id = s.student_id
            INNER JOIN
                Enrollments e ON s.student_id = e.student_id AND e.academic_year_id = fg.academic_year_id
            INNER JOIN
                LabSlots l ON e.lab_slot_id = l.id
            LEFT JOIN
                StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = l.id
            WHERE 
                fg.academic_year_id = ?
        ''', [academic_year_id])
        
        # Convert student data to DataFrame
        students_data = [dict(student) for student in students]
        df_students = pd.DataFrame(students_data)
        
        # Create a writer for Excel output
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"{academic_year['semester']}.{academic_year['year']}.{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_')
        
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Sheet 1: Students by Lab Slot
            if not df_students.empty:
                df_students.to_excel(writer, sheet_name="Students by Lab Slot", index=False)
            
            # Sheet 2: Students Alphabetically
            if not df_students.empty:
                df_alpha = df_students.sort_values(by="name")
                df_alpha.to_excel(writer, sheet_name="Students Alphabetically", index=False)
            
            # Sheet 3: Grades per Lab Slot
            if all_grades:
                # Process grades for each lab slot
                for lab_slot_id in selected_lab_ids:
                    # Filter grades for this lab slot
                    lab_grades = [g for g in all_grades if g['lab_slot_id'] == lab_slot_id]
                    
                    if lab_grades:
                        lab_slot_name = lab_slots_info.get(lab_slot_id, f"Lab Slot {lab_slot_id}")
                        sheet_name = f"Grades - {lab_slot_name}"
                        
                        # Convert to DataFrame
                        df_grades = pd.DataFrame([dict(g) for g in lab_grades])
                        
                        # Create a pivot table for grades
                        try:
                            grades_pivot = pd.pivot_table(
                                df_grades, 
                                values='grade', 
                                index=['student_id', 'lab_slot_name'],
                                columns='exercise_slot', 
                                aggfunc='first'
                            ).reset_index()
                            
                            # Merge with student info
                            students_in_lab = [s for s in students_data if s['lab_slot_id'] == lab_slot_id]
                            if students_in_lab:
                                df_students_in_lab = pd.DataFrame(students_in_lab)
                                merged_df = pd.merge(
                                    df_students_in_lab[['student_id', 'name', 'team_number']], 
                                    grades_pivot,
                                    on='student_id',
                                    how='left'
                                )
                                
                                # Rename columns for better readability
                                merged_df = merged_df.rename(columns={
                                    'name': 'Student Name',
                                    'student_id': 'Student ID',
                                    'team_number': 'Team Number',
                                    'lab_slot_name': 'Lab Slot'
                                })
                                
                                # Sort by team number and student name
                                merged_df = merged_df.sort_values(by=['Team Number', 'Student Name'])
                                
                                # Limit sheet name length to avoid Excel errors
                                if len(sheet_name) > 31:
                                    sheet_name = sheet_name[:28] + "..."
                                
                                merged_df.to_excel(writer, sheet_name=sheet_name, index=False)
                        except Exception as e:
                            print(f"Error creating grades pivot for lab slot {lab_slot_id}: {e}")
            
            # Sheet 4: Final Grades
            if all_final_grades:
                df_final = pd.DataFrame([dict(fg) for fg in all_final_grades])
                
                # Rename columns
                df_final = df_final.rename(columns={
                    'student_name': 'Student Name',
                    'student_id': 'Student ID',
                    'team_number': 'Team Number',
                    'lab_slot_name': 'Lab Slot',
                    'lab_average': 'Lab Average',
                    'jun_exam_grade': 'June Exam',
                    'sep_exam_grade': 'September Exam',
                    'final_grade': 'Final Grade'
                })
                
                # Sort by lab slot, team number, and student name
                df_final = df_final.sort_values(by=['Lab Slot', 'Team Number', 'Student Name'])
                
                df_final.to_excel(writer, sheet_name="Final Grades", index=False)
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'danger')
        print(f"Error exporting all data: {str(e)}")
        return redirect(url_for('students_show', academic_year_id=academic_year_id))

@app.route('/attendance/absences/')
@login_required
def attendance_absences():
    academic_year_id = request.args.get('academic_year_id', type=int)
    
    if not academic_year_id:
        # Get all academic years for the dropdown
        academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
        
        return render_template('attendance/absences.html',
                             academic_years=academic_years)
    
    # Get academic year
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('attendance_index'))
    
    # Get all lab slots for this academic year (for replenishment scheduling)
    lab_slots = query_db(
        'SELECT id, name FROM LabSlots WHERE academic_year_id = ? ORDER BY name',
        [academic_year_id]
    )
    
    # Get all absences for this academic year
    try:
        # Check if replenishment_note column exists
        column_exists = True
        try:
            # Try a test query
            get_db().execute('SELECT replenishment_note FROM Attendance LIMIT 1')
        except sqlite3.OperationalError:
            column_exists = False
            # Show a flash message suggesting upgrade
            flash('Database schema needs to be upgraded to support replenishment scheduling. Please use the "Upgrade Database" option from the menu.', 'warning')
        
        if column_exists:
            # Use query with replenishment_note
            absences = query_db('''
                SELECT 
                    a.id,
                    s.student_id, 
                    s.name as student_name,
                    s.email as student_email,
                    l.name as lab_slot_name,
                    a.exercise_slot,
                    a.timestamp,
                    a.replenishment_note
                FROM 
                    Attendance a
                JOIN 
                    Students s ON a.student_id = s.student_id
                JOIN 
                    LabSlots l ON a.lab_slot_id = l.id
                WHERE 
                    a.academic_year_id = ? AND a.status = 'Absent'
                ORDER BY 
                    l.name, a.exercise_slot, s.name
            ''', [academic_year_id])
            
            # Convert Row objects to dictionaries
            absences = [dict(absence) for absence in absences]
        else:
            # Use query without replenishment_note
            absences_basic = query_db('''
                SELECT 
                    a.id,
                    s.student_id, 
                    s.name as student_name,
                    s.email as student_email,
                    l.name as lab_slot_name,
                    a.exercise_slot,
                    a.timestamp
                FROM 
                    Attendance a
                JOIN 
                    Students s ON a.student_id = s.student_id
                JOIN 
                    LabSlots l ON a.lab_slot_id = l.id
                WHERE 
                    a.academic_year_id = ? AND a.status = 'Absent'
                ORDER BY 
                    l.name, a.exercise_slot, s.name
            ''', [academic_year_id])
            
            # Convert Row objects to dictionaries first
            absences_basic = [dict(absence) for absence in absences_basic]
            
            # Add empty replenishment_note field
            absences = []
            for absence in absences_basic:
                absence['replenishment_note'] = None
                absences.append(absence)
                
        # Count absences per student and mark those with 2+ absences as failed
        students_absent_count = {}
        for absence in absences:
            student_id = absence['student_id']
            if student_id in students_absent_count:
                students_absent_count[student_id] += 1
            else:
                students_absent_count[student_id] = 1
        
        # Add a has_failed flag to each absence entry
        for absence in absences:
            student_id = absence['student_id']
            absence['has_failed'] = students_absent_count[student_id] >= 2
            absence['absence_count'] = students_absent_count[student_id]
            
    except Exception as e:
        flash(f'Error retrieving absences: {str(e)}', 'danger')
        absences = []
    
    return render_template('attendance/absences.html',
                         academic_year=academic_year,
                         lab_slots=lab_slots,
                         absences=absences)

@app.route('/attendance/export_absences/<int:academic_year_id>/')
@login_required
def export_absences(academic_year_id):
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id=?',
        [academic_year_id],
        one=True
    )
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('attendance_index'))
    
    try:
        # Get all absences for this academic year
        absences = query_db('''
            SELECT 
                s.student_id, 
                s.name as student_name,
                s.email as student_email,
                l.name as lab_slot_name,
                a.exercise_slot,
                a.timestamp,
                a.replenishment_note
            FROM 
                Attendance a
            JOIN 
                Students s ON a.student_id = s.student_id
            JOIN 
                LabSlots l ON a.lab_slot_id = l.id
            WHERE 
                a.academic_year_id = ? AND a.status = 'Absent'
            ORDER BY 
                l.name, a.exercise_slot, s.name
        ''', [academic_year_id])
        
        if not absences:
            flash('No absences found for the selected academic year', 'warning')
            return redirect(url_for('attendance_absences', academic_year_id=academic_year_id))
        
        # Convert to pandas DataFrame
        absences_data = [dict(absence) for absence in absences]
        
        # Count absences per student
        students_absent_count = {}
        for absence in absences_data:
            student_id = absence['student_id']
            if student_id in students_absent_count:
                students_absent_count[student_id] += 1
            else:
                students_absent_count[student_id] = 1
        
        # Add absence count and failed status
        for absence in absences_data:
            student_id = absence['student_id']
            absence['absence_count'] = students_absent_count[student_id]
            absence['has_failed'] = students_absent_count[student_id] >= 2
        
        df_absences = pd.DataFrame(absences_data)
        
        # Rename columns for better readability
        df_absences = df_absences.rename(columns={
            'student_id': 'Student ID',
            'student_name': 'Student Name',
            'student_email': 'Email',
            'lab_slot_name': 'Lab Slot',
            'exercise_slot': 'Exercise',
            'timestamp': 'Absence Date',
            'replenishment_note': 'Replenishment Details',
            'absence_count': 'Total Absences',
            'has_failed': 'Failed Lab'
        })
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"Absences_{academic_year['semester']}_{academic_year['year']}_{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_')
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Write absences to Excel
            df_absences.to_excel(writer, sheet_name="Absences", index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Absences"]
            
            # Add filters
            worksheet.autofilter(0, 0, len(df_absences), len(df_absences.columns) - 1)
            
            # Format the replenishment column to wrap text
            wrap_format = workbook.add_format({'text_wrap': True})
            worksheet.set_column('G:G', 30, wrap_format)
            
            # Add header formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            for col_num, value in enumerate(df_absences.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Add conditional formatting for failed students
            failed_format = workbook.add_format({
                'bg_color': '#FFC7CE',
                'font_color': '#9C0006'
            })
            
            # Apply to the failed column
            worksheet.conditional_format(1, 8, len(df_absences), 8, {
                'type': 'cell',
                'criteria': 'equal to',
                'value': True,
                'format': failed_format
            })
            
            # Add a separate Failed Students summary sheet
            # Get unique students with their absence counts
            students_summary = {}
            for absence in absences_data:
                student_id = absence['student_id']
                if student_id not in students_summary:
                    students_summary[student_id] = {
                        'Student ID': student_id,
                        'Student Name': absence['student_name'],
                        'Email': absence['student_email'],
                        'Lab Slot': absence['lab_slot_name'],
                        'Total Absences': absence['absence_count'],
                        'Failed Lab': absence['has_failed']
                    }
            
            # Create summary DataFrame
            summary_data = list(students_summary.values())
            df_summary = pd.DataFrame(summary_data)
            
            # Sort by absence count (descending) and student name
            if not df_summary.empty:
                df_summary = df_summary.sort_values(by=['Total Absences', 'Student Name'], ascending=[False, True])
                
                # Add a Summary sheet
                df_summary.to_excel(writer, sheet_name="Students Summary", index=False)
                
                # Format the summary sheet
                summary_sheet = writer.sheets["Students Summary"]
                
                # Add filters
                summary_sheet.autofilter(0, 0, len(df_summary), len(df_summary.columns) - 1)
                
                # Add header formatting
                for col_num, value in enumerate(df_summary.columns.values):
                    summary_sheet.write(0, col_num, value, header_format)
                
                # Add conditional formatting for the absence count
                # Red for failed (>=2), yellow for warning (1)
                summary_sheet.conditional_format(1, 4, len(df_summary), 4, {
                    'type': 'cell',
                    'criteria': '>=',
                    'value': 2,
                    'format': failed_format
                })
                
                warning_format = workbook.add_format({
                    'bg_color': '#FFEB9C',
                    'font_color': '#9C6500'
                })
                
                summary_sheet.conditional_format(1, 4, len(df_summary), 4, {
                    'type': 'cell',
                    'criteria': '=',
                    'value': 1,
                    'format': warning_format
                })
                
                # Format the failed column
                summary_sheet.conditional_format(1, 5, len(df_summary), 5, {
                    'type': 'cell',
                    'criteria': 'equal to',
                    'value': True,
                    'format': failed_format
                })
        
        return send_file(filename, as_attachment=True)
        
    except Exception as e:
        flash(f'Error exporting absences: {str(e)}', 'danger')
        print(f"Error exporting absences: {str(e)}")
        return redirect(url_for('attendance_absences', academic_year_id=academic_year_id))

@app.route('/attendance/save_note/', methods=['POST'])
@login_required
def attendance_save_note():
    attendance_id = request.form.get('attendance_id', type=int)
    replenishment_note = request.form.get('replenishment_note', '')
    
    if not attendance_id:
        return jsonify({'status': 'error', 'message': 'Attendance ID is required'}), 400
    
    try:
        # Check if replenishment_note column exists first
        db = get_db()
        column_exists = True
        
        try:
            # Try a test query
            db.execute('SELECT replenishment_note FROM Attendance LIMIT 1')
        except sqlite3.OperationalError:
            column_exists = False
            
        if not column_exists:
            # Try to add the column
            try:
                print("Adding replenishment_note column to Attendance table...")
                db.execute('ALTER TABLE Attendance ADD COLUMN replenishment_note TEXT')
                db.commit()
                print("Successfully added replenishment_note column.")
                column_exists = True
            except sqlite3.OperationalError as e:
                error_msg = f"Could not add 'replenishment_note' column: {e}"
                print(error_msg)
                return jsonify({
                    'status': 'error', 
                    'message': 'Database needs to be upgraded. Please use the "Upgrade Database" option from the menu.'
                }), 500
        
        if column_exists:
            # Update the attendance record with the replenishment note
            db.execute(
                'UPDATE Attendance SET replenishment_note = ? WHERE id = ?',
                [replenishment_note, attendance_id]
            )
            db.commit()
            
            return jsonify({
                'status': 'success', 
                'message': 'Replenishment scheduled successfully'
            })
        else:
            return jsonify({
                'status': 'error', 
                'message': 'Could not save note - database needs to be upgraded'
            }), 500
            
    except Exception as e:
        error_msg = f"Error saving replenishment note: {str(e)}"
        print(error_msg)
        return jsonify({'status': 'error', 'message': error_msg}), 500

@app.route('/attendance/export_view/<int:academic_year_id>/<int:lab_slot_id>/<path:exercise_slot>')
@login_required
def export_attendance_view(academic_year_id, lab_slot_id, exercise_slot):
    # Get academic year and lab slot
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id=?',
        [academic_year_id],
        one=True
    )
    
    lab_slot = query_db(
        'SELECT id, name FROM LabSlots WHERE id=?',
        [lab_slot_id],
        one=True
    )
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('attendance_index'))
    
    try:
        # Check if replenishment_note column exists
        column_exists = True
        try:
            # Try a test query
            get_db().execute('SELECT replenishment_note FROM Attendance LIMIT 1')
        except sqlite3.OperationalError:
            column_exists = False
        
        # Get attendance records with student details
        if column_exists:
            attendance_records = query_db('''
                SELECT 
                    s.student_id, 
                    s.name,
                    s.email,
                    st.team_number,
                    a.status,
                    a.timestamp,
                    a.replenishment_note
                FROM 
                    Attendance a
                JOIN 
                    Students s ON a.student_id = s.student_id
                LEFT JOIN 
                    StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
                WHERE 
                    a.lab_slot_id = ? AND a.exercise_slot = ? AND a.academic_year_id = ?
                ORDER BY 
                    st.team_number, s.name
            ''', [lab_slot_id, lab_slot_id, exercise_slot, academic_year_id])
        else:
            # Use query without replenishment_note
            attendance_basic = query_db('''
                SELECT 
                    s.student_id, 
                    s.name,
                    s.email,
                    st.team_number,
                    a.status,
                    a.timestamp
                FROM 
                    Attendance a
                JOIN 
                    Students s ON a.student_id = s.student_id
                LEFT JOIN 
                    StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
                WHERE 
                    a.lab_slot_id = ? AND a.exercise_slot = ? AND a.academic_year_id = ?
                ORDER BY 
                    st.team_number, s.name
            ''', [lab_slot_id, lab_slot_id, exercise_slot, academic_year_id])
            
            # Convert Row objects to dictionaries first
            attendance_basic = [dict(record) for record in attendance_basic]
            
            # Add empty replenishment_note field
            attendance_records = []
            for record in attendance_basic:
                record['replenishment_note'] = None
                attendance_records.append(record)
        
        if not attendance_records:
            flash('No attendance records found', 'warning')
            return redirect(url_for('attendance_view', 
                                  academic_year_id=academic_year_id, 
                                  lab_slot_id=lab_slot_id,
                                  exercise_slot=exercise_slot))
        
        # Convert to pandas DataFrame
        attendance_data = [dict(record) for record in attendance_records]
        df_attendance = pd.DataFrame(attendance_data)
        
        # Rename columns for better readability
        df_attendance = df_attendance.rename(columns={
            'student_id': 'Student ID',
            'name': 'Student Name',
            'email': 'Email',
            'team_number': 'Team',
            'status': 'Status',
            'timestamp': 'Recorded At',
            'replenishment_note': 'Replenishment Details'
        })
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"Attendance_{academic_year['semester']}_{academic_year['year']}_{lab_slot['name']}_{exercise_slot}_{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_').replace(' ', '_')
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Write attendance to Excel
            df_attendance.to_excel(writer, sheet_name="Attendance", index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Attendance"]
            
            # Add filters
            worksheet.autofilter(0, 0, len(df_attendance), len(df_attendance.columns) - 1)
            
            # Format the replenishment column to wrap text
            wrap_format = workbook.add_format({'text_wrap': True})
            worksheet.set_column('G:G', 30, wrap_format)
            
            # Format the status column with colors
            for row_num, status in enumerate(df_attendance['Status'], start=1):
                if status == 'Present':
                    present_format = workbook.add_format({'bg_color': '#c6efce', 'font_color': '#006100'})
                    worksheet.write(row_num, 4, status, present_format)
                else:
                    absent_format = workbook.add_format({'bg_color': '#ffc7ce', 'font_color': '#9c0006'})
                    worksheet.write(row_num, 4, status, absent_format)
            
            # Add header formatting
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            for col_num, value in enumerate(df_attendance.columns.values):
                worksheet.write(0, col_num, value, header_format)
        
        return send_file(filename, as_attachment=True)
        
    except Exception as e:
        flash(f'Error exporting attendance: {str(e)}', 'danger')
        print(f"Error exporting attendance: {str(e)}")
        return redirect(url_for('attendance_view', 
                              academic_year_id=academic_year_id, 
                              lab_slot_id=lab_slot_id,
                              exercise_slot=exercise_slot))

@app.route('/upgrade_database/')
@login_required
def upgrade_database():
    try:
        # Initialize connection
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        # Check if replenishment_note column exists
        column_exists = True
        try:
            cursor.execute('SELECT replenishment_note FROM Attendance LIMIT 1')
            print("Column replenishment_note already exists.")
            flash("Column replenishment_note already exists.", "info")
        except sqlite3.OperationalError:
            # Add the column
            print("Adding replenishment_note column to Attendance table...")
            cursor.execute('ALTER TABLE Attendance ADD COLUMN replenishment_note TEXT')
            conn.commit()
            print("Successfully added replenishment_note column.")
            flash("Successfully added replenishment_note column to Attendance table.", "success")
        
        # Check if ExamSlots table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ExamSlots'")
        if not cursor.fetchone():
            print("Adding ExamSlots table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ExamSlots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    date TEXT,
                    time TEXT,
                    location TEXT,
                    academic_year_id INTEGER,
                    exam_period TEXT,
                    FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
                )
            ''')
            conn.commit()
            print("Successfully added ExamSlots table.")
            flash("Successfully added ExamSlots table to database.", "success")
        
        # Check if ExamEnrollments table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ExamEnrollments'")
        if not cursor.fetchone():
            print("Adding ExamEnrollments table...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ExamEnrollments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    exam_slot_id INTEGER,
                    academic_year_id INTEGER,
                    timestamp TEXT,
                    FOREIGN KEY(student_id) REFERENCES Students(student_id),
                    FOREIGN KEY(exam_slot_id) REFERENCES ExamSlots(id),
                    FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
                )
            ''')
            conn.commit()
            print("Successfully added ExamEnrollments table.")
            flash("Successfully added ExamEnrollments table to database.", "success")
        
        conn.close()
        
    except Exception as e:
        error_msg = f"Error upgrading database: {e}"
        print(error_msg)
        flash(error_msg, "danger")
    
    return redirect(url_for('dashboard'))

# Function to check for the replenishment_note column
def check_database_schema():
    try:
        # Check if replenishment_note column exists
        column_exists = True
        try:
            # Try a test query
            get_db().execute('SELECT replenishment_note FROM Attendance LIMIT 1')
            print("Column 'replenishment_note' already exists in Attendance table.")
        except sqlite3.OperationalError:
            print("Column 'replenishment_note' does not exist in Attendance table.")
            
            # Add the column
            try:
                modify_db('ALTER TABLE Attendance ADD COLUMN replenishment_note TEXT')
                print("Successfully added 'replenishment_note' column to Attendance table.")
            except sqlite3.OperationalError as e:
                print(f"Error adding replenishment_note column: {e}")
        
        # Check if ExamSlots table exists
        try:
            get_db().execute('SELECT id FROM ExamSlots LIMIT 1')
            print("Table 'ExamSlots' already exists.")
        except sqlite3.OperationalError:
            print("Table 'ExamSlots' does not exist.")
            
            # Create the table
            try:
                modify_db('''
                    CREATE TABLE IF NOT EXISTS ExamSlots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        date TEXT,
                        time TEXT,
                        location TEXT,
                        academic_year_id INTEGER,
                        exam_period TEXT,
                        FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
                    )
                ''')
                print("Successfully created 'ExamSlots' table.")
            except sqlite3.OperationalError as e:
                print(f"Error creating ExamSlots table: {e}")
        
        # Check if ExamEnrollments table exists
        try:
            get_db().execute('SELECT id FROM ExamEnrollments LIMIT 1')
            print("Table 'ExamEnrollments' already exists.")
        except sqlite3.OperationalError:
            print("Table 'ExamEnrollments' does not exist.")
            
            # Create the table
            try:
                modify_db('''
                    CREATE TABLE IF NOT EXISTS ExamEnrollments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        exam_slot_id INTEGER,
                        academic_year_id INTEGER,
                        timestamp TEXT,
                        FOREIGN KEY(student_id) REFERENCES Students(student_id),
                        FOREIGN KEY(exam_slot_id) REFERENCES ExamSlots(id),
                        FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
                    )
                ''')
                print("Successfully created 'ExamEnrollments' table.")
            except sqlite3.OperationalError as e:
                print(f"Error creating ExamEnrollments table: {e}")
        
        # Check if ExamGrades table exists
        try:
            get_db().execute('SELECT id FROM ExamGrades LIMIT 1')
            print("Table 'ExamGrades' already exists.")
        except sqlite3.OperationalError:
            print("Table 'ExamGrades' does not exist.")
            
            # Create the table
            try:
                modify_db('''
                    CREATE TABLE IF NOT EXISTS ExamGrades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        exam_slot_id INTEGER,
                        grade REAL,
                        timestamp TEXT,
                        academic_year_id INTEGER,
                        notes TEXT,
                        FOREIGN KEY(student_id) REFERENCES Students(student_id),
                        FOREIGN KEY(exam_slot_id) REFERENCES ExamSlots(id),
                        FOREIGN KEY(academic_year_id) REFERENCES AcademicYear(id)
                    )
                ''')
                print("Successfully created 'ExamGrades' table.")
            except sqlite3.OperationalError as e:
                print(f"Error creating ExamGrades table: {e}")
        
        # Check if attendance column exists
        try:
            get_db().execute('SELECT attendance FROM ExamGrades LIMIT 1')
            print("Column 'attendance' in ExamGrades table already exists.")
        except sqlite3.OperationalError:
            print("Adding 'attendance' column to ExamGrades table...")
            try:
                modify_db('ALTER TABLE ExamGrades ADD COLUMN attendance INTEGER DEFAULT 1')
                print("Successfully added 'attendance' column to ExamGrades table.")
            except sqlite3.OperationalError as e:
                print(f"Error adding attendance column to ExamGrades table: {e}")
    except Exception as e:
        print(f"Error checking database schema: {e}")

# Register a function to run before the first request
@app.before_request
def before_first_request():
    if not getattr(app, 'schema_checked', False):
        with app.app_context():
            check_database_schema()
        app.schema_checked = True

@app.route('/teams/export/<int:academic_year_id>/<int:lab_slot_id>/')
@login_required
def export_teams(academic_year_id, lab_slot_id):
    # Get academic year and lab slot
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id=?',
        [academic_year_id],
        one=True
    )
    
    lab_slot = query_db(
        'SELECT id, name FROM LabSlots WHERE id=?',
        [lab_slot_id],
        one=True
    )
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('teams_index'))
    
    try:
        # Get students with their team assignments
        students = query_db('''
            SELECT 
                s.student_id, 
                s.name,
                s.email,
                s.username,
                st.team_number
            FROM 
                Students s
            JOIN 
                Enrollments e ON s.student_id = e.student_id
            LEFT JOIN 
                StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
            WHERE 
                e.lab_slot_id = ? AND e.academic_year_id = ?
            ORDER BY 
                st.team_number, s.name
        ''', [lab_slot_id, lab_slot_id, academic_year_id])
        
        if not students:
            flash('No students found for this lab slot', 'warning')
            return redirect(url_for('teams_show', 
                                  academic_year_id=academic_year_id, 
                                  lab_slot_id=lab_slot_id))
        
        # Convert to pandas DataFrame
        student_data = [dict(student) for student in students]
        df_students = pd.DataFrame(student_data)
        
        # Rename columns for better readability
        df_students = df_students.rename(columns={
            'student_id': 'Student ID',
            'name': 'Student Name',
            'email': 'Email',
            'username': 'Username',
            'team_number': 'Team Number'
        })
        
        # Generate filename and export to Excel
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"Teams_{academic_year['semester']}_{academic_year['year']}_{lab_slot['name']}_{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_').replace(' ', '_')
        
        # Create Excel writer with formatting
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Write students to Excel
            df_students.to_excel(writer, sheet_name="Team Assignments", index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Team Assignments"]
            
            # Add filters
            worksheet.autofilter(0, 0, len(df_students), len(df_students.columns) - 1)
            
            # Format headers
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            for col_num, value in enumerate(df_students.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Add conditional formatting for team numbers (color by team)
            # Check if we have the Team Number column and it has values
            if 'Team Number' in df_students.columns:
                # Get unique team numbers, filtering out NaN values
                team_numbers = df_students['Team Number'].dropna().unique()
                
                # Colors for teams
                colors = ['#FFD700', '#98FB98', '#87CEFA', '#FFA07A', '#DDA0DD', '#FFDAB9']
                
                for team_num in team_numbers:
                    if pd.notna(team_num):  # Make sure it's not NaN
                        # Generate a color based on team number (cycling through a few colors)
                        color = colors[int(team_num) % len(colors)]
                        
                        team_format = workbook.add_format({
                            'bg_color': color
                        })
                        
                        # Apply conditional formatting for this team number
                        # Find the column index for Team Number
                        team_col_idx = list(df_students.columns).index('Team Number')
                        
                        worksheet.conditional_format(1, team_col_idx, len(df_students), team_col_idx, {
                            'type': 'cell',
                            'criteria': 'equal to',
                            'value': team_num,
                            'format': team_format
                        })
            
            # Add a second sheet with team summaries
            # Create a summary of students per team
            if 'Team Number' in df_students.columns:
                try:
                    # Count students per team
                    team_counts = df_students.groupby('Team Number').size().reset_index(name='Count')
                    team_counts = team_counts.rename(columns={'Team Number': 'Team', 'Count': 'Number of Students'})
                    
                    # Add team summary sheet
                    team_counts.to_excel(writer, sheet_name="Team Summary", index=False)
                    
                    # Format the summary sheet
                    summary_sheet = writer.sheets["Team Summary"]
                    
                    # Add header formatting
                    for col_num, value in enumerate(team_counts.columns.values):
                        summary_sheet.write(0, col_num, value, header_format)
                except Exception as e:
                    print(f"Error creating team summary: {e}")
                    # Continue without the summary sheet
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        flash(f'Error exporting teams data: {str(e)}', 'danger')
        print(f"Error exporting teams data: {str(e)}")
        return redirect(url_for('teams_show', 
                              academic_year_id=academic_year_id, 
                              lab_slot_id=lab_slot_id))

@app.route('/grades/export/<int:academic_year_id>/<int:lab_slot_id>/')
@login_required
def export_grades(academic_year_id, lab_slot_id):
    # Get academic year and lab slot
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id=?',
        [academic_year_id],
        one=True
    )
    
    lab_slot = query_db(
        'SELECT id, name FROM LabSlots WHERE id=?',
        [lab_slot_id],
        one=True
    )
    
    if not academic_year or not lab_slot:
        flash('Academic year or lab slot not found', 'danger')
        return redirect(url_for('grades_index'))
    
    try:
        # Get all students for this lab slot
        students = query_db('''
            SELECT 
                s.student_id, 
                s.name,
                s.email,
                st.team_number
            FROM 
                Students s
            JOIN 
                Enrollments e ON s.student_id = e.student_id
            LEFT JOIN 
                StudentTeams st ON s.student_id = st.student_id AND st.lab_slot_id = ?
            WHERE 
                e.lab_slot_id = ? AND e.academic_year_id = ?
            ORDER BY 
                st.team_number, s.name
        ''', [lab_slot_id, lab_slot_id, academic_year_id])
        
        if not students:
            flash('No students found for this lab slot', 'warning')
            return redirect(url_for('grades_index'))
            
        # Convert student data to DataFrame
        student_data = [dict(student) for student in students]
        df_students = pd.DataFrame(student_data)
        
        # Get all grades for this lab slot
        grades = query_db('''
            SELECT 
                g.student_id,
                g.exercise_slot,
                g.grade,
                g.timestamp
            FROM 
                Grades g
            WHERE 
                g.lab_slot_id = ? AND g.academic_year_id = ?
        ''', [lab_slot_id, academic_year_id])
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"Grades_{academic_year['semester']}_{academic_year['year']}_{lab_slot['name']}_{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_').replace(' ', '_')
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Create different sheets for different views
            
            # Sheet 1: Student summary with all grades
            if grades:
                # Convert grades to DataFrame
                grades_data = [dict(grade) for grade in grades]
                df_grades = pd.DataFrame(grades_data)
                
                # Create a pivot table
                if not df_grades.empty and 'student_id' in df_grades.columns and 'exercise_slot' in df_grades.columns and 'grade' in df_grades.columns:
                    # Ensure the index and column values exist
                    grades_pivot = pd.pivot_table(
                        df_grades, 
                        values='grade', 
                        index='student_id',
                        columns='exercise_slot', 
                        aggfunc='first'
                    )
                    
                    # Calculate average grade for each student
                    grades_pivot['Average'] = grades_pivot.mean(axis=1, numeric_only=True)
                    
                    # Merge with student info
                    if 'student_id' in df_students.columns:
                        merged_df = pd.merge(
                            df_students, 
                            grades_pivot,
                            left_on='student_id',
                            right_index=True,
                            how='left'
                        )
                        
                        # Rename columns for better readability
                        merged_df = merged_df.rename(columns={
                            'student_id': 'Student ID',
                            'name': 'Student Name',
                            'email': 'Email',
                            'team_number': 'Team'
                        })
                        
                        # Sort by team and student name
                        if 'Team' in merged_df.columns and 'Student Name' in merged_df.columns:
                            merged_df = merged_df.sort_values(by=['Team', 'Student Name'])
                        
                        # Write to Excel
                        merged_df.to_excel(writer, sheet_name="Grades Summary", index=False)
                        
                        # Get workbook and worksheet
                        workbook = writer.book
                        worksheet = writer.sheets["Grades Summary"]
                        
                        # Add filters
                        worksheet.autofilter(0, 0, len(merged_df), len(merged_df.columns) - 1)
                        
                        # Add header formatting
                        header_format = workbook.add_format({
                            'bold': True,
                            'bg_color': '#D3D3D3',
                            'border': 1
                        })
                        
                        for col_num, value in enumerate(merged_df.columns.values):
                            worksheet.write(0, col_num, value, header_format)
                        
                        # Add conditional formatting for grades
                        # Green for good grades (>=8.5), yellow for ok (>=5), red for fail (<5)
                        good_format = workbook.add_format({'bg_color': '#c6efce'})
                        ok_format = workbook.add_format({'bg_color': '#ffeb9c'})
                        fail_format = workbook.add_format({'bg_color': '#ffc7ce'})
                        
                        # Apply to all numeric grade columns (skip the first 4 columns which are student info)
                        for col_num in range(4, len(merged_df.columns)):
                            worksheet.conditional_format(1, col_num, len(merged_df), col_num, {
                                'type': 'cell',
                                'criteria': '>=',
                                'value': 8.5,
                                'format': good_format
                            })
                            
                            worksheet.conditional_format(1, col_num, len(merged_df), col_num, {
                                'type': 'cell',
                                'criteria': 'between',
                                'minimum': 5,
                                'maximum': 8.49,
                                'format': ok_format
                            })
                            
                            worksheet.conditional_format(1, col_num, len(merged_df), col_num, {
                                'type': 'cell',
                                'criteria': '<',
                                'value': 5,
                                'format': fail_format
                            })
                else:
                    # If no proper grade data, just export student list
                    df_students_renamed = df_students.rename(columns={
                        'student_id': 'Student ID',
                        'name': 'Student Name',
                        'email': 'Email',
                        'team_number': 'Team'
                    })
                    
                    df_students_renamed.to_excel(writer, sheet_name="Students", index=False)
            else:
                # If no grades, just export student list
                df_students_renamed = df_students.rename(columns={
                    'student_id': 'Student ID',
                    'name': 'Student Name',
                    'email': 'Email',
                    'team_number': 'Team'
                })
                
                df_students_renamed.to_excel(writer, sheet_name="Students", index=False)
            
            # Sheet 2: Per-exercise details (only if we have grades)
            if grades and len(grades) > 0:
                # Convert grades to DataFrame first
                grades_data = [dict(grade) for grade in grades]
                df_all_grades = pd.DataFrame(grades_data)
                
                if not df_all_grades.empty and 'exercise_slot' in df_all_grades.columns:
                    # Group by exercise slot
                    exercise_slots = sorted(set(df_all_grades['exercise_slot'].tolist()))
                    
                    for i, exercise in enumerate(exercise_slots[:10]):  # Limit to 10 exercises to avoid too many sheets
                        # Filter grades for this exercise
                        exercise_grades = df_all_grades[df_all_grades['exercise_slot'] == exercise]
                        
                        if not exercise_grades.empty and 'student_id' in exercise_grades.columns:
                            # Merge with student info
                            if 'student_id' in df_students.columns:
                                ex_merged = pd.merge(
                                    df_students,
                                    exercise_grades[['student_id', 'grade', 'timestamp']],
                                    on='student_id',
                                    how='left'
                                )
                                
                                # Rename columns
                                ex_merged = ex_merged.rename(columns={
                                    'student_id': 'Student ID',
                                    'name': 'Student Name',
                                    'email': 'Email',
                                    'team_number': 'Team',
                                    'grade': 'Grade',
                                    'timestamp': 'Recorded At'
                                })
                                
                                # Sort by team and student name
                                if 'Team' in ex_merged.columns and 'Student Name' in ex_merged.columns:
                                    ex_merged = ex_merged.sort_values(by=['Team', 'Student Name'])
                                
                                # Limit sheet name length (Excel has a 31 char limit)
                                sheet_name = f"{exercise}"
                                if len(sheet_name) > 31:
                                    sheet_name = sheet_name[:28] + "..."
                                
                                # Write to Excel
                                ex_merged.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        flash(f'Error exporting grades: {str(e)}', 'danger')
        print(f"Error exporting grades: {str(e)}")
        return redirect(url_for('grades_index'))

# Exam Slots routes
@app.route('/exams/')
@login_required
def exam_slots_index():
    # Get all academic years
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    
    # Convert academic_years to a list of dictionaries and add exam slots count
    academic_years_with_counts = []
    for year in academic_years:
        year_dict = dict(year)
        year_dict['exam_slots'] = query_db(
            'SELECT * FROM ExamSlots WHERE academic_year_id = ?', 
            [year_dict['id']]
        )
        academic_years_with_counts.append(year_dict)
    
    return render_template('exam_slots/index.html', academic_years=academic_years_with_counts)

@app.route('/exams/manage/<int:academic_year_id>/')
@login_required
def exam_slots_manage(academic_year_id):
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [academic_year_id], 
        one=True
    )
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Convert academic_year from sqlite row to dict to avoid display issues
    academic_year_dict = dict(academic_year)
    
    # Get all exam slots for this academic year
    exam_slots = query_db('''
        SELECT 
            id, 
            name, 
            date,
            time,
            location,
            academic_year_id,
            exam_period,
            (SELECT COUNT(*) FROM ExamEnrollments WHERE ExamEnrollments.exam_slot_id = ExamSlots.id) as enrollment_count
        FROM ExamSlots
        WHERE academic_year_id = ?
        ORDER BY date, time
    ''', [academic_year_id])
    
    return render_template(
        'exam_slots/manage.html',
        academic_year=academic_year_dict,
        exam_slots=exam_slots
    )

@app.route('/exams/create/<int:academic_year_id>/', methods=['GET', 'POST'])
@login_required
def exam_slots_create(academic_year_id):
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [academic_year_id], 
        one=True
    )
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Convert to dictionary to avoid display issues
    academic_year_dict = dict(academic_year)
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        date = request.form.get('date')
        time = request.form.get('time')
        location = request.form.get('location')
        exam_period = request.form.get('exam_period')
        
        # Validate inputs
        if not name or not date or not time or not location or not exam_period:
            flash('Please fill in all fields', 'danger')
            return redirect(url_for('exam_slots_create', academic_year_id=academic_year_id))
        
        # Create new exam slot
        try:
            modify_db(
                'INSERT INTO ExamSlots (name, date, time, location, academic_year_id, exam_period) VALUES (?, ?, ?, ?, ?, ?)',
                [name, date, time, location, academic_year_id, exam_period]
            )
            flash(f'Exam slot "{name}" created successfully', 'success')
            return redirect(url_for('exam_slots_manage', academic_year_id=academic_year_id))
        except Exception as e:
            flash(f'Error creating exam slot: {e}', 'danger')
            return redirect(url_for('exam_slots_create', academic_year_id=academic_year_id))
    
    return render_template(
        'exam_slots/create.html',
        academic_year=academic_year_dict
    )

@app.route('/exams/edit/<int:exam_slot_id>/', methods=['GET', 'POST'])
@login_required
def exam_slots_edit(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, name, date, time, location, academic_year_id, exam_period FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [exam_slot['academic_year_id']], 
        one=True
    )
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        date = request.form.get('date')
        time = request.form.get('time')
        location = request.form.get('location')
        exam_period = request.form.get('exam_period')
        
        # Validate inputs
        if not name or not date or not time or not location or not exam_period:
            flash('Please fill in all fields', 'danger')
            return redirect(url_for('exam_slots_edit', exam_slot_id=exam_slot_id))
        
        # Update exam slot
        try:
            modify_db(
                'UPDATE ExamSlots SET name = ?, date = ?, time = ?, location = ?, exam_period = ? WHERE id = ?',
                [name, date, time, location, exam_period, exam_slot_id]
            )
            flash(f'Exam slot "{name}" updated successfully', 'success')
            return redirect(url_for('exam_slots_manage', academic_year_id=exam_slot['academic_year_id']))
        except Exception as e:
            flash(f'Error updating exam slot: {e}', 'danger')
            return redirect(url_for('exam_slots_edit', exam_slot_id=exam_slot_id))
    
    return render_template(
        'exam_slots/edit.html',
        exam_slot=exam_slot,
        academic_year=academic_year
    )

@app.route('/exams/delete/<int:exam_slot_id>/', methods=['POST'])
@login_required
def exam_slots_delete(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Delete exam enrollments first
    try:
        modify_db('DELETE FROM ExamEnrollments WHERE exam_slot_id = ?', [exam_slot_id])
        
        # Delete exam slot
        modify_db('DELETE FROM ExamSlots WHERE id = ?', [exam_slot_id])
        
        flash('Exam slot deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting exam slot: {e}', 'danger')
    
    return redirect(url_for('exam_slots_manage', academic_year_id=exam_slot['academic_year_id']))

@app.route('/exams/enrollments/<int:exam_slot_id>/')
@login_required
def exam_slots_enrollments(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, name, date, time, location, academic_year_id, exam_period FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [exam_slot['academic_year_id']], 
        one=True
    )
    
    # Convert to dictionaries to avoid display issues
    exam_slot_dict = dict(exam_slot)
    academic_year_dict = dict(academic_year)
    
    # Get all enrolled students
    enrolled_students = query_db('''
        SELECT 
            s.student_id,
            s.name,
            e.id as enrollment_id
        FROM 
            Students s
        JOIN 
            ExamEnrollments e ON s.student_id = e.student_id
        WHERE 
            e.exam_slot_id = ?
        ORDER BY 
            s.name
    ''', [exam_slot_id])
    
    # Get all students not enrolled yet
    enrolled_ids = ','.join([f"'{s['student_id']}'" for s in enrolled_students]) or "''"
    
    available_students = query_db(f'''
        SELECT 
            student_id,
            name
        FROM 
            Students
        WHERE 
            student_id NOT IN ({enrolled_ids})
        ORDER BY 
            name
    ''')
    
    return render_template(
        'exam_slots/enrollments.html',
        exam_slot=exam_slot_dict,
        academic_year=academic_year_dict,
        enrolled_students=enrolled_students,
        available_students=available_students
    )

@app.route('/exams/enroll/<int:exam_slot_id>/', methods=['POST'])
@login_required
def exam_slots_enroll(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Get selected students
    student_ids = request.form.getlist('student_id')
    
    if not student_ids:
        flash('No students selected', 'warning')
        return redirect(url_for('exam_slots_enrollments', exam_slot_id=exam_slot_id))
    
    # Current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Enroll students
    enroll_count = 0
    for student_id in student_ids:
        # Check if already enrolled
        existing = query_db(
            'SELECT id FROM ExamEnrollments WHERE student_id = ? AND exam_slot_id = ?',
            [student_id, exam_slot_id],
            one=True
        )
        
        if not existing:
            try:
                modify_db(
                    'INSERT INTO ExamEnrollments (student_id, exam_slot_id, academic_year_id, timestamp) VALUES (?, ?, ?, ?)',
                    [student_id, exam_slot_id, exam_slot['academic_year_id'], timestamp]
                )
                enroll_count += 1
            except Exception as e:
                flash(f'Error enrolling student {student_id}: {e}', 'danger')
    
    if enroll_count > 0:
        flash(f'{enroll_count} student(s) enrolled successfully', 'success')
    
    return redirect(url_for('exam_slots_enrollments', exam_slot_id=exam_slot_id))

@app.route('/exams/add_manual/<int:exam_slot_id>/', methods=['POST'])
@login_required
def exam_slots_add_manual(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Get form data
    name = request.form.get('name')
    student_id = request.form.get('student_id')
    
    # Validate inputs
    if not name or not student_id:
        flash('Name and ID are required', 'danger')
        return redirect(url_for('exam_slots_enrollments', exam_slot_id=exam_slot_id))
    
    # Check if student already exists
    existing_student = query_db(
        'SELECT student_id FROM Students WHERE student_id = ?',
        [student_id],
        one=True
    )
    
    # Current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        if not existing_student:
            # Create new student
            modify_db(
                'INSERT INTO Students (student_id, name, email, username) VALUES (?, ?, ?, ?)',
                [student_id, name, f"{student_id}@example.com", student_id.lower()]
            )
        
        # Check if already enrolled
        existing_enrollment = query_db(
            'SELECT id FROM ExamEnrollments WHERE student_id = ? AND exam_slot_id = ?',
            [student_id, exam_slot_id],
            one=True
        )
        
        if existing_enrollment:
            flash(f'Student {name} ({student_id}) is already enrolled', 'warning')
        else:
            # Create enrollment
            modify_db(
                'INSERT INTO ExamEnrollments (student_id, exam_slot_id, academic_year_id, timestamp) VALUES (?, ?, ?, ?)',
                [student_id, exam_slot_id, exam_slot['academic_year_id'], timestamp]
            )
            flash(f'Student {name} ({student_id}) added and enrolled successfully', 'success')
    except Exception as e:
        flash(f'Error adding/enrolling student: {e}', 'danger')
    
    return redirect(url_for('exam_slots_enrollments', exam_slot_id=exam_slot_id))

@app.route('/exams/unenroll/<int:enrollment_id>/', methods=['POST'])
@login_required
def exam_slots_unenroll(enrollment_id):
    # Get enrollment
    enrollment = query_db(
        'SELECT id, exam_slot_id FROM ExamEnrollments WHERE id = ?', 
        [enrollment_id], 
        one=True
    )
    
    if not enrollment:
        flash('Enrollment not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Delete enrollment
    try:
        modify_db('DELETE FROM ExamEnrollments WHERE id = ?', [enrollment_id])
        flash('Student unenrolled successfully', 'success')
    except Exception as e:
        flash(f'Error unenrolling student: {e}', 'danger')
    
    return redirect(url_for('exam_slots_enrollments', exam_slot_id=enrollment['exam_slot_id']))

@app.route('/exams/export/<int:exam_slot_id>/')
@login_required
def export_exam_enrollments(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, name, date, time, location, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [exam_slot['academic_year_id']], 
        one=True
    )
    
    try:
        # Get all enrolled students with additional information
        enrolled_students = query_db('''
            SELECT 
                s.student_id,
                s.name,
                s.email,
                s.username,
                e.id as enrollment_id,
                e.timestamp
            FROM 
                Students s
            JOIN 
                ExamEnrollments e ON s.student_id = e.student_id
            WHERE 
                e.exam_slot_id = ?
            ORDER BY 
                s.name
        ''', [exam_slot_id])
        
        if not enrolled_students:
            flash('No students enrolled in this exam slot', 'warning')
            return redirect(url_for('exam_slots_enrollments', exam_slot_id=exam_slot_id))
        
        # Convert to pandas DataFrame
        student_data = [dict(student) for student in enrolled_students]
        df_students = pd.DataFrame(student_data)
        
        # Rename columns for better readability
        df_students = df_students.rename(columns={
            'student_id': 'Student ID',
            'name': 'Student Name',
            'email': 'Email',
            'username': 'Username',
            'timestamp': 'Enrollment Date'
        })
        
        # Remove enrollment_id column as it's not needed in the export
        if 'enrollment_id' in df_students.columns:
            df_students = df_students.drop(columns=['enrollment_id'])
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"Exam_{academic_year['semester']}_{academic_year['year']}_{exam_slot['name']}_{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_').replace(' ', '_')
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Write students to Excel
            df_students.to_excel(writer, sheet_name="Enrolled Students", index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Enrolled Students"]
            
            # Add filters
            worksheet.autofilter(0, 0, len(df_students), len(df_students.columns) - 1)
            
            # Format headers
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            for col_num, value in enumerate(df_students.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Add exam details sheet
            exam_info = pd.DataFrame([{
                'Name': exam_slot['name'],
                'Date': exam_slot['date'],
                'Time': exam_slot['time'],
                'Location': exam_slot['location'],
                'Academic Year': f"{academic_year['semester']} {academic_year['year']}",
                'Total Enrolled': len(enrolled_students),
                'Export Date': timestamp
            }])
            
            exam_info.to_excel(writer, sheet_name="Exam Details", index=False)
            
            # Format the exam details sheet
            details_sheet = writer.sheets["Exam Details"]
            for col_num, value in enumerate(exam_info.columns.values):
                details_sheet.write(0, col_num, value, header_format)
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'danger')
        print(f"Error exporting exam enrollments: {str(e)}")
        return redirect(url_for('exam_slots_enrollments', exam_slot_id=exam_slot_id))

@app.route('/exams/export_all/<int:academic_year_id>/')
@login_required
def export_all_exam_slots(academic_year_id):
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [academic_year_id], 
        one=True
    )
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    try:
        # Get all exam slots for this academic year
        exam_slots = query_db('''
            SELECT 
                id, 
                name, 
                date,
                time,
                location,
                academic_year_id,
                exam_period,
                (SELECT COUNT(*) FROM ExamEnrollments WHERE ExamEnrollments.exam_slot_id = ExamSlots.id) as enrollment_count
            FROM ExamSlots
            WHERE academic_year_id = ?
            ORDER BY date, time
        ''', [academic_year_id])
        
        if not exam_slots:
            flash('No exam slots found for this academic year', 'warning')
            return redirect(url_for('exam_slots_manage', academic_year_id=academic_year_id))
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"All_Exams_{academic_year['semester']}_{academic_year['year']}_{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_').replace(' ', '_')
        
        # Create Excel writer
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Create a DataFrame for the overview
            exam_slots_data = [dict(slot) for slot in exam_slots]
            df_exams = pd.DataFrame(exam_slots_data)
            
            # Rename columns
            df_exams = df_exams.rename(columns={
                'id': 'Exam ID',
                'name': 'Exam Name',
                'date': 'Date',
                'time': 'Time',
                'location': 'Location',
                'enrollment_count': 'Number of Students'
            })
            
            # Write overview to Excel
            df_exams.to_excel(writer, sheet_name="All Exams", index=False)
            
            # Format the overview sheet
            workbook = writer.book
            worksheet = writer.sheets["All Exams"]
            
            # Add filters
            worksheet.autofilter(0, 0, len(df_exams), len(df_exams.columns) - 1)
            
            # Format headers
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            for col_num, value in enumerate(df_exams.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Add sheet for each exam slot with enrolled students and grades
            for exam_slot in exam_slots:
                # Get all enrolled students for this exam slot 
                enrolled_students = query_db('''
                    SELECT 
                        s.student_id,
                        s.name,
                        s.email,
                        e.timestamp as enrollment_date
                    FROM 
                        Students s
                    JOIN 
                        ExamEnrollments e ON s.student_id = e.student_id
                    WHERE 
                        e.exam_slot_id = ?
                    ORDER BY 
                        s.name
                ''', [exam_slot['id']])
                
                if enrolled_students:
                    # Get grades for these students (if available)
                    grades = query_db('''
                        SELECT 
                            student_id,
                            grade,
                            notes,
                            timestamp as grade_timestamp,
                            attendance
                        FROM 
                            ExamGrades
                        WHERE 
                            exam_slot_id = ?
                    ''', [exam_slot['id']])
                    
                    # Create a dictionary for quick grade lookup
                    grades_dict = {}
                    for grade in grades:
                        grades_dict[grade['student_id']] = dict(grade)
                    
                    # Create complete student data with grades
                    student_data = []
                    for student in enrolled_students:
                        student_dict = dict(student)
                        
                        # If student has grades, add them
                        if student['student_id'] in grades_dict:
                            grade_info = grades_dict[student['student_id']]
                            student_dict['grade'] = grade_info['grade']
                            student_dict['notes'] = grade_info['notes']
                            student_dict['grade_timestamp'] = grade_info['grade_timestamp']
                            student_dict['attendance'] = grade_info['attendance']
                            
                            # Set grade to 0 if absent
                            if grade_info['attendance'] == 0:
                                student_dict['grade'] = 0
                        else:
                            # Default values for students without grades
                            student_dict['grade'] = 0
                            student_dict['notes'] = 'No grade recorded'
                            student_dict['grade_timestamp'] = None
                            student_dict['attendance'] = 0  # Default to absent
                        
                        student_data.append(student_dict)
                    
                    # Convert to DataFrame
                    df_students = pd.DataFrame(student_data)
                    
                    # Rename columns
                    df_students = df_students.rename(columns={
                        'student_id': 'Student ID',
                        'name': 'Student Name',
                        'email': 'Email',
                        'enrollment_date': 'Enrollment Date',
                        'grade': 'Grade',
                        'notes': 'Notes',
                        'grade_timestamp': 'Grade Recorded At',
                        'attendance': 'Attendance'
                    })
                    
                    # Convert attendance to text
                    df_students['Attendance'] = df_students['Attendance'].apply(
                        lambda x: 'Present' if x == 1 else 'Absent'
                    )
                    
                    # Add grade statistics if grades are available
                    has_grades = 'Grade' in df_students.columns
                    grade_stats = {}
                    if has_grades:
                        grades = df_students['Grade']
                        if not grades.empty:
                            grade_stats = {
                                'Average': grades.mean(),
                                'Max': grades.max(),
                                'Min': grades.min(),
                                'Count': len(grades),
                                'Pass Rate': (grades >= 5).mean() * 100  # Percentage of grades >= 5
                            }
                    
                    # Create safe sheet name (limit to 31 chars, Excel limitation)
                    sheet_name = f"{exam_slot['name']}"
                    if len(sheet_name) > 31:
                        sheet_name = sheet_name[:28] + "..."
                    
                    # Write to Excel
                    df_students.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # Format this sheet
                    exam_sheet = writer.sheets[sheet_name]
                    
                    # Add filters
                    exam_sheet.autofilter(0, 0, len(df_students), len(df_students.columns) - 1)
                    
                    # Format headers
                    for col_num, value in enumerate(df_students.columns.values):
                        exam_sheet.write(0, col_num, value, header_format)
                    
                    # Add conditional formatting for grades if they exist
                    if has_grades:
                        # Find the grade column index
                        grade_col_idx = df_students.columns.get_loc('Grade')
                        
                        if grade_col_idx is not None:
                            # Set up formats for different grade ranges
                            good_format = workbook.add_format({'bg_color': '#c6efce', 'font_color': '#006100'})
                            ok_format = workbook.add_format({'bg_color': '#ffeb9c', 'font_color': '#9c6500'})
                            fail_format = workbook.add_format({'bg_color': '#ffc7ce', 'font_color': '#9c0006'})
                            
                            # Apply conditional formatting for grades
                            exam_sheet.conditional_format(1, grade_col_idx, len(df_students), grade_col_idx, {
                                'type': 'cell',
                                'criteria': '>=',
                                'value': 8.5,
                                'format': good_format
                            })
                            
                            exam_sheet.conditional_format(1, grade_col_idx, len(df_students), grade_col_idx, {
                                'type': 'cell',
                                'criteria': 'between',
                                'minimum': 5,
                                'maximum': 8.49,
                                'format': ok_format
                            })
                            
                            exam_sheet.conditional_format(1, grade_col_idx, len(df_students), grade_col_idx, {
                                'type': 'cell',
                                'criteria': '<',
                                'value': 5,
                                'format': fail_format
                            })
                        
                        # Add conditional formatting for attendance
                        attendance_col_idx = df_students.columns.get_loc('Attendance')
                        present_format = workbook.add_format({'bg_color': '#c6efce', 'font_color': '#006100'})
                        absent_format = workbook.add_format({'bg_color': '#ffc7ce', 'font_color': '#9c0006'})
                        
                        exam_sheet.conditional_format(1, attendance_col_idx, len(df_students), attendance_col_idx, {
                            'type': 'text',
                            'criteria': 'containing',
                            'value': 'Present',
                            'format': present_format
                        })
                        
                        exam_sheet.conditional_format(1, attendance_col_idx, len(df_students), attendance_col_idx, {
                            'type': 'text',
                            'criteria': 'containing',
                            'value': 'Absent',
                            'format': absent_format
                        })
            
            # Add a summary sheet for grades
            all_grades = []
            for exam_slot in exam_slots:
                # Get all enrolled students for this exam slot
                enrolled_students = query_db('''
                    SELECT 
                        s.student_id,
                        s.name,
                        e.timestamp
                    FROM 
                        Students s
                    JOIN 
                        ExamEnrollments e ON s.student_id = e.student_id
                    WHERE 
                        e.exam_slot_id = ?
                ''', [exam_slot['id']])
                
                # Get exam slot info
                exam_info = {
                    'exam_name': exam_slot['name'],
                    'date': exam_slot['date']
                }
                
                # Get grades for this exam slot
                grades = query_db('''
                    SELECT 
                        g.student_id,
                        g.grade,
                        g.notes,
                        g.attendance
                    FROM 
                        ExamGrades g
                    WHERE 
                        g.exam_slot_id = ?
                ''', [exam_slot['id']])
                
                # Create dictionary for quick lookup
                grades_dict = {}
                for grade in grades:
                    grades_dict[grade['student_id']] = dict(grade)
                
                # Create a record for each enrolled student
                for student in enrolled_students:
                    student_data = {
                        'student_id': student['student_id'],
                        'name': student['name'],
                        'exam_name': exam_info['exam_name'],
                        'date': exam_info['date']
                    }
                    
                    # If student has a grade, use it
                    if student['student_id'] in grades_dict:
                        grade_data = grades_dict[student['student_id']]
                        student_data['grade'] = grade_data['grade']
                        student_data['notes'] = grade_data['notes']
                        student_data['attendance'] = grade_data['attendance']
                        
                        # Set grade to 0 for absent students
                        if grade_data['attendance'] == 0:
                            student_data['grade'] = 0
                    else:
                        # Default values for students without grades
                        student_data['grade'] = 0
                        student_data['notes'] = 'No grade recorded'
                        student_data['attendance'] = 0
                    
                    # Convert attendance to text
                    student_data['attendance'] = 'Present' if student_data['attendance'] == 1 else 'Absent'
                    
                    all_grades.append(student_data)
            
            if all_grades:
                # Create a summary DataFrame
                df_all_grades = pd.DataFrame(all_grades)
                
                # Rename columns
                df_all_grades = df_all_grades.rename(columns={
                    'student_id': 'Student ID',
                    'name': 'Student Name',
                    'exam_name': 'Exam',
                    'date': 'Exam Date',
                    'grade': 'Grade',
                    'notes': 'Notes',
                    'attendance': 'Attendance'
                })
                
                # Sort by student name and exam
                if 'Student Name' in df_all_grades.columns and 'Exam' in df_all_grades.columns:
                    df_all_grades = df_all_grades.sort_values(by=['Student Name', 'Exam'])
                
                # Write to Excel
                df_all_grades.to_excel(writer, sheet_name="All Grades", index=False)
                
                # Format the sheet
                all_grades_sheet = writer.sheets["All Grades"]
                
                # Add filters
                all_grades_sheet.autofilter(0, 0, len(df_all_grades), len(df_all_grades.columns) - 1)
                
                # Format headers
                for col_num, value in enumerate(df_all_grades.columns.values):
                    all_grades_sheet.write(0, col_num, value, header_format)
                
                # Add conditional formatting for grades
                if 'Grade' in df_all_grades.columns:
                    grade_col_idx = df_all_grades.columns.get_loc('Grade')
                    
                    # Set up formats for different grade ranges
                    good_format = workbook.add_format({'bg_color': '#c6efce', 'font_color': '#006100'})
                    ok_format = workbook.add_format({'bg_color': '#ffeb9c', 'font_color': '#9c6500'})
                    fail_format = workbook.add_format({'bg_color': '#ffc7ce', 'font_color': '#9c0006'})
                    
                    # Apply conditional formatting for grades
                    all_grades_sheet.conditional_format(1, grade_col_idx, len(df_all_grades), grade_col_idx, {
                        'type': 'cell',
                        'criteria': '>=',
                        'value': 8.5,
                        'format': good_format
                    })
                    
                    all_grades_sheet.conditional_format(1, grade_col_idx, len(df_all_grades), grade_col_idx, {
                        'type': 'cell',
                        'criteria': 'between',
                        'minimum': 5,
                        'maximum': 8.49,
                        'format': ok_format
                    })
                    
                    all_grades_sheet.conditional_format(1, grade_col_idx, len(df_all_grades), grade_col_idx, {
                        'type': 'cell',
                        'criteria': '<',
                        'value': 5,
                        'format': fail_format
                    })
                    
                # Add conditional formatting for attendance
                if 'Attendance' in df_all_grades.columns:
                    attendance_col_idx = df_all_grades.columns.get_loc('Attendance')
                    
                    # Format for attendance status
                    present_format = workbook.add_format({'bg_color': '#c6efce', 'font_color': '#006100'})
                    absent_format = workbook.add_format({'bg_color': '#ffc7ce', 'font_color': '#9c0006'})
                    
                    all_grades_sheet.conditional_format(1, attendance_col_idx, len(df_all_grades), attendance_col_idx, {
                        'type': 'text',
                        'criteria': 'containing',
                        'value': 'Present',
                        'format': present_format
                    })
                    
                    all_grades_sheet.conditional_format(1, attendance_col_idx, len(df_all_grades), attendance_col_idx, {
                        'type': 'text',
                        'criteria': 'containing',
                        'value': 'Absent',
                        'format': absent_format
                    })
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'danger')
        print(f"Error exporting all exam slots: {str(e)}")
        return redirect(url_for('exam_slots_manage', academic_year_id=academic_year_id))

# Exam Grades routes
@app.route('/exams/grades/')
@login_required
def exam_grades_index():
    # Get all academic years for the dropdown
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    
    # Convert academic_years to list of dictionaries
    academic_years = [dict(year) for year in academic_years]
    
    # Get exam grade statistics
    exam_grade_records = query_db('''
        SELECT 
            g.academic_year_id,
            g.exam_slot_id,
            MAX(g.timestamp) as timestamp,
            ac.semester || ' ' || ac.year as academic_year_name,
            es.name as exam_slot_name,
            es.date as exam_date,
            COUNT(g.id) as students_count,
            AVG(g.grade) as average_grade
        FROM 
            ExamGrades g
        JOIN 
            AcademicYear ac ON g.academic_year_id = ac.id
        JOIN 
            ExamSlots es ON g.exam_slot_id = es.id
        GROUP BY 
            g.academic_year_id, g.exam_slot_id
        ORDER BY 
            timestamp DESC
    ''')
    
    # Convert grade_records to list of dictionaries
    grade_records = [dict(record) for record in exam_grade_records]
    
    return render_template('exam_slots/grades_index.html', 
                         academic_years=academic_years,
                         grade_records=exam_grade_records)

@app.route('/exams/grades/insert/<int:exam_slot_id>/')
@login_required
def exam_grades_insert(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, name, date, time, location, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_grades_index'))
    
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [exam_slot['academic_year_id']], 
        one=True
    )
    
    # Convert to dictionaries to avoid display issues
    exam_slot_dict = dict(exam_slot)
    academic_year_dict = dict(academic_year)
    
    # Get all enrolled students with their grades (if any)
    students = query_db('''
        SELECT 
            s.student_id,
            s.name,
            e.id as enrollment_id,
            g.grade,
            g.notes,
            g.attendance
        FROM 
            Students s
        JOIN 
            ExamEnrollments e ON s.student_id = e.student_id
        LEFT JOIN
            ExamGrades g ON s.student_id = g.student_id AND g.exam_slot_id = e.exam_slot_id
        WHERE 
            e.exam_slot_id = ?
        ORDER BY 
            s.name
    ''', [exam_slot_id])
    
    return render_template(
        'exam_slots/grades_insert.html',
        exam_slot=exam_slot_dict,
        academic_year=academic_year_dict,
        students=students
    )

@app.route('/exams/grades/save/<int:exam_slot_id>/', methods=['POST'])
@login_required
def exam_grades_save(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_grades_index'))
    
    # Check if attendance column exists in ExamGrades
    try:
        print("Checking if attendance column exists...")
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT attendance FROM ExamGrades LIMIT 1')
        print("Attendance column exists")
    except sqlite3.OperationalError:
        print("Attendance column does not exist. Adding it now...")
        try:
            # Add attendance column
            db.execute('ALTER TABLE ExamGrades ADD COLUMN attendance INTEGER DEFAULT 1')
            db.commit()
            print("Successfully added attendance column to ExamGrades table")
        except Exception as e:
            print(f"Error adding attendance column: {e}")
            flash(f"Error adding attendance column: {e}", "danger")
    
    # Get all enrolled students for this exam slot
    students = query_db('''
        SELECT s.student_id
        FROM Students s
        JOIN ExamEnrollments e ON s.student_id = e.student_id
        WHERE e.exam_slot_id = ?
    ''', [exam_slot_id])
    
    try:
        # Delete existing grade records for this exam slot
        modify_db('DELETE FROM ExamGrades WHERE exam_slot_id = ?', [exam_slot_id])
        
        # Insert new grade records
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = 0
        
        # For debugging
        print("Form data keys:", list(request.form.keys()))
        
        for student in students:
            student_id = student['student_id']
            grade_value = request.form.get(f'grade_{student_id}', '')
            notes = request.form.get(f'notes_{student_id}', '')
            
            # Get attendance value directly from the form
            attendance_key = f'attendance_{student_id}'
            attendance_value = request.form.get(attendance_key)
            
            # Debug print
            print(f"Student {student_id}, attendance value: {attendance_value}")
            
            # Set attendance to 1 if checkbox was checked, otherwise 0
            attendance = 1 if attendance_value == "1" else 0
            
            # If student is absent, set grade to 0 regardless of entered value
            if attendance == 0:
                grade = 0
                if not notes:
                    notes = "Absent from exam"
            elif grade_value.strip():
                try:
                    grade = float(grade_value)
                except ValueError:
                    flash(f'Invalid grade value for student {student_id}, defaulting to 0', 'warning')
                    grade = 0
            else:
                grade = 0
                
            # Insert grade record
            print(f"Inserting grade record for {student_id} with attendance={attendance}")
            modify_db(
                '''INSERT INTO ExamGrades 
                (student_id, exam_slot_id, grade, notes, timestamp, academic_year_id, attendance) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                [student_id, exam_slot_id, grade, notes, timestamp, exam_slot['academic_year_id'], attendance]
            )
            count += 1
        
        flash(f'Grades recorded for {count} students', 'success')
    except Exception as e:
        flash(f'Error saving grades: {str(e)}', 'danger')
        print(f"Error saving exam grades: {str(e)}")
    
    return redirect(url_for('exam_grades_view', exam_slot_id=exam_slot_id))

@app.route('/exams/grades/view/<int:exam_slot_id>/')
@login_required
def exam_grades_view(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, name, date, time, location, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_grades_index'))
    
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [exam_slot['academic_year_id']], 
        one=True
    )
    
    # Convert to dictionaries to avoid display issues
    exam_slot_dict = dict(exam_slot)
    academic_year_dict = dict(academic_year)
    
    # Get exam grades for this exam slot
    grade_records = query_db('''
        SELECT 
            s.student_id,
            s.name,
            g.grade,
            g.notes,
            g.attendance
        FROM 
            ExamGrades g
        JOIN
            Students s ON g.student_id = s.student_id
        WHERE 
            g.exam_slot_id = ?
        ORDER BY 
            s.name
    ''', [exam_slot_id])
    
    # Debug: Print each student's attendance value
    print("Attendance values from database:")
    for record in grade_records:
        print(f"Student {record['student_id']}: attendance = {record['attendance']}")
    
    # Calculate grade statistics
    grade_stats = {
        'total': len(grade_records),
        'average': 0,
        'min': 10,
        'max': 0,
        'distribution': [0] * 10,  # For grades 0-1, 1-2, ..., 9-10
        'present': 0,
        'absent': 0
    }
    
    if grade_stats['total'] > 0:
        total_grade = 0
        for record in grade_records:
            grade = record['grade']
            total_grade += grade
            grade_stats['min'] = min(grade_stats['min'], grade)
            grade_stats['max'] = max(grade_stats['max'], grade)
            
            # Count attendance and debug print
            attendance_value = record['attendance']
            print(f"Processing attendance for {record['student_id']}: attendance value = {attendance_value}, type = {type(attendance_value)}")
            
            if attendance_value == 1:
                grade_stats['present'] += 1
            else:
                grade_stats['absent'] += 1
            
            # Increment the appropriate bin in the distribution
            bin_index = min(int(grade), 9)  # Grades 10 go into the 9-10 bin
            grade_stats['distribution'][bin_index] += 1
            
        grade_stats['average'] = total_grade / grade_stats['total']
    else:
        grade_stats['min'] = 0
    
    # Debug: Print the calculated statistics
    print(f"Grade stats: present={grade_stats['present']}, absent={grade_stats['absent']}, total={grade_stats['total']}")
    
    return render_template(
        'exam_slots/grades_view.html',
        exam_slot=exam_slot_dict,
        academic_year=academic_year_dict,
        grade_records=grade_records,
        grade_stats=grade_stats
    )

@app.route('/exams/grades/export/<int:exam_slot_id>/')
@login_required
def export_exam_grades(exam_slot_id):
    # Get exam slot
    exam_slot = query_db(
        'SELECT id, name, date, time, location, academic_year_id FROM ExamSlots WHERE id = ?', 
        [exam_slot_id], 
        one=True
    )
    
    if not exam_slot:
        flash('Exam slot not found', 'danger')
        return redirect(url_for('exam_grades_index'))
    
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [exam_slot['academic_year_id']], 
        one=True
    )
    
    try:
        # Get all enrolled students
        all_students = query_db('''
            SELECT 
                s.student_id, 
                s.name,
                s.email
            FROM 
                Students s
            JOIN 
                ExamEnrollments e ON s.student_id = e.student_id
            WHERE 
                e.exam_slot_id = ?
            ORDER BY 
                s.name
        ''', [exam_slot_id])
        
        if not all_students:
            flash('No students enrolled in this exam', 'warning')
            return redirect(url_for('exam_grades_view', exam_slot_id=exam_slot_id))
        
        # Get grade records with student details (for those who have grades)
        grade_records = query_db('''
            SELECT 
                s.student_id, 
                g.grade,
                g.notes,
                g.timestamp,
                g.attendance
            FROM 
                ExamGrades g
            JOIN 
                Students s ON g.student_id = s.student_id
            WHERE 
                g.exam_slot_id = ?
        ''', [exam_slot_id])
        
        # Create a dictionary of student_id -> grade data for quick lookup
        grades_by_student = {}
        for record in grade_records:
            grades_by_student[record['student_id']] = dict(record)
        
        # Create a complete dataset with all students
        complete_data = []
        present_count = 0
        absent_count = 0
        
        for student in all_students:
            student_data = dict(student)
            
            # If student has a grade record, use it
            if student['student_id'] in grades_by_student:
                grade_data = grades_by_student[student['student_id']]
                student_data['grade'] = grade_data['grade']
                student_data['notes'] = grade_data['notes']
                student_data['timestamp'] = grade_data['timestamp']
                student_data['attendance'] = grade_data['attendance']
                
                # Count attendance
                if grade_data['attendance'] == 1:
                    present_count += 1
                else:
                    absent_count += 1
                    # Ensure absent students have grade 0
                    student_data['grade'] = 0
            else:
                # For students without grades, set defaults
                student_data['grade'] = 0
                student_data['notes'] = 'No grade recorded'
                student_data['timestamp'] = None
                student_data['attendance'] = 0  # Default to absent
                absent_count += 1
            
            complete_data.append(student_data)
        
        # Convert to pandas DataFrame
        df_grades = pd.DataFrame(complete_data)
        
        # Rename columns for better readability
        df_grades = df_grades.rename(columns={
            'student_id': 'Student ID',
            'name': 'Student Name',
            'email': 'Email',
            'grade': 'Grade',
            'notes': 'Notes',
            'timestamp': 'Last Updated',
            'attendance': 'Attendance'
        })
        
        # Convert attendance numeric value to text
        df_grades['Attendance'] = df_grades['Attendance'].apply(lambda x: 'Present' if x == 1 else 'Absent')
        
        # Calculate attendance rate
        attendance_rate = present_count / len(all_students) * 100 if len(all_students) > 0 else 0
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"Exam_Grades_{exam_slot['name']}_{timestamp}.xlsx"
        filename = filename.replace(':', '_').replace('/', '_').replace('\\', '_').replace(' ', '_')
        
        # Create Excel writer with formatting
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Write grades to Excel
            df_grades.to_excel(writer, sheet_name="Student Grades", index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Student Grades"]
            
            # Add filters
            worksheet.autofilter(0, 0, len(df_grades), len(df_grades.columns) - 1)
            
            # Format headers
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            })
            
            for col_num, value in enumerate(df_grades.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Format the notes column to wrap text
            wrap_format = workbook.add_format({'text_wrap': True})
            notes_col_idx = list(df_grades.columns).index('Notes')
            worksheet.set_column(notes_col_idx, notes_col_idx, 30, wrap_format)
            
            # Add conditional formatting for grades
            grade_col_idx = list(df_grades.columns).index('Grade')
            
            # Format for failing grades (< 5)
            fail_format = workbook.add_format({
                'bg_color': '#FFC7CE',  # Light red
                'font_color': '#9C0006'  # Dark red
            })
            
            # Format for good grades (>= 8.5)
            good_format = workbook.add_format({
                'bg_color': '#C6EFCE',  # Light green
                'font_color': '#006100'  # Dark green
            })
            
            # Apply conditional formatting for failing grades
            worksheet.conditional_format(1, grade_col_idx, len(df_grades), grade_col_idx, {
                'type': 'cell',
                'criteria': '<',
                'value': 5,
                'format': fail_format
            })
            
            # Apply conditional formatting for good grades
            worksheet.conditional_format(1, grade_col_idx, len(df_grades), grade_col_idx, {
                'type': 'cell',
                'criteria': '>=',
                'value': 8.5,
                'format': good_format
            })
            
            # Add conditional formatting for attendance
            attendance_col_idx = list(df_grades.columns).index('Attendance')
            
            # Format for absent students
            absent_format = workbook.add_format({
                'bg_color': '#FFC7CE',  # Light red
                'font_color': '#9C0006'  # Dark red
            })
            
            # Format for present students
            present_format = workbook.add_format({
                'bg_color': '#C6EFCE',  # Light green
                'font_color': '#006100'  # Dark green
            })
            
            # Apply conditional formatting for attendance
            worksheet.conditional_format(1, attendance_col_idx, len(df_grades), attendance_col_idx, {
                'type': 'text',
                'criteria': 'containing',
                'value': 'Absent',
                'format': absent_format
            })
            
            worksheet.conditional_format(1, attendance_col_idx, len(df_grades), attendance_col_idx, {
                'type': 'text',
                'criteria': 'containing',
                'value': 'Present',
                'format': present_format
            })
            
            # Add exam information sheet
            exam_info = pd.DataFrame([{
                'Exam Name': exam_slot['name'],
                'Date': exam_slot['date'],
                'Time': exam_slot['time'],
                'Location': exam_slot['location'],
                'Academic Year': f"{academic_year['semester']} {academic_year['year']}",
                'Total Students': len(all_students),
                'Present Students': present_count,
                'Absent Students': absent_count,
                'Attendance Rate': f"{attendance_rate:.1f}%",
                'Average Grade': df_grades['Grade'].mean() if 'Grade' in df_grades else 0,
                'Export Date': timestamp
            }])
            
            exam_info.to_excel(writer, sheet_name="Exam Information", index=False)
            
            # Format the exam info sheet
            info_sheet = writer.sheets["Exam Information"]
            for col_num, value in enumerate(exam_info.columns.values):
                info_sheet.write(0, col_num, value, header_format)
        
        return send_file(filename, as_attachment=True)
    except Exception as e:
        flash(f'Error exporting grades: {str(e)}', 'danger')
        print(f"Error exporting exam grades: {str(e)}")
        return redirect(url_for('exam_grades_view', exam_slot_id=exam_slot_id))

@app.route('/exams/batch-create/<int:academic_year_id>/', methods=['GET', 'POST'])
@login_required
def exam_slots_batch_create(academic_year_id):
    # Get academic year
    academic_year = query_db(
        'SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
        [academic_year_id], 
        one=True
    )
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('exam_slots_index'))
    
    # Convert to dictionary to avoid display issues
    academic_year_dict = dict(academic_year)
    
    if request.method == 'POST':
        # Get form data
        name_prefix = request.form.get('name_prefix', 'Exam Slot')
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        num_slots = request.form.get('num_slots', type=int)
        location = request.form.get('location')
        exam_period = request.form.get('exam_period', 'June')  # Default to June if not specified
        
        # Validate inputs
        if not date or not start_time or not num_slots or not location or not exam_period:
            flash('Please fill in all fields', 'danger')
            return redirect(url_for('exam_slots_batch_create', academic_year_id=academic_year_id))
        
        if num_slots < 1 or num_slots > 50:
            flash('Number of slots must be between 1 and 50', 'danger')
            return redirect(url_for('exam_slots_batch_create', academic_year_id=academic_year_id))
        
        try:
            # Parse starting time
            from datetime import datetime, timedelta
            
            # Get current time as a starting point
            current_time = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
            
            # Create exam slots
            created_count = 0
            for i in range(1, num_slots + 1):
                slot_start_time = current_time.strftime("%H:%M")
                
                # Each slot is 25 minutes
                slot_end_time = (current_time + timedelta(minutes=25)).strftime("%H:%M")
                slot_time = f"{slot_start_time}-{slot_end_time}"
                
                # Create the slot
                modify_db(
                    'INSERT INTO ExamSlots (name, date, time, location, academic_year_id, exam_period) VALUES (?, ?, ?, ?, ?, ?)',
                    [f"{name_prefix} {i}", date, slot_time, location, academic_year_id, exam_period]
                )
                created_count += 1
                
                # Move to the next slot start time (after 5 minute break)
                current_time = current_time + timedelta(minutes=25 + 5)
                
                # Add extra 5 minute break after every 4 slots
                if i % 4 == 0 and i < num_slots:
                    current_time = current_time + timedelta(minutes=5)
            
            flash(f'Successfully created {created_count} exam slots', 'success')
            return redirect(url_for('exam_slots_manage', academic_year_id=academic_year_id))
            
        except Exception as e:
            flash(f'Error creating exam slots: {str(e)}', 'danger')
            print(f"Error creating exam slots: {str(e)}")
            return redirect(url_for('exam_slots_batch_create', academic_year_id=academic_year_id))
    
    return render_template(
        'exam_slots/batch_create.html',
        academic_year=academic_year_dict
    )

@app.route('/debug/grades/<int:academic_year_id>')
@login_required
def debug_grades(academic_year_id):
    # Get the average grades for the academic year
    avg_grades_by_exercise = query_db('''
        SELECT 
            exercise_slot as exercise_name, 
            ROUND(CAST(AVG(grade) AS REAL), 2) as avg_grade
        FROM 
            Grades
        WHERE 
            academic_year_id = ?
        GROUP BY 
            exercise_slot
        ORDER BY 
            exercise_slot
    ''', [academic_year_id])
    
    # Count total grades
    total_grades = query_db(
        'SELECT COUNT(*) as count FROM Grades WHERE academic_year_id = ?', 
        [academic_year_id], 
        one=True
    )['count']
    
    # Prepare response data
    response_data = {
        'total_grades': total_grades,
        'grades': []
    }
    
    for grade in avg_grades_by_exercise:
        response_data['grades'].append({
            'exercise_name': grade['exercise_name'],
            'avg_grade': float(grade['avg_grade'])
        })
    
    return jsonify(response_data)

# Check and update database schema
def check_database_schema():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Check if exam_period column exists in ExamSlots table
        column_exists = False
        try:
            cursor.execute('SELECT exam_period FROM ExamSlots LIMIT 1')
            column_exists = True
        except sqlite3.OperationalError:
            column_exists = False
        
        # Add exam_period column if it doesn't exist
        if not column_exists:
            try:
                cursor.execute('ALTER TABLE ExamSlots ADD COLUMN exam_period TEXT')
                db.commit()
                print("Added exam_period column to ExamSlots table")
            except sqlite3.OperationalError as e:
                print(f"Error adding exam_period column: {e}")

# Function that was previously decorated with before_first_request
def before_first_request():
    print("Initializing database and checking schema...")
    init_db()
    check_database_schema()

# Register with app in a Flask 2.0+ compatible way
with app.app_context():
    before_first_request()

@app.route('/grades/download_template/')
@login_required
def download_grade_template():
    """Generate and download a template Excel file for grade imports"""
    from create_grade_template import create_grade_template
    import os
    from flask import send_file
    
    academic_year_id = request.args.get('academic_year_id', type=int)
    lab_slot_id = request.args.get('lab_slot_id', type=int)
    exercise_slot = request.args.get('exercise_slot')
    
    if not academic_year_id or not lab_slot_id or not exercise_slot:
        flash('Please provide all required parameters', 'danger')
        return redirect(url_for('grades_index'))
    
    try:
        # Generate the template file
        template_file = create_grade_template(lab_slot_id, exercise_slot, academic_year_id)
        
        # Send the file as a download
        return send_file(
            template_file,
            as_attachment=True,
            download_name=os.path.basename(template_file),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f'Error generating template: {str(e)}', 'danger')
        print(f"Error generating template: {str(e)}")
        return redirect(url_for('grades_insert', 
                             academic_year_id=academic_year_id, 
                             lab_slot_id=lab_slot_id,
                             exercise_slot=exercise_slot))

if __name__ == '__main__':
    try:
        # Create database if it doesn't exist
        if not os.path.exists('student_register.db'):
            conn = sqlite3.connect('student_register.db')
            conn.close()
            print("Database file created.")
        
        # Initialize the database schema
        init_db()
        
        # Launch the application
        print("Database schema initialized successfully.")
        
        # Function to open browser after a delay
        def open_browser():
            time.sleep(1.5)  # Wait for the server to start
            webbrowser.open('http://127.0.0.1:5050')  # Open localhost in the browser
        
        # Check if environment variable is set to avoid duplicate browser windows in debug mode
        if not os.environ.get('WERKZEUG_RUN_MAIN'):
            # Start browser in a separate thread
            threading.Thread(target=open_browser).start()
        
        # Start the Flask app on all interfaces (0.0.0.0)
        # This makes it listen on both localhost and the network IP address
        app.run(debug=True, host='0.0.0.0', port=5050)
    except Exception as e:
        print(f"Error starting application: {e}") 