from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from models import db_session, db, AcademicYear, LabSlot, Student, Enrollment, StudentTeam, Attendance, Grade, FinalGrade
import pandas as pd
import os
from datetime import datetime
import sqlite3

academic_year_blueprint = Blueprint('academic_year', __name__)

@academic_year_blueprint.route('/')
def index():
    # Get all academic years
    academic_years = AcademicYear.query.order_by(AcademicYear.year, AcademicYear.semester).all()
    
    return render_template(
        'academic/index.html',
        academic_years=academic_years
    )

@academic_year_blueprint.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        semester = request.form.get('semester')
        year = request.form.get('year')
        
        # Validate inputs
        if not semester or not year:
            flash('Please provide both semester and year', 'danger')
            return redirect(url_for('academic_year.create'))
        
        # Check if already exists
        existing = AcademicYear.query.filter_by(semester=semester, year=year).first()
        if existing:
            flash(f'Academic year {semester} {year} already exists', 'warning')
            return redirect(url_for('academic_year.index'))
            
        # Create new academic year
        new_academic_year = AcademicYear(semester=semester, year=year)
        db.session.add(new_academic_year)
        db.session.commit()
        
        flash(f'Academic year {semester} {year} created successfully', 'success')
        return redirect(url_for('academic_year.index'))
        
    return render_template('academic/create.html')

@academic_year_blueprint.route('/export_data')
def export_data():
    # Get all academic years
    academic_years = AcademicYear.query.order_by(AcademicYear.year, AcademicYear.semester).all()
    
    return render_template(
        'academic/export_data.html',
        academic_years=academic_years
    )

@academic_year_blueprint.route('/export/<int:academic_year_id>/<int:lab_slot_id>')
def export_lab_slot_data(academic_year_id, lab_slot_id):
    """Export data for a specific lab slot to Excel"""
    
    # Get academic year and lab slot
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    lab_slot = LabSlot.query.get_or_404(lab_slot_id)
    
    # Create a DataFrame for students in this lab slot
    conn = sqlite3.connect('student_register.db')
    
    # Get students with their team numbers and attendance
    query = """
    SELECT 
        s.student_id, 
        s.name, 
        s.email, 
        s.username,
        st.team_number,
        (SELECT COUNT(*) FROM Attendance a WHERE a.student_id = s.student_id 
            AND a.lab_slot_id = ? AND a.academic_year_id = ? AND a.status = 'Absent') as absences
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
    """
    
    df = pd.read_sql_query(
        query, 
        conn, 
        params=(lab_slot_id, academic_year_id, lab_slot_id, lab_slot_id, academic_year_id)
    )
    
    # Get grades for each student
    grades_query = """
    SELECT 
        s.student_id,
        g.exercise_slot,
        g.grade
    FROM 
        Students s
    INNER JOIN 
        Grades g ON s.student_id = g.student_id
    WHERE 
        g.lab_slot_id = ? AND g.academic_year_id = ?
    """
    
    grades_df = pd.read_sql_query(
        grades_query, 
        conn, 
        params=(lab_slot_id, academic_year_id)
    )
    
    # Pivot the grades DataFrame
    if not grades_df.empty:
        grades_pivot = grades_df.pivot(index='student_id', columns='exercise_slot', values='grade')
        
        # Merge with the main DataFrame
        df = df.merge(grades_pivot, left_on='student_id', right_index=True, how='left')
    
    conn.close()
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
    filename = f"{academic_year.semester}.{academic_year.year}.{timestamp}.xlsx"
    
    # Export to Excel
    df.to_excel(filename, index=False)
    
    # Return the file for download
    return send_file(filename, as_attachment=True) 