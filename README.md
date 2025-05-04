# Student Register Book 📚

A web application for managing lab students, teams, attendance, and grades.

![Flask](https://img.shields.io/badge/Flask-3.0.2-blue)
![SQLite](https://img.shields.io/badge/SQLite-3-green)
![Python](https://img.shields.io/badge/Python-3.8+-yellow)

## Features

- Dashboard with summary statistics (absences, teams, lab slots)
- Import students from Excel files
- Assign students to teams
- Record attendance for lab sessions
- Track and view students' absences
- Insert and manage grades
- Calculate final grades
- Export data to Excel

## Installation

1. Make sure you have Python 3.8+ installed
2. Clone this repository
3. Create a virtual environment:
   ```
   python -m venv venv
   ```
4. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
5. Install dependencies:
   ```
   pip install -r requirements-web.txt
   ```

## Running the Application

1. Activate the virtual environment (if not already activated)
2. Run the Flask application:
   ```
   python app.py
   ```
3. Open your browser and navigate to `http://127.0.0.1:5000`

## Usage Guide

### 1. Create/Update Database

- Start by accessing the "Create/Update DB" page
- This will set up the necessary database tables or update the existing ones

### 2. Import Students

- Go to the "Import Students" page
- Select an academic year or create a new one
- Upload an Excel file containing student information
- The system will extract the lab slot name and student data

### 3. Assign Teams

- Go to the "Assign Teams" page
- Select the academic year and lab slot
- Assign students to teams by selecting students and entering a team number
- View current team assignments

### 4. Record Attendance

- Go to the "Record Attendance" page
- Select the academic year, lab slot, and exercise slot
- Mark students as present or absent
- Save the attendance records

### 5. Insert Grades

- Go to the "Insert Grades" page
- Select the academic year, lab slot, and exercise slot
- Enter grades for each student
- View and calculate final grades

### 6. Export Data

- Go to the "Export Data" page
- Select the academic year and lab slot
- Export student data, team assignments, attendance, and grades to Excel

## Data Structure

The application uses SQLite to store the following data:

- Academic years (semester and year)
- Lab slots
- Students
- Team assignments
- Attendance records
- Grades
- Final grades

## Dashboard

The dashboard provides an overview of:

- Total number of students
- Lab slots available by academic year
- Student absences
- Team distribution across lab slots

## Live Demo

Check out the [live demo](https://natrix77.github.io/Lab_Database/) on GitHub Pages.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions or issues, please open an issue on GitHub. 
