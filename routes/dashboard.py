from flask import Blueprint, render_template, request
from models import db_session, db, AcademicYear, LabSlot, Student, Enrollment, StudentTeam, Attendance, Grade
from sqlalchemy import func
import sqlite3

dashboard_blueprint = Blueprint('dashboard', __name__)

@dashboard_blueprint.route('/')
def index():
    # Get selected academic year
    academic_year_id = request.args.get('academic_year_id', type=int)
    
    # Get all academic years for the dropdown
    academic_years = AcademicYear.query.all()
    selected_academic_year = None
    
    if academic_year_id:
        selected_academic_year = AcademicYear.query.get(academic_year_id)
    
    # Apply filter if academic year is selected
    lab_slot_filter = {}
    if academic_year_id:
        lab_slot_filter['academic_year_id'] = academic_year_id
    
    # Total counts
    total_students = Student.query.count()
    total_lab_slots = LabSlot.query.filter_by(**lab_slot_filter).count()
    
    # Absences count
    if academic_year_id:
        absences = Attendance.query.filter_by(status='Absent', academic_year_id=academic_year_id).count()
    else:
        absences = Attendance.query.filter_by(status='Absent').count()
    
    # Team distribution
    team_query = db_session.query(
        LabSlot.name, 
        func.count(StudentTeam.id).label('count')
    ).join(
        StudentTeam, 
        StudentTeam.lab_slot_id == LabSlot.id
    )
    
    if academic_year_id:
        team_query = team_query.filter(LabSlot.academic_year_id == academic_year_id)
    
    team_counts = team_query.group_by(LabSlot.name).all()
    
    # Absences by lab slot
    absences_query = db_session.query(
        LabSlot.name.label('lab_name'),
        func.count(Attendance.id).label('absent_count')
    ).join(
        Attendance,
        Attendance.lab_slot_id == LabSlot.id
    ).filter(
        Attendance.status == 'Absent'
    )
    
    if academic_year_id:
        absences_query = absences_query.filter(LabSlot.academic_year_id == academic_year_id)
    
    absences_by_lab = absences_query.group_by(LabSlot.name).all()
    
    # Lab slots breakdown by academic year
    lab_slots_by_academic_year = {}
    
    if academic_year_id:
        year = AcademicYear.query.get(academic_year_id)
        lab_slots = LabSlot.query.filter_by(academic_year_id=year.id).all()
        lab_slots_by_academic_year[str(year)] = lab_slots
    else:
        for year in academic_years:
            lab_slots = LabSlot.query.filter_by(academic_year_id=year.id).all()
            lab_slots_by_academic_year[str(year)] = lab_slots
    
    return render_template(
        'dashboard/index.html',
        academic_years=academic_years,
        selected_academic_year=selected_academic_year,
        total_students=total_students,
        total_lab_slots=total_lab_slots,
        absences=absences,
        team_counts=team_counts,
        absences_by_lab=absences_by_lab,
        lab_slots_by_academic_year=lab_slots_by_academic_year
    ) 