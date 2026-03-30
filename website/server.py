from flask import Flask, request, jsonify, render_template, session, send_from_directory

import os
import json
import sqlite3
import subprocess
import secrets
from dotenv import load_dotenv

load_dotenv()
print("SERVER.PY LOADED ✅")
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'autograder-fixed-secret-2024')

#-----------------------
# PATHS
#-----------------------
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
AUTOGRADER_DIR = os.path.dirname(BASE_DIR)
LOCAL_AG_DIR   = os.path.join(AUTOGRADER_DIR, 'local_autograder')
RESULTS_PATH   = os.path.join(LOCAL_AG_DIR, 'results_all.json')
FEEDBACK_PATH  = os.path.join(AUTOGRADER_DIR, 'feedback.json')
RUN_ALL_PATH   = os.path.join(AUTOGRADER_DIR, 'run_all.sh')
UPLOAD_DIR     = os.path.join(BASE_DIR, 'Submissions')
DB_PATH        = os.path.join(BASE_DIR, 'website.db')

os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {'py', 'pdf'}

import sys
sys.path.insert(0, AUTOGRADER_DIR)
from canvas_connection import submit_file_to_canvas, post_feedback_comment, DRY_RUN

#-----------------------
# DATABASE SETUP
#-----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            canvas_id TEXT UNIQUE,
            name      TEXT,
            email     TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT,
            canvas_course_id     TEXT,
            canvas_assignment_id TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    INTEGER,
            assignment_id INTEGER,
            filename      TEXT,
            submitted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id)   REFERENCES students(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    INTEGER,
            assignment_id INTEGER,
            test_name     TEXT,
            status        TEXT,
            output        TEXT,
            score         REAL,
            max_score     REAL,
            graded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id)   REFERENCES students(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    INTEGER,
            assignment_id INTEGER,
            feedback_text TEXT,
            generated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id)   REFERENCES students(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS lti_config (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            consumer_key  TEXT,
            shared_secret TEXT,
            canvas_url    TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS lti_state (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            state      TEXT UNIQUE,
            nonce      TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

init_db()

#------------------------
# HELPERS
#------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_results_to_db(student_id, assignment_id, tests):
    conn = get_db()
    c = conn.cursor()
    # Clear old results for this student + assignment
    c.execute('DELETE FROM results WHERE student_id=? AND assignment_id=?', (student_id, assignment_id))
    for t in tests:
        c.execute('''
            INSERT INTO results (student_id, assignment_id, test_name, status, output, score, max_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, assignment_id, t['name'], t['status'], t['output'], t.get('score', 0), t.get('max_score', 0)))
    conn.commit()
    conn.close()

def save_feedback_to_db(student_id, assignment_id, feedback_text):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM feedback WHERE student_id=? AND assignment_id=?', (student_id, assignment_id))
    c.execute('''
        INSERT INTO feedback (student_id, assignment_id, feedback_text)
        VALUES (?, ?, ?)
    ''', (student_id, assignment_id, feedback_text))
    conn.commit()
    conn.close()

#-----------------------
# REGISTER LTI BLUEPRINT
#-----------------------
from lti_routes import lti_bp
app.register_blueprint(lti_bp)

#-----------------------
# TEST LOGIN ROUTES (remove before production)
#-----------------------
@app.route('/test-login1')
def test_login1():
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO students (canvas_id, name, email) VALUES (?, ?, ?)',
              ('student_001', 'Harshini Nujella', 'hnujella@university.edu'))
    c.execute('INSERT OR IGNORE INTO assignments (name, canvas_course_id, canvas_assignment_id) VALUES (?, ?, ?)',
              ('Lab 07', 'course_123', 'assignment_456'))
    conn.commit()
    c.execute('SELECT id FROM students WHERE canvas_id=?', ('student_001',))
    student_id = c.fetchone()['id']
    c.execute('SELECT id FROM assignments WHERE canvas_assignment_id=?', ('assignment_456',))
    assignment_id = c.fetchone()['id']
    conn.close()

    student_name = 'Harshini Nujella'
    session['student_name'] = student_name
    session['student_folder'] = student_name.replace(' ', '_')
    session['assignment_name'] = 'Lab 07'
    session['student_db_id'] = student_id
    session['assignment_db_id'] = assignment_id
    session['canvas_course_id'] = os.environ.get('COURSE_ID', 'course_123')
    session['canvas_assignment_id'] = os.environ.get('ASSIGNMENT_ID', 'assignment_456')
    session['canvas_user_id'] = 'student_001'
    session['lti_version'] = 'test'
    return render_template('homepage.html')

@app.route('/test-login2')
def test_login2():
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO students (canvas_id, name, email) VALUES (?, ?, ?)',
              ('student_002', 'Steve Jobs', 'sjobs@university.edu'))
    c.execute('INSERT OR IGNORE INTO assignments (name, canvas_course_id, canvas_assignment_id) VALUES (?, ?, ?)',
              ('Lab 07', 'course_123', 'assignment_456'))
    conn.commit()
    c.execute('SELECT id FROM students WHERE canvas_id=?', ('student_002',))  # ← fixed
    student_id = c.fetchone()['id']
    c.execute('SELECT id FROM assignments WHERE canvas_assignment_id=?', ('assignment_456',))
    assignment_id = c.fetchone()['id']
    conn.close()

    student_name = 'Steve Jobs'
    session['student_name']         = student_name
    session['student_folder']       = student_name.replace(' ', '_')
    session['assignment_name']      = 'Lab 07'
    session['student_db_id']        = student_id
    session['assignment_db_id']     = assignment_id
    session['canvas_course_id']     = os.environ.get('COURSE_ID', 'course_123')
    session['canvas_assignment_id'] = os.environ.get('ASSIGNMENT_ID', 'assignment_456')
    session['canvas_user_id']       = 'student_002'
    session['lti_version']          = 'test'
    return render_template('homepage.html')

#-----------------------
# ROUTES
#-----------------------
@app.route('/static/<path:filename>')
def static_files(filename):
    response = send_from_directory('static', filename)
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response

@app.route('/')
def index():
    return render_template('homepage.html')

@app.after_request
def add_headers(response):
    response.headers['ngrok-skip-browser-warning'] = 'true'
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://catcourses.ucmerced.edu"
    return response

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    reupload = request.form.get('reupload') == 'true'
    original_name = request.form.get('original_name', '').strip()

    if file.filename == '':
        return jsonify({'success': False, 'error': 'Empty filename'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Only .py and .pdf files are allowed'}), 400
    
    # LTI info: 
    student_db_id    = session.get('student_db_id')
    assignment_db_id = session.get('assignment_db_id')
    student_name     = session.get('student_name')
    folder_name      = session.get('student_folder', student_name.replace(' ', '_'))
    
    print(f"UPLOAD DEBUG - student_db_id: {student_db_id}")
    print(f"UPLOAD DEBUG - assignment_db_id: {assignment_db_id}")
    print(f"UPLOAD DEBUG - student_name: {student_name}")

    if not student_name:
        return jsonify({'success': False, 'error': 'Unknown student — please access this page through Canvas.'}), 403
    
    folder_name = student_name.replace(' ', '_')
    student_folder = os.path.join(UPLOAD_DIR, folder_name)
    os.makedirs(student_folder, exist_ok=True)
    
    # If re-uploading, clear the student's folder contents but keep the folder
    # if reupload and original_name:
    #     for f in os.listdir(student_folder):
    #         os.remove(os.path.join(student_folder, f))

    for f in os.listdir(student_folder):
        file_path = os.path.join(student_folder, f)
        if os.path.isfile(file_path):
            os.remove(file_path)

    dest = os.path.join(student_folder, file.filename)
    file.save(dest)

    # Save folder name in session so /grade knows which folder to grade
    session['student_folder'] = folder_name
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO submissions (student_id, assignment_id, filename) VALUES (?, ?, ?)',
              (student_db_id, assignment_db_id, file.filename))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/grade', methods=['POST'])
def grade():
    try:
        # Check session for student folder
        student_folder = session.get('student_folder')
        student_id    = session.get('student_db_id')
        assignment_id = session.get('assignment_db_id') 
        
        print(f"GRADE DEBUG - student_id: {student_id}")
        print(f"GRADE DEBUG - assignment_id: {assignment_id}")
        print(f"GRADE DEBUG - student_folder: {student_folder}")
      
        if not student_id or not assignment_id:
            return jsonify({'success': False, 'error': 'Unknown student — please access this page through Canvas.'})    
        if not student_folder:
            return jsonify({'success': False, 'error': 'No submission found. Please upload a file first.'})

        # Run bash script
        result = subprocess.run(
            ['bash', RUN_ALL_PATH, student_folder],
            text=True,
            timeout=300,
            cwd=AUTOGRADER_DIR
        )

        if result.returncode != 0:
            return jsonify({'success': False, 'error': 'Grading failed — check terminal for details.'})

        # Load results_all.json
        if not os.path.exists(RESULTS_PATH):
            return jsonify({'success': False, 'error': 'results_all.json not found after grading.'})

        with open(RESULTS_PATH, 'r') as f:
            data = json.load(f)

        tests = []
        if isinstance(data, dict):
            student_data = data.get(student_folder, {})  # ← only this student's data
            if isinstance(student_data, dict):
                test_list = student_data.get('tests', [])
                if not isinstance(student_data, dict):
                    test_list = student_data.get('tests', [])
                for t in test_list:
                    tests.append({
                        'name': t.get('name', 'Unknown'),
                        'status': t.get('status', 'unknown'),
                        'output': t.get('output', '').strip(),
                        'score': t.get('score', 0),
                        'max_score': t.get('max_score', 0)
                    })

        total_score = sum(t['score'] for t in tests)
        total_possible = sum(t['max_score'] for t in tests)
        total  = len(tests)
        passed = sum(1 for t in tests if t['status'] == 'passed')
        failed = total - passed

        # Save results to DB
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM results WHERE student_id=? AND assignment_id=?', (student_id, assignment_id))
        for t in tests:
            c.execute('''
                INSERT INTO results (student_id, assignment_id, test_name, status, output, score, max_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, assignment_id, t['name'], t['status'], t['output'], t['score'], t['max_score']))
        conn.commit()
        conn.close()

        # Load feedback.json
        feedback_text = None
        if os.path.exists(FEEDBACK_PATH):
            with open(FEEDBACK_PATH, 'r') as f:
                feedback_data = json.load(f)

            if isinstance(feedback_data, list):
                parts = []
                for entry in feedback_data:
                    if isinstance(entry, dict):
                        fb = entry.get('feedback', '')
                        name = entry.get('full_name', '')
                        if fb:
                            parts.append(f"{name}: {fb}" if name else fb)
                    elif isinstance(entry, str):
                        parts.append(entry)
                feedback_text = '\n\n'.join(parts)
            elif isinstance(feedback_data, str):
                feedback_text = feedback_data

        # Save feedback to DB
        if feedback_text:
            conn = get_db()
            c = conn.cursor()
            c.execute('DELETE FROM feedback WHERE student_id=? AND assignment_id=?', (student_id, assignment_id))
            c.execute('''
                INSERT INTO feedback (student_id, assignment_id, feedback_text)
                VALUES (?, ?, ?)
            ''', (student_id, assignment_id, feedback_text))
            conn.commit()
            conn.close()

        return jsonify({
            'success': True,
            'tests': tests,
            'total': total,
            'passed': passed,
            'failed': failed,
            'total_score': total_score,
            'total_possible': total_possible,
            'feedback': feedback_text
        })

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Grading timed out after 5 minutes.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/submit', methods=['POST'])
def submit():
    try:
        student_name         = session.get('student_name')
        course_id            = session.get('canvas_course_id')
        assignment_id        = session.get('canvas_assignment_id')
        canvas_user_id       = session.get('canvas_user_id')
        student_db_id        = session.get('student_db_id')
        assignment_db_id     = session.get('assignment_db_id')
        student_folder       = session.get('student_folder')

        print(f"SUBMIT DEBUG - course_id: {course_id}")
        print(f"SUBMIT DEBUG - assignment_id: {assignment_id}")
        print(f"SUBMIT DEBUG - canvas_user_id: {canvas_user_id}")
        
        if not student_name or not course_id or not canvas_user_id:
            return jsonify({'success': False, 'error': 'Missing Canvas info — please access through Canvas.'})

        if not student_folder:
            return jsonify({'success': False, 'error': 'No submission found — please upload a file first.'})

        # Find the uploaded file in the student's folder
        student_folder_path = os.path.join(UPLOAD_DIR, student_folder)
        files = [f for f in os.listdir(student_folder_path) if os.path.isfile(os.path.join(student_folder_path, f))]

        if not files:
            return jsonify({'success': False, 'error': 'No file found in submission folder.'})

        filename  = files[0]  # take the first (and should be only) file
        file_path = os.path.join(student_folder_path, filename)

        # Submit file to Canvas
        submit_file_to_canvas(course_id, assignment_id, canvas_user_id, file_path, filename, student_name=student_name)

        # Also post feedback as a comment if available
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            SELECT feedback_text FROM feedback
            WHERE student_id=? AND assignment_id=?
            ORDER BY generated_at DESC LIMIT 1
        ''', (student_db_id, assignment_db_id))
        row = c.fetchone()
        conn.close()

        if row and row['feedback_text']:
            post_feedback_comment(course_id, assignment_id, canvas_user_id, row['feedback_text'])

        return jsonify({
            'success': True,
            'dry_run': DRY_RUN,
            'message': 'Dry run — nothing posted.' if DRY_RUN else f'"{filename}" submitted to Canvas successfully!'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, use_reloader=False)
    