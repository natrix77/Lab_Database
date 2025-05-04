from sqlalchemy import Column, Integer, String, Float, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, scoped_session, sessionmaker
from datetime import datetime

# Create engine and session
engine = create_engine('sqlite:///student_register.db')
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

# Create a db object to be imported by routes
class SQLAlchemyDB:
    def __init__(self, session):
        self.session = session
    
    def commit(self):
        self.session.commit()
    
    def add(self, obj):
        self.session.add(obj)
    
    def rollback(self):
        self.session.rollback()
    
    def remove(self):
        self.session.remove()

# Create db instance
db = SQLAlchemyDB(db_session)

class AcademicYear(Base):
    __tablename__ = 'AcademicYear'
    id = Column(Integer, primary_key=True, autoincrement=True)
    semester = Column(String(10))
    year = Column(Integer)
    lab_slots = relationship('LabSlot', backref='academic_year', lazy=True)
    enrollments = relationship('Enrollment', backref='academic_year', lazy=True)
    attendances = relationship('Attendance', backref='academic_year', lazy=True)
    grades = relationship('Grade', backref='academic_year', lazy=True)
    final_grades = relationship('FinalGrade', backref='academic_year', lazy=True)

    def __repr__(self):
        return f"{self.semester} {self.year}"

class LabSlot(Base):
    __tablename__ = 'LabSlots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    academic_year_id = Column(Integer, ForeignKey('AcademicYear.id'))
    enrollments = relationship('Enrollment', backref='lab_slot', lazy=True)
    teams = relationship('StudentTeam', backref='lab_slot', lazy=True)
    attendances = relationship('Attendance', backref='lab_slot', lazy=True)
    grades = relationship('Grade', backref='lab_slot', lazy=True)

    def __repr__(self):
        return f"{self.name}"

class Student(Base):
    __tablename__ = 'Students'
    student_id = Column(String(20), primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    registration_number = Column(String(20))
    username = Column(String(100))
    enrollments = relationship('Enrollment', backref='student', lazy=True)
    teams = relationship('StudentTeam', backref='student', lazy=True)
    attendances = relationship('Attendance', backref='student', lazy=True)
    grades = relationship('Grade', backref='student', lazy=True)
    final_grades = relationship('FinalGrade', backref='student', lazy=True)

    def __repr__(self):
        return f"{self.name} ({self.student_id})"

class Enrollment(Base):
    __tablename__ = 'Enrollments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey('Students.student_id'))
    lab_slot_id = Column(Integer, ForeignKey('LabSlots.id'))
    academic_year_id = Column(Integer, ForeignKey('AcademicYear.id'))

class StudentTeam(Base):
    __tablename__ = 'StudentTeams'
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_number = Column(Integer)
    student_id = Column(String(20), ForeignKey('Students.student_id'))
    lab_slot_id = Column(Integer, ForeignKey('LabSlots.id'))

class Attendance(Base):
    __tablename__ = 'Attendance'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey('Students.student_id'))
    lab_slot_id = Column(Integer, ForeignKey('LabSlots.id'))
    exercise_slot = Column(String(20))
    status = Column(String(10))  # Present, Absent
    timestamp = Column(String(20))
    academic_year_id = Column(Integer, ForeignKey('AcademicYear.id'))

class Grade(Base):
    __tablename__ = 'Grades'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey('Students.student_id'))
    lab_slot_id = Column(Integer, ForeignKey('LabSlots.id'))
    exercise_slot = Column(String(20))
    grade = Column(Float)
    timestamp = Column(String(20))
    academic_year_id = Column(Integer, ForeignKey('AcademicYear.id'))

class FinalGrade(Base):
    __tablename__ = 'FinalGrades'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey('Students.student_id'))
    lab_average = Column(Float)
    jun_exam_grade = Column(Float)
    sep_exam_grade = Column(Float)
    final_grade = Column(Float)
    academic_year_id = Column(Integer, ForeignKey('AcademicYear.id'))

def init_db():
    Base.metadata.create_all(bind=engine)

def shutdown_session():
    db_session.remove() 