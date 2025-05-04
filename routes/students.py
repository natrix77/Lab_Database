from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db_session, db, AcademicYear, LabSlot, Student, Enrollment, StudentTeam, Attendance, Grade
import pandas as pd
from sqlalchemy import text

students_blueprint = Blueprint('students', __name__)

@students_blueprint.route('/')
def index():
    # Get all students
    students = Student.query.order_by(Student.name).all()
    return render_template('students/index.html', students=students)

@students_blueprint.route('/import', methods=['GET', 'POST'])
def import_students():
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
            lab_slot = LabSlot.query.filter_by(name=lab_slot_name, academic_year_id=academic_year_id).first()
            
            if lab_slot:
                # Ask if user wants to replace data
                replace = request.form.get('replace_data') == 'on'
                
                if replace:
                    # Delete existing enrollments for this lab slot
                    Enrollment.query.filter_by(lab_slot_id=lab_slot.id).delete()
                    
                    # Delete the lab slot
                    db.session.delete(lab_slot)
                    db.session.commit()
                    
                    # Create new lab slot
                    lab_slot = LabSlot(name=lab_slot_name, academic_year_id=academic_year_id)
                    db.session.add(lab_slot)
                    db.session.commit()
                else:
                    flash(f'Lab slot {lab_slot_name} already exists. Please check "Replace existing data" if you want to replace it.', 'warning')
                    return redirect(request.url)
            else:
                # Create new lab slot
                lab_slot = LabSlot(name=lab_slot_name, academic_year_id=academic_year_id)
                db.session.add(lab_slot)
                db.session.commit()
            
            # Insert students and enrollments
            for index, row in df.iterrows():
                student_id = str(row['Αριθμός μητρώου'])
                name = row['Student_Name']
                email = row['E-mail']
                username = row['Όνομα χρήστη (username)']
                
                # Insert student if not exists
                student = Student.query.filter_by(student_id=student_id).first()
                if not student:
                    student = Student(student_id=student_id, name=name, email=email, username=username)
                    db.session.add(student)
                else:
                    # Check if student is already enrolled in this academic year
                    enrollment = Enrollment.query.filter_by(
                        student_id=student_id, 
                        academic_year_id=academic_year_id
                    ).first()
                    
                    if enrollment and enrollment.lab_slot_id != lab_slot.id:
                        flash(f'Student ID {student_id} is already enrolled in this academic year.', 'warning')
                        continue
                
                # Insert enrollment
                enrollment = Enrollment(
                    student_id=student_id,
                    lab_slot_id=lab_slot.id,
                    academic_year_id=academic_year_id
                )
                db.session.add(enrollment)
            
            db.session.commit()
            flash(f'Successfully imported {len(df)} students to lab slot {lab_slot_name}', 'success')
            return redirect(url_for('students.show_students', academic_year_id=academic_year_id))
            
        except Exception as e:
            flash(f'Error importing students: {str(e)}', 'danger')
            return redirect(request.url)
    
    # Get all academic years for the form
    academic_years = AcademicYear.query.order_by(AcademicYear.year, AcademicYear.semester).all()
    
    return render_template('students/import.html', academic_years=academic_years)

@students_blueprint.route('/show/<int:academic_year_id>')
def show_students(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    # Get students for selected lab slots (or all if none selected)
    selected_lab_ids = request.args.getlist('lab_slot_id', type=int)
    
    if selected_lab_ids:
        students = db.session.query(Student, LabSlot.name.label('lab_slot_name')).\
            join(Enrollment, Student.student_id == Enrollment.student_id).\
            join(LabSlot, Enrollment.lab_slot_id == LabSlot.id).\
            filter(Enrollment.academic_year_id == academic_year_id).\
            filter(LabSlot.id.in_(selected_lab_ids)).\
            order_by(LabSlot.name, Student.name).all()
    else:
        students = db.session.query(Student, LabSlot.name.label('lab_slot_name')).\
            join(Enrollment, Student.student_id == Enrollment.student_id).\
            join(LabSlot, Enrollment.lab_slot_id == LabSlot.id).\
            filter(Enrollment.academic_year_id == academic_year_id).\
            order_by(LabSlot.name, Student.name).all()
    
    return render_template(
        'students/show.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        students=students,
        selected_lab_ids=selected_lab_ids
    )

@students_blueprint.route('/manage')
def manage():
    # Get all students with their enrollments and teams
    academic_years = AcademicYear.query.order_by(AcademicYear.year, AcademicYear.semester).all()
    
    selected_year_id = request.args.get('academic_year_id', type=int)
    if selected_year_id:
        academic_year = AcademicYear.query.get_or_404(selected_year_id)
        
        # Get students enrolled in this academic year
        students = db.session.query(Student, LabSlot.name.label('lab_slot_name')).\
            join(Enrollment, Student.student_id == Enrollment.student_id).\
            join(LabSlot, Enrollment.lab_slot_id == LabSlot.id).\
            filter(Enrollment.academic_year_id == selected_year_id).\
            order_by(Student.name).all()
    else:
        academic_year = None
        students = []
    
    return render_template(
        'students/manage.html',
        academic_years=academic_years,
        selected_year=academic_year,
        students=students
    ) 