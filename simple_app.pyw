import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, g, send_file
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['DATABASE'] = 'student_register.db'

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

# Home route
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

# Dashboard route
@app.route('/dashboard')
def dashboard():
    # Get filter parameters
    academic_year_id = request.args.get('academic_year_id', type=int)
    
    # Get basic statistics
    stats = {}
    
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
        
        year_key = f"{selected_academic_year['semester']} {selected_academic_year['year']}"
        lab_slots_by_year = {year_key: lab_slots}
        
        # Get team distribution for the selected academic year
        team_counts = query_db('''
            SELECT LabSlots.name, COUNT(DISTINCT StudentTeams.team_number) as count
            FROM StudentTeams
            JOIN LabSlots ON StudentTeams.lab_slot_id = LabSlots.id
            WHERE LabSlots.academic_year_id = ?
            GROUP BY LabSlots.name
        ''', [academic_year_id])
        
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
    else:
        # No filter, get all statistics
        selected_academic_year = None
        
        # Count students, lab slots, and absences
        stats['total_students'] = query_db('SELECT COUNT(*) as count FROM Students', one=True)['count']
        stats['total_lab_slots'] = query_db('SELECT COUNT(*) as count FROM LabSlots', one=True)['count']
        stats['absences'] = query_db('SELECT COUNT(*) as count FROM Attendance WHERE status = "Absent"', one=True)['count']
        
        # Get academic years
        academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
        
        # Get lab slots by academic year
        lab_slots_by_year = {}
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
            
            year_key = f"{year['semester']} {year['year']}"
            lab_slots_by_year[year_key] = lab_slots
        
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
        absences=stats['absences'],
        team_counts=team_counts,
        lab_slots_by_academic_year=lab_slots_by_year,
        absences_by_lab=absences_by_lab
    )

# Update the URL routes for dashboard in base.html
@app.context_processor
def inject_globals():
    return {
        'request': request
    }

# Academic Year routes
@app.route('/academic/')
def academic_year_index():
    # Get all academic years
    academic_years = query_db('SELECT id, semester, year FROM AcademicYear ORDER BY year, semester')
    return render_template('academic/index.html', academic_years=academic_years)

@app.route('/academic/create/', methods=['GET', 'POST'])
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
def grades_final():
    academic_year_id = request.args.get('academic_year_id', type=int)
    
    if not academic_year_id:
        flash('Please select an academic year', 'danger')
        return redirect(url_for('grades_index'))
    
    academic_year = query_db('SELECT id, semester, year FROM AcademicYear WHERE id = ?', 
                           [academic_year_id], one=True)
    
    if not academic_year:
        flash('Academic year not found', 'danger')
        return redirect(url_for('grades_index'))
    
    # Get all lab slots for this academic year
    lab_slots = query_db('''
        SELECT id, name 
        FROM LabSlots 
        WHERE academic_year_id = ?
        ORDER BY name
    ''', [academic_year_id])
    
    # Get students with their final grades
    students = query_db('''
        SELECT 
            s.student_id, 
            s.name,
            fg.lab_average,
            fg.jun_exam_grade,
            fg.sep_exam_grade,
            fg.final_grade
        FROM 
            Students s
        JOIN 
            Enrollments e ON s.student_id = e.student_id
        LEFT JOIN 
            FinalGrades fg ON s.student_id = fg.student_id AND fg.academic_year_id = ?
        WHERE 
            e.academic_year_id = ?
        GROUP BY 
            s.student_id
        ORDER BY 
            s.name
    ''', [academic_year_id, academic_year_id])
    
    # For each student, calculate average lab grade if not already set
    for student in students:
        if student['lab_average'] is None:
            # Calculate average lab grade
            avg_grades = query_db('''
                SELECT AVG(grade) as avg_grade
                FROM Grades
                WHERE student_id = ? AND academic_year_id = ?
            ''', [student['student_id'], academic_year_id], one=True)
            
            if avg_grades and avg_grades['avg_grade']:
                student['calculated_lab_average'] = round(avg_grades['avg_grade'], 2)
            else:
                student['calculated_lab_average'] = 0
    
    return render_template('grades/final.html',
                          academic_year=academic_year,
                          lab_slots=lab_slots,
                          students=students)

@app.route('/grades/final/save/', methods=['POST'])
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
def student_detail(student_id):
    # Get student info
    student = query_db('SELECT * FROM Students WHERE student_id = ?', [student_id], one=True)
    
    if not student:
        flash('Student not found', 'danger')
        return redirect(url_for('students_index'))
    
    # Get enrollments
    enrollments = query_db('''
        SELECT 
            e.id,
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
    ''', [student_id])
    
    # Get team assignments
    teams = query_db('''
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
    ''', [student_id])
    
    # Get attendance records
    attendance = query_db('''
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
    ''', [student_id])
    
    # Get grades
    grades = query_db('''
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
    ''', [student_id])
    
    # Get final grades
    final_grades = query_db('''
        SELECT 
            fg.*,
            ac.semester,
            ac.year
        FROM 
            FinalGrades fg
        JOIN 
            AcademicYear ac ON fg.academic_year_id = ac.id
        WHERE 
            fg.student_id = ?
        ORDER BY 
            ac.year DESC, ac.semester
    ''', [student_id])
    
    return render_template('students/detail.html',
                         student=student,
                         enrollments=enrollments,
                         teams=teams,
                         attendance=attendance,
                         grades=grades,
                         final_grades=final_grades)

@app.route('/students/edit/<string:student_id>/', methods=['GET', 'POST'])
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
        
        # Get lab slot IDs for 2024
        lab_slot_2024_1 = query_db('SELECT id FROM LabSlots WHERE name = ? AND academic_year_id = ?', 
                                 ["ΠΕΜΠΤΗ 15:00-17:00 (A)", academic_year_2024], one=True)['id']
        
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

        db.commit()
        print("Database schema initialized successfully.")

@app.route('/export_all_data/<int:academic_year_id>/')
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
def upgrade_database():
    try:
        # Initialize connection
        conn = sqlite3.connect(app.config['DATABASE'])
        cursor = conn.cursor()
        
        # Check if column exists
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
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error starting application: {e}") 