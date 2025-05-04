from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import db_session, db, AcademicYear, LabSlot, Student, Enrollment, StudentTeam
import pandas as pd
from datetime import datetime
import os

teams_blueprint = Blueprint('teams', __name__)

@teams_blueprint.route('/')
def index():
    # Get all academic years
    academic_years = AcademicYear.query.order_by(AcademicYear.year, AcademicYear.semester).all()
    
    return render_template(
        'teams/index.html',
        academic_years=academic_years
    )

@teams_blueprint.route('/assign/<int:academic_year_id>', methods=['GET', 'POST'])
def assign(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    if not lab_slots:
        flash('No lab slots found for this academic year', 'warning')
        return redirect(url_for('teams.index'))
    
    selected_lab_id = request.args.get('lab_slot_id', type=int) or request.form.get('lab_slot_id', type=int)
    
    if not selected_lab_id and lab_slots:
        selected_lab_id = lab_slots[0].id
    
    if request.method == 'POST':
        if 'assign_team' in request.form:
            team_number = request.form.get('team_number', type=int)
            student_ids = request.form.getlist('student_id')
            
            if not team_number or not student_ids:
                flash('Please select a team number and at least one student', 'danger')
                return redirect(url_for('teams.assign', academic_year_id=academic_year_id, lab_slot_id=selected_lab_id))
            
            # Assign students to team
            for student_id in student_ids:
                # Check if student is already in a team
                existing_team = StudentTeam.query.filter_by(
                    student_id=student_id,
                    lab_slot_id=selected_lab_id
                ).first()
                
                if existing_team:
                    # Update team number
                    existing_team.team_number = team_number
                else:
                    # Create new team assignment
                    team = StudentTeam(
                        student_id=student_id,
                        lab_slot_id=selected_lab_id,
                        team_number=team_number
                    )
                    db.session.add(team)
            
            db.session.commit()
            flash(f'Successfully assigned {len(student_ids)} students to Team {team_number}', 'success')
            
        elif 'remove_from_team' in request.form:
            student_ids = request.form.getlist('student_id')
            
            if not student_ids:
                flash('Please select at least one student', 'danger')
                return redirect(url_for('teams.assign', academic_year_id=academic_year_id, lab_slot_id=selected_lab_id))
            
            # Remove students from their teams
            for student_id in student_ids:
                team = StudentTeam.query.filter_by(
                    student_id=student_id,
                    lab_slot_id=selected_lab_id
                ).first()
                
                if team:
                    db.session.delete(team)
            
            db.session.commit()
            flash(f'Successfully removed {len(student_ids)} students from their teams', 'success')
    
    # Get lab slot name
    lab_slot = None
    if selected_lab_id:
        lab_slot = LabSlot.query.get(selected_lab_id)
    
    # Get students and their team assignments
    if lab_slot:
        students_with_teams = db.session.query(
            Student, 
            StudentTeam.team_number
        ).join(
            Enrollment, 
            Student.student_id == Enrollment.student_id
        ).outerjoin(
            StudentTeam,
            (Student.student_id == StudentTeam.student_id) & 
            (StudentTeam.lab_slot_id == selected_lab_id)
        ).filter(
            Enrollment.academic_year_id == academic_year_id,
            Enrollment.lab_slot_id == selected_lab_id
        ).order_by(
            StudentTeam.team_number,
            Student.name
        ).all()
        
        # Get assigned and unassigned counts
        assigned_count = sum(1 for _, team_number in students_with_teams if team_number is not None)
        total_count = len(students_with_teams)
        unassigned_count = total_count - assigned_count
    else:
        students_with_teams = []
        assigned_count = 0
        total_count = 0
        unassigned_count = 0
    
    return render_template(
        'teams/assign.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        selected_lab=lab_slot,
        students_with_teams=students_with_teams,
        assigned_count=assigned_count,
        total_count=total_count,
        unassigned_count=unassigned_count
    )

@teams_blueprint.route('/show/<int:academic_year_id>')
def show(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    # Get selected lab slots
    selected_lab_ids = request.args.getlist('lab_slot_id', type=int)
    
    if not selected_lab_ids and lab_slots:
        selected_lab_ids = [lab_slots[0].id]
    
    # Get teams for the selected lab slots
    teams_by_lab = {}
    
    for lab_id in selected_lab_ids:
        lab_slot = LabSlot.query.get(lab_id)
        
        if lab_slot:
            teams = db.session.query(
                StudentTeam.team_number,
                db.func.count(StudentTeam.id).label('student_count')
            ).filter(
                StudentTeam.lab_slot_id == lab_id
            ).group_by(
                StudentTeam.team_number
            ).order_by(
                StudentTeam.team_number
            ).all()
            
            # Get students for each team
            teams_with_students = []
            for team_number, student_count in teams:
                students = db.session.query(Student).join(
                    StudentTeam,
                    Student.student_id == StudentTeam.student_id
                ).filter(
                    StudentTeam.lab_slot_id == lab_id,
                    StudentTeam.team_number == team_number
                ).order_by(
                    Student.name
                ).all()
                
                teams_with_students.append((team_number, students))
            
            teams_by_lab[lab_slot.name] = teams_with_students
    
    return render_template(
        'teams/show.html',
        academic_year=academic_year,
        lab_slots=lab_slots,
        selected_lab_ids=selected_lab_ids,
        teams_by_lab=teams_by_lab
    )

@teams_blueprint.route('/export/<int:academic_year_id>')
def export(academic_year_id):
    academic_year = AcademicYear.query.get_or_404(academic_year_id)
    
    # Get all lab slots for this academic year
    lab_slots = LabSlot.query.filter_by(academic_year_id=academic_year_id).all()
    
    # Get selected lab slot
    selected_lab_id = request.args.get('lab_slot_id', type=int)
    
    if not selected_lab_id and lab_slots:
        selected_lab_id = lab_slots[0].id
    
    lab_slot = LabSlot.query.get(selected_lab_id)
    
    if not lab_slot:
        flash('Please select a lab slot', 'danger')
        return redirect(url_for('teams.show', academic_year_id=academic_year_id))
    
    # Get teams and students for this lab slot
    team_data = []
    
    # Get all team numbers for this lab slot
    team_numbers = db.session.query(
        StudentTeam.team_number
    ).filter(
        StudentTeam.lab_slot_id == selected_lab_id
    ).distinct().order_by(
        StudentTeam.team_number
    ).all()
    
    # For each team, get the students
    for team_number, in team_numbers:
        students = db.session.query(
            Student
        ).join(
            StudentTeam,
            Student.student_id == StudentTeam.student_id
        ).filter(
            StudentTeam.lab_slot_id == selected_lab_id,
            StudentTeam.team_number == team_number
        ).order_by(
            Student.name
        ).all()
        
        # Add to team data
        for idx, student in enumerate(students):
            team_data.append({
                'Team': f'Team {team_number}',
                'Student ID': student.student_id,
                'Name': student.name,
                'Email': student.email,
                'Username': student.username
            })
    
    # Create DataFrame and export to Excel
    if team_data:
        df = pd.DataFrame(team_data)
        
        timestamp = datetime.now().strftime("%Y.%m.%d.%H.%M.%S")
        filename = f"Teams_{lab_slot.name}_{academic_year.semester}_{academic_year.year}_{timestamp}.xlsx"
        
        df.to_excel(filename, index=False)
        
        flash(f'Successfully exported teams to {filename}', 'success')
        return redirect(url_for('teams.show', academic_year_id=academic_year_id, lab_slot_id=selected_lab_id))
    else:
        flash('No team data to export', 'warning')
        return redirect(url_for('teams.show', academic_year_id=academic_year_id, lab_slot_id=selected_lab_id)) 