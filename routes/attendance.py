from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db_session, db, AcademicYear, LabSlot, Student, Enrollment, StudentTeam, Attendance
from datetime import datetime

attendance_blueprint = Blueprint('attendance', __name__)

@attendance_blueprint.route('/')
def index():
    # Get all academic years
    academic_years = AcademicYear.query.order_by(AcademicYear.year, AcademicYear.semester).all()
    
    return render_template(
        'attendance/index.html',
        academic_years=academic_years
    )

@attendance_blueprint.route('/record/<int:academic_year_id>', methods=['GET', 'POST'])
def record(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    if not lab_slots:
        flash('No lab slots found for this academic year', 'warning')
        return redirect(url_for('attendance.index'))
    
    # Get selected lab slot
    selected_lab_id = request.args.get('lab_slot_id', type=int) or request.form.get('lab_slot_id', type=int)
    
    if not selected_lab_id and lab_slots:
        selected_lab_id = lab_slots[0].id
    
    # Get exercise slot
    exercise_slot = request.args.get('exercise_slot') or request.form.get('exercise_slot')
    exercise_slots = ["Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Replacement1", "Replacement2", "Exam.Jun", "Exam.Sep"]
    
    if not exercise_slot and exercise_slots:
        exercise_slot = exercise_slots[0]
    
    # If form is submitted
    if request.method == 'POST' and 'save_attendance' in request.form:
        # Get all students for this lab slot
        student_ids = request.form.getlist('student_id')
        statuses = request.form.getlist('status')
        
        # Save attendance
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for student_id, status in zip(student_ids, statuses):
            # Check if attendance record already exists
            attendance = Attendance.query.filter_by(
                student_id=student_id,
                lab_slot_id=selected_lab_id,
                exercise_slot=exercise_slot,
                academic_year_id=academic_year_id
            ).first()
            
            if attendance:
                # Update existing record
                attendance.status = status
                attendance.timestamp = timestamp
            else:
                # Create new record
                attendance = Attendance(
                    student_id=student_id,
                    lab_slot_id=selected_lab_id,
                    exercise_slot=exercise_slot,
                    status=status,
                    timestamp=timestamp,
                    academic_year_id=academic_year_id
                )
                db.session.add(attendance)
        
        db.session.commit()
        flash('Attendance records saved successfully', 'success')
        return redirect(url_for(
            'attendance.record',
            academic_year_id=academic_year_id,
            lab_slot_id=selected_lab_id,
            exercise_slot=exercise_slot
        ))
    
    # Get lab slot name
    lab_slot = None
    if selected_lab_id:
        lab_slot = LabSlot.query.get(selected_lab_id)
    
    # Get students and their attendance
    if lab_slot and exercise_slot:
        students = db.session.query(
            Student,
            Attendance.status,
            Attendance.timestamp
        ).join(
            Enrollment,
            Student.student_id == Enrollment.student_id
        ).outerjoin(
            Attendance,
            (Student.student_id == Attendance.student_id) &
            (Attendance.lab_slot_id == selected_lab_id) &
            (Attendance.exercise_slot == exercise_slot) &
            (Attendance.academic_year_id == academic_year_id)
        ).filter(
            Enrollment.academic_year_id == academic_year_id,
            Enrollment.lab_slot_id == selected_lab_id
        ).order_by(
            Student.name
        ).all()
        
        # Check if attendance has been recorded
        attendance_recorded = any(status is not None for _, status, _ in students)
    else:
        students = []
        attendance_recorded = False
    
    return render_template(
        'attendance/record.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        selected_lab=lab_slot,
        exercise_slots=exercise_slots,
        selected_exercise_slot=exercise_slot,
        students=students,
        attendance_recorded=attendance_recorded
    )

@attendance_blueprint.route('/show/<int:academic_year_id>')
def show(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    # Get selected lab slots
    selected_lab_ids = request.args.getlist('lab_slot_id', type=int)
    
    if not selected_lab_ids and lab_slots:
        selected_lab_ids = [lab_slots[0].id]
    
    # Get selected exercise slots
    selected_exercise_slots = request.args.getlist('exercise_slot')
    exercise_slots = ["Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Replacement1", "Replacement2", "Exam.Jun", "Exam.Sep"]
    
    if not selected_exercise_slots:
        selected_exercise_slots = exercise_slots
    
    # Get attendance records
    attendance_data = {}
    
    for lab_id in selected_lab_ids:
        lab_slot = LabSlot.query.get(lab_id)
        
        if lab_slot:
            # Get students for this lab slot
            students = db.session.query(
                Student
            ).join(
                Enrollment,
                Student.student_id == Enrollment.student_id
            ).filter(
                Enrollment.academic_year_id == academic_year_id,
                Enrollment.lab_slot_id == lab_id
            ).order_by(
                Student.name
            ).all()
            
            # Get attendance for each student
            students_with_attendance = []
            
            for student in students:
                # Get attendance records for this student
                attendance_records = Attendance.query.filter(
                    Attendance.student_id == student.student_id,
                    Attendance.academic_year_id == academic_year_id,
                    Attendance.lab_slot_id == lab_id,
                    Attendance.exercise_slot.in_(selected_exercise_slots)
                ).all()
                
                # Create a dictionary of exercise_slot -> status
                attendance_by_slot = {
                    record.exercise_slot: record.status
                    for record in attendance_records
                }
                
                # Count absences
                absences = sum(1 for record in attendance_records if record.status == 'Absent')
                
                students_with_attendance.append((student, attendance_by_slot, absences))
            
            attendance_data[lab_slot.name] = students_with_attendance
    
    return render_template(
        'attendance/show.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        selected_lab_ids=selected_lab_ids,
        exercise_slots=exercise_slots,
        selected_exercise_slots=selected_exercise_slots,
        attendance_data=attendance_data
    )

@attendance_blueprint.route('/absences/<int:academic_year_id>')
def absences(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    # Get selected lab slots
    selected_lab_ids = request.args.getlist('lab_slot_id', type=int)
    
    if not selected_lab_ids and lab_slots:
        selected_lab_ids = [lab_slots[0].id]
    
    # Get students with absences
    students_with_absences = db.session.query(
        Student,
        LabSlot.name.label('lab_slot_name'),
        db.func.count(Attendance.id).label('absence_count')
    ).join(
        Enrollment,
        Student.student_id == Enrollment.student_id
    ).join(
        LabSlot,
        Enrollment.lab_slot_id == LabSlot.id
    ).join(
        Attendance,
        (Student.student_id == Attendance.student_id) &
        (Attendance.lab_slot_id == LabSlot.id) &
        (Attendance.status == 'Absent')
    ).filter(
        Enrollment.academic_year_id == academic_year_id,
        LabSlot.id.in_(selected_lab_ids)
    ).group_by(
        Student.student_id,
        LabSlot.id
    ).order_by(
        db.func.count(Attendance.id).desc(),
        LabSlot.name,
        Student.name
    ).all()
    
    return render_template(
        'attendance/absences.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        selected_lab_ids=selected_lab_ids,
        students_with_absences=students_with_absences
    ) 