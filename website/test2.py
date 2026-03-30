from flask import Flask, request, jsonify, render_template, session
import os
import json
import sqlite3
import subprocess
import shutil
import secrets

import hashlib
import hmac
import base64
import urllib.parse
import time

from dotenv import load_dotenv
from lti_routes import lti_bp
load_dotenv()
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.register_blueprint(lti_bp)

#------------------------
# PATHS
#------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # website/
AUTOGRADER_DIR = os.path.dirname(BASE_DIR)  # Autograder_research/
LOCAL_AG_DIR = os.path.join(AUTOGRADER_DIR, 'local_autograder') #local_autograder/
RESULTS_PATH = os.path.join(LOCAL_AG_DIR, 'results_all.json')
FEEDBACK_PATH = os.path.join(AUTOGRADER_DIR, 'feedback.json')
RUN_ALL_PATH = os.path.join(AUTOGRADER_DIR, 'run_all.sh')
UPLOAD_DIR= os.path.join(BASE_DIR, 'Submissions')
DB_PATH= os.path.join(BASE_DIR, 'website.db')

#------------------------
# LTI 1.1 Config
#------------------------

LTI_CONSUMER_KEY   = os.environ.get('LTI_CONSUMER_KEY', 'autograder_key')
LTI_SHARED_SECRET  = os.environ.get('LTI_SHARED_SECRET', 'autograder_secret')


os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {'py', 'pdf'}

#------------------------
# LTI Setup
#------------------------
@app.route('/lti-launch', methods=['POST'])
def lti_launch():
    try:
        params = dict(request.form)
        # Flatten single-value lists
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}

        # Check OAuth signature
        consumer_key = params.get('oauth_consumer_key', '')

        if consumer_key != LTI_CONSUMER_KEY:
            return "Unauthorized: invalid consumer key", 403

        # Check timestamp is within 5 minutes - to prevent replay attacks
        oauth_timestamp = int(params.get('oauth_timestamp', 0))
        if abs(time.time() - oauth_timestamp) > 300:
            return "Unauthorized: timestamp expired", 403

        # Student info from Canvas
        canvas_user_id  = params.get('user_id', '')
        student_name    = params.get('lis_person_name_full', 'Unknown Student')
        student_email   = params.get('lis_person_contact_email_primary', '')
        assignment_name = params.get('resource_link_title', 'Assignment')
        course_id       = params.get('context_id', '')
        assignment_id   = params.get('resource_link_id', '')
        conn = get_db()
        c = conn.cursor()

        # Insert or update student
        c.execute(
            '''INSERT INTO students (canvas_id, name, email)
            VALUES (?, ?, ?)
            ON CONFLICT(canvas_id) DO UPDATE SET
                name  = excluded.name,
                email = excluded.email
        ''', (canvas_user_id, student_name, student_email))
        conn.commit()

        c.execute('SELECT id FROM students WHERE canvas_id=?', (canvas_user_id,))
        student_row = c.fetchone()
        student_db_id = student_row['id']

        # Insert or get assignment
        c.execute(
            '''INSERT OR IGNORE INTO assignments
                (name, canvas_course_id, canvas_assignment_id)
            VALUES (?, ?, ?)
            ''', (assignment_name, course_id, assignment_id))
        conn.commit()

        c.execute('SELECT id FROM assignments WHERE canvas_assignment_id=?', (assignment_id,))
        assignment_row = c.fetchone()
        assignment_db_id = assignment_row['id']
        conn.close()

        # Store student info
        session['student_db_id']    = student_db_id
        session['assignment_db_id'] = assignment_db_id
        session['student_name']     = student_name
        session['student_folder']   = student_name.replace(' ', '_')
        session['assignment_name'] = assignment_name

        print(f"LTI Launch: {student_name} ({student_email}) → {assignment_name}")

        return render_template('homepage.html')

    except Exception as e:
        print(f"LTI launch error: {e}")
        return f"LTI Error: {str(e)}", 500

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

    session['student_name']     = 'Harshini Nujella'
    session['student_folder']   = 'Harshini_Nujella'
    session['assignment_name']  = 'Lab 07'
    session['student_db_id']    = student_id
    session['assignment_db_id'] = assignment_id
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
    c.execute('SELECT id FROM students WHERE canvas_id=?', ('student_001',))
    student_id = c.fetchone()['id']
    c.execute('SELECT id FROM assignments WHERE canvas_assignment_id=?', ('assignment_456',))
    assignment_id = c.fetchone()['id']
    conn.close()

    session['student_name']     = 'Steve Jobs'
    session['student_folder']   = 'Steve_Jobs'
    session['assignment_name']  = 'Lab 07'
    session['student_db_id']    = student_id
    session['assignment_db_id'] = assignment_id
    return render_template('homepage.html')

#------------------------
# DATABASE SETUP
#------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canvas_id TEXT UNIQUE,
            name TEXT,
            email TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            canvas_course_id TEXT,
            canvas_assignment_id TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            assignment_id INTEGER,
            filename TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id)   REFERENCES students(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            assignment_id INTEGER,
            test_name TEXT,
            status TEXT,
            output TEXT,
            score REAL,
            max_score REAL,
            graded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            assignment_id INTEGER,
            feedback_text TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS lti_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consumer_key TEXT,
            shared_secret TEXT,
            canvas_url TEXT
        )
    ''')
    
    # LTI 1.3 state storage
    c.execute('''
        CREATE TABLE IF NOT EXISTS lti_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT UNIQUE,
            nonce TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # LTI 1.3 tool config
    c.execute('''
        CREATE TABLE IF NOT EXISTS lti_tool_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issuer TEXT,
            client_id TEXT,
            auth_login_url TEXT,
            auth_token_url TEXT,
            key_set_url TEXT,
            private_key TEXT,
            public_key TEXT,
            deployment_id TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()

#------------------------
# # HELPERS
#------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

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

#------------------------
# ROUTES
#------------------------
@app.route('/')
def index():
    return render_template('homepage.html')

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

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, use_reloader=False)
    