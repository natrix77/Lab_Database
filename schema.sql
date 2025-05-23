-- Database schema for the lab database application

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0
);

-- Academic Year table
CREATE TABLE IF NOT EXISTS AcademicYear (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year TEXT NOT NULL,
    semester TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Students table
CREATE TABLE IF NOT EXISTS Students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lab Slots table
CREATE TABLE IF NOT EXISTS LabSlots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    academic_year_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (academic_year_id) REFERENCES AcademicYear(id)
);

-- Enrollments table - connecting students to lab slots and academic years
CREATE TABLE IF NOT EXISTS Enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    lab_slot_id INTEGER NOT NULL,
    academic_year_id INTEGER NOT NULL,
    team_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Students(student_id),
    FOREIGN KEY (lab_slot_id) REFERENCES LabSlots(id),
    FOREIGN KEY (academic_year_id) REFERENCES AcademicYear(id)
);

-- Attendance table
CREATE TABLE IF NOT EXISTS Attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    lab_slot_id INTEGER NOT NULL,
    academic_year_id INTEGER NOT NULL,
    exercise_slot TEXT NOT NULL,
    status TEXT NOT NULL, -- Present, Absent, Excused
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Students(student_id),
    FOREIGN KEY (lab_slot_id) REFERENCES LabSlots(id),
    FOREIGN KEY (academic_year_id) REFERENCES AcademicYear(id)
); 