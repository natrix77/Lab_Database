import os
from flask import Flask, render_template, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
import sqlite3
import random
from datetime import datetime, timedelta

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///student_register.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set up CSRF protection
csrf = CSRFProtect(app)

# Import models (after app is created)
from models import db_session, db, init_db, AcademicYear, LabSlot, Student, Enrollment, StudentTeam, Attendance, Grade, FinalGrade

# Import routes after app is created to avoid circular imports
from routes.dashboard import dashboard_blueprint
from routes.academic_year import academic_year_blueprint
from routes.students import students_blueprint
from routes.teams import teams_blueprint
from routes.attendance import attendance_blueprint
from routes.grades import grades_blueprint

# Register blueprints
app.register_blueprint(dashboard_blueprint)
app.register_blueprint(academic_year_blueprint, url_prefix='/academic')
app.register_blueprint(students_blueprint, url_prefix='/students')
app.register_blueprint(teams_blueprint, url_prefix='/teams')
app.register_blueprint(attendance_blueprint, url_prefix='/attendance')
app.register_blueprint(grades_blueprint, url_prefix='/grades')

@app.route('/')
def index():
    return redirect(url_for('dashboard.index'))

@app.route('/init_test_data')
def init_test_data_route():
    # Add a test academic year
    academic_year = AcademicYear.query.filter_by(semester='ΕΑΡΙΝΟ', year=2025).first()
    if not academic_year:
        academic_year = AcademicYear(semester='ΕΑΡΙΝΟ', year=2025)
        db.session.add(academic_year)
        db.session.commit()
    
    # Add some test lab slots
    lab_slots = []
    for day in ['ΔΕΥΤΕΡΑ', 'ΤΡΙΤΗ', 'ΤΕΤΑΡΤΗ', 'ΠΕΜΠΤΗ', 'ΠΑΡΑΣΚΕΥΗ']:
        for time_slot in ['09:00-11:00', '11:00-13:00', '13:00-15:00', '15:00-17:00', '17:00-19:00']:
            slot_name = f"{day} {time_slot}"
            lab_slot = LabSlot.query.filter_by(name=slot_name, academic_year_id=academic_year.id).first()
            if not lab_slot:
                lab_slot = LabSlot(name=slot_name, academic_year_id=academic_year.id)
                db.session.add(lab_slot)
            lab_slots.append(lab_slot)
    
    db.session.commit()
    
    # Add some test students if there are none
    if Student.query.count() == 0:
        greek_names = ["Γεώργιος", "Ιωάννης", "Κωνσταντίνος", "Νικόλαος", "Δημήτριος", 
                   "Παναγιώτης", "Βασίλειος", "Μιχαήλ", "Αντώνιος", "Χρήστος", 
                   "Αθανάσιος", "Ευάγγελος", "Σπυρίδων", "Αναστάσιος", "Στέφανος",
                   "Μαρία", "Ελένη", "Αικατερίνη", "Βασιλική", "Σοφία", 
                   "Αναστασία", "Ευαγγελία", "Ιωάννα", "Δήμητρα", "Παρασκευή"]
        
        greek_surnames = ["Παπαδόπουλος", "Βασιλείου", "Αντωνίου", "Γεωργίου", "Νικολάου", 
                      "Δημητρίου", "Παπαδάκης", "Ιωάννου", "Κωνσταντίνου", "Μακρής",
                      "Παπαδοπούλου", "Βασιλείου", "Αντωνίου", "Γεωργίου", "Νικολάου", 
                      "Δημητρίου", "Παπαδάκη", "Ιωάννου", "Κωνσταντίνου", "Μακρή"]
        
        for i in range(1, 101):
            name = f"{random.choice(greek_surnames)} {random.choice(greek_names)}"
            student_id = f"tp{20230000 + i}"
            email = f"{student_id}@teiath.gr"
            username = f"tp{i}"
            
            student = Student(
                student_id=student_id,
                name=name,
                email=email,
                username=username
            )
            db.session.add(student)
            
            # Enroll student in a random lab slot
            lab_slot = random.choice(lab_slots)
            enrollment = Enrollment(
                student_id=student_id,
                lab_slot_id=lab_slot.id,
                academic_year_id=academic_year.id
            )
            db.session.add(enrollment)
    
    db.session.commit()
    
    flash("Test data has been initialized!", "success")
    return redirect(url_for('dashboard.index'))

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == '__main__':
    try:
        # Create database if it doesn't exist
        if not os.path.exists('student_register.db'):
            conn = sqlite3.connect('student_register.db')
            conn.close()
            print("Database file created.")
        
        # Initialize the database schema
        init_db()
        print("Database schema initialized.")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error starting application: {e}") 