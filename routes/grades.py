from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db_session, db, AcademicYear, LabSlot, Student, Enrollment, Grade, FinalGrade
from datetime import datetime
from sqlalchemy import text

grades_blueprint = Blueprint('grades', __name__)

@grades_blueprint.route('/')
def index():
    # Get all academic years
    academic_years = AcademicYear.query.order_by(AcademicYear.year, AcademicYear.semester).all()
    
    return render_template(
        'grades/index.html',
        academic_years=academic_years
    )

@grades_blueprint.route('/insert/<int:academic_year_id>', methods=['GET', 'POST'])
def insert(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    if not lab_slots:
        flash('No lab slots found for this academic year', 'warning')
        return redirect(url_for('grades.index'))
    
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
    if request.method == 'POST' and 'save_grades' in request.form:
        # Get all students for this lab slot
        student_ids = request.form.getlist('student_id')
        grades = request.form.getlist('grade')
        
        # Save grades
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for student_id, grade_value in zip(student_ids, grades):
            if grade_value.strip():  # Only save if grade is not empty
                try:
                    grade_value = float(grade_value)
                    
                    # Check if grade record already exists
                    grade = Grade.query.filter_by(
                        student_id=student_id,
                        lab_slot_id=selected_lab_id,
                        exercise_slot=exercise_slot,
                        academic_year_id=academic_year_id
                    ).first()
                    
                    if grade:
                        # Update existing record
                        grade.grade = grade_value
                        grade.timestamp = timestamp
                    else:
                        # Create new record
                        grade = Grade(
                            student_id=student_id,
                            lab_slot_id=selected_lab_id,
                            exercise_slot=exercise_slot,
                            grade=grade_value,
                            timestamp=timestamp,
                            academic_year_id=academic_year_id
                        )
                        db.session.add(grade)
                except ValueError:
                    flash(f'Invalid grade for student {student_id}: {grade_value}', 'danger')
                    continue
        
        db.session.commit()
        flash('Grades saved successfully', 'success')
        return redirect(url_for(
            'grades.insert',
            academic_year_id=academic_year_id,
            lab_slot_id=selected_lab_id,
            exercise_slot=exercise_slot
        ))
    
    # Get lab slot name
    lab_slot = None
    if selected_lab_id:
        lab_slot = LabSlot.query.get(selected_lab_id)
    
    # Get students and their grades
    if lab_slot and exercise_slot:
        students = db.session.query(
            Student,
            Grade.grade,
            Grade.timestamp
        ).join(
            Enrollment,
            Student.student_id == Enrollment.student_id
        ).outerjoin(
            Grade,
            (Student.student_id == Grade.student_id) &
            (Grade.lab_slot_id == selected_lab_id) &
            (Grade.exercise_slot == exercise_slot) &
            (Grade.academic_year_id == academic_year_id)
        ).filter(
            Enrollment.academic_year_id == academic_year_id,
            Enrollment.lab_slot_id == selected_lab_id
        ).order_by(
            Student.name
        ).all()
        
        # Check if grades have been recorded
        grades_recorded = any(grade is not None for _, grade, _ in students)
    else:
        students = []
        grades_recorded = False
    
    return render_template(
        'grades/insert.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        selected_lab=lab_slot,
        exercise_slots=exercise_slots,
        selected_exercise_slot=exercise_slot,
        students=students,
        grades_recorded=grades_recorded
    )

@grades_blueprint.route('/show/<int:academic_year_id>')
def show(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    # Get selected lab slots
    selected_lab_ids = request.args.getlist('lab_slot_id', type=int)
    
    if not selected_lab_ids and lab_slots:
        selected_lab_ids = [lab_slots[0].id]
    
    # Get grades for each lab slot
    grades_data = {}
    
    for lab_id in selected_lab_ids:
        lab_slot = LabSlot.query.get(lab_id)
        
        if lab_slot:
            # Get all exercise slots that have grades for this lab slot
            exercise_slots = db.session.query(
                Grade.exercise_slot
            ).filter(
                Grade.lab_slot_id == lab_id,
                Grade.academic_year_id == academic_year_id
            ).distinct().order_by(
                Grade.exercise_slot
            ).all()
            
            exercise_slots = [slot[0] for slot in exercise_slots]
            
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
            
            # Get grades for each student
            students_with_grades = []
            
            for student in students:
                # Get grades for all exercise slots
                grades = {}
                total_grades = 0
                grade_count = 0
                
                for slot in exercise_slots:
                    grade = Grade.query.filter_by(
                        student_id=student.student_id,
                        lab_slot_id=lab_id,
                        exercise_slot=slot,
                        academic_year_id=academic_year_id
                    ).first()
                    
                    if grade:
                        grades[slot] = grade.grade
                        total_grades += grade.grade
                        grade_count += 1
                
                # Calculate average
                average = total_grades / grade_count if grade_count > 0 else None
                
                students_with_grades.append((student, grades, average))
            
            grades_data[lab_slot.name] = {
                'exercise_slots': exercise_slots,
                'students': students_with_grades
            }
    
    return render_template(
        'grades/show.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        selected_lab_ids=selected_lab_ids,
        grades_data=grades_data
    )

@grades_blueprint.route('/calculate_final/<int:academic_year_id>', methods=['GET', 'POST'])
def calculate_final(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    if request.method == 'POST':
        # Get all students for this academic year
        students = db.session.query(
            Student
        ).join(
            Enrollment,
            Student.student_id == Enrollment.student_id
        ).filter(
            Enrollment.academic_year_id == academic_year_id
        ).distinct().all()
        
        for student in students:
            # Get lab average
            lab_average = db.session.query(
                db.func.avg(Grade.grade)
            ).filter(
                Grade.student_id == student.student_id,
                Grade.academic_year_id == academic_year_id,
                ~Grade.exercise_slot.in_(["Exam.Jun", "Exam.Sep"])
            ).scalar() or 0
            
            # Get exam grades
            jun_exam_grade = db.session.query(
                Grade.grade
            ).filter(
                Grade.student_id == student.student_id,
                Grade.academic_year_id == academic_year_id,
                Grade.exercise_slot == "Exam.Jun"
            ).scalar()
            
            sep_exam_grade = db.session.query(
                Grade.grade
            ).filter(
                Grade.student_id == student.student_id,
                Grade.academic_year_id == academic_year_id,
                Grade.exercise_slot == "Exam.Sep"
            ).scalar()
            
            # Calculate final grade (40% lab, 60% exam)
            exam_grade = sep_exam_grade if sep_exam_grade is not None else (jun_exam_grade if jun_exam_grade is not None else 0)
            final_grade = 0.4 * lab_average + 0.6 * exam_grade if exam_grade is not None else None
            
            # Update or create final grade record
            final_grade_record = FinalGrade.query.filter_by(
                student_id=student.student_id,
                academic_year_id=academic_year_id
            ).first()
            
            if final_grade_record:
                final_grade_record.lab_average = lab_average
                final_grade_record.jun_exam_grade = jun_exam_grade
                final_grade_record.sep_exam_grade = sep_exam_grade
                final_grade_record.final_grade = final_grade
            else:
                final_grade_record = FinalGrade(
                    student_id=student.student_id,
                    academic_year_id=academic_year_id,
                    lab_average=lab_average,
                    jun_exam_grade=jun_exam_grade,
                    sep_exam_grade=sep_exam_grade,
                    final_grade=final_grade
                )
                db.session.add(final_grade_record)
        
        db.session.commit()
        flash('Final grades calculated successfully', 'success')
        return redirect(url_for('grades.final', academic_year_id=academic_year_id))
    
    return render_template(
        'grades/calculate.html',
        academic_year=academic_year
    )

@grades_blueprint.route('/final/<int:academic_year_id>')
def final(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all final grades for this academic year
    final_grades = db.session.query(
        Student,
        FinalGrade
    ).join(
        FinalGrade,
        Student.student_id == FinalGrade.student_id
    ).filter(
        FinalGrade.academic_year_id == academic_year_id
    ).order_by(
        FinalGrade.final_grade.desc(),
        Student.name
    ).all()
    
    return render_template(
        'grades/final.html',
        academic_year=academic_year,
        final_grades=final_grades
    ) 