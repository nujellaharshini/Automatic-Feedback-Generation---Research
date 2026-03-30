from flask import Blueprint, request, session, redirect, render_template, jsonify, url_for
from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch
from pylti1p3.deep_link_resource import DeepLinkResource
import sqlite3
import os
import time
import secrets
from lti_config import (
    get_lti13_tool_conf,
    save_state, verify_and_consume_state, cleanup_old_states,
    LTI1_CONSUMER_KEY, LTI1_SHARED_SECRET,
    LTI13_CLIENT_ID, LTI13_ISSUER
)

lti_bp = Blueprint('lti', __name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'website.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def save_student_to_session(student_name, student_email, canvas_user_id,
                             assignment_name, course_id, assignment_id):
    """Save student info to DB and session — shared by both LTI 1.1 and 1.3"""
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        INSERT INTO students (canvas_id, name, email)
        VALUES (?, ?, ?)
        ON CONFLICT(canvas_id) DO UPDATE SET
            name  = excluded.name,
            email = excluded.email
    ''', (canvas_user_id, student_name, student_email))
    conn.commit()

    c.execute('SELECT id FROM students WHERE canvas_id=?', (canvas_user_id,))
    student_db_id = c.fetchone()['id']

    c.execute('''
        INSERT OR IGNORE INTO assignments (name, canvas_course_id, canvas_assignment_id)
        VALUES (?, ?, ?)
    ''', (assignment_name, course_id, assignment_id))
    conn.commit()

    c.execute('SELECT id FROM assignments WHERE canvas_assignment_id=?', (assignment_id,))
    assignment_row = c.fetchone()
    assignment_db_id = assignment_row['id'] if assignment_row else None
    conn.close()

    session['student_db_id']         = student_db_id
    session['assignment_db_id']      = assignment_db_id
    session['student_name']          = student_name
    session['student_folder']        = student_name.replace(' ', '_')
    session['assignment_name']       = assignment_name
    session['canvas_course_id']      = course_id
    session['canvas_assignment_id']  = assignment_id
    session['canvas_user_id']        = canvas_user_id

    print(f"LTI Launch: {student_name} ({student_email}) → {assignment_name}")

# ─────────────────────────────────────────
# LTI 1.3 Routes
# ─────────────────────────────────────────

@lti_bp.route('/lti13/login', methods=['GET', 'POST'])
def lti13_login():
    """Step 1 of LTI 1.3 OIDC flow — Canvas initiates login"""
    try:
        tool_conf = get_lti13_tool_conf()
        oidc_login = FlaskOIDCLogin(request, tool_conf)
        return oidc_login.enable_check_cookies().redirect(
            url_for('lti.lti13_launch', _external=True)
        )
    except Exception as e:
        return f"LTI 1.3 Login Error: {str(e)}", 500


@lti_bp.route('/lti13/launch', methods=['POST'])
def lti13_launch():
    """Step 2 of LTI 1.3 OIDC flow — Canvas posts the JWT token"""
    try:
        tool_conf = get_lti13_tool_conf()
        message_launch = FlaskMessageLaunch(request, tool_conf)
        launch_data = message_launch.get_launch_data()

        # Extract student info from JWT claims
        student_name   = launch_data.get('name', 'Unknown Student')
        student_email  = launch_data.get('email', '')
        canvas_user_id = launch_data.get('sub', '')

        # Assignment info
        resource_claim  = launch_data.get(
            'https://purl.imsglobal.org/spec/lti/claim/resource_link', {})
        assignment_name = resource_claim.get('title', 'Assignment')
        assignment_id   = resource_claim.get('id', '')

        # Course info
        context_claim = launch_data.get(
            'https://purl.imsglobal.org/spec/lti/claim/context', {})
        course_id = context_claim.get('id', '')

        # LTI Advantage — Names and Roles
        nrps_claim = launch_data.get(
            'https://purl.imsglobal.org/spec/lti-nrp/claim/namesroleservice', {})
        session['nrps_endpoint'] = nrps_claim.get('context_memberships_url', '')

        # LTI Advantage — Assignment and Grade Services
        ags_claim = launch_data.get(
            'https://purl.imsglobal.org/spec/lti-ags/claim/endpoint', {})
        session['ags_lineitems_url'] = ags_claim.get('lineitems', '')
        session['ags_lineitem_url']  = ags_claim.get('lineitem', '')
        session['ags_scope']         = ags_claim.get('scope', [])

        session['lti_version'] = '1.3'

        save_student_to_session(
            student_name, student_email, canvas_user_id,
            assignment_name, course_id, assignment_id
        )

        return render_template('homepage.html')

    except Exception as e:
        print(f"LTI 1.3 launch error: {e}")
        # Fall back to LTI 1.1 if 1.3 fails
        return redirect(url_for('lti.lti11_launch'))


@lti_bp.route('/lti13/jwks', methods=['GET'])
def lti13_jwks():
    """Serves your public key as JWKS — Canvas needs this to verify your tool"""
    try:
        tool_conf = get_lti13_tool_conf()
        return jsonify(tool_conf.get_jwks())
    except Exception as e:
        return jsonify({'error': str(e)}), 500
      


# ─────────────────────────────────────────
# LTI 1.1 Routes (fallback)
# ─────────────────────────────────────────

@lti_bp.route('/lti-launch', methods=['POST'])
def lti11_launch():
    """LTI 1.1 launch — fallback if 1.3 not configured"""
    try:
        params = dict(request.form)
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}

        consumer_key    = params.get('oauth_consumer_key', '')
        oauth_timestamp = int(params.get('oauth_timestamp', 0))

        if consumer_key != LTI1_CONSUMER_KEY:
            return "Unauthorized: invalid consumer key", 403

        if abs(time.time() - oauth_timestamp) > 300:
            return "Unauthorized: timestamp expired", 403

        canvas_user_id  = params.get('user_id', '')
        student_name    = params.get('lis_person_name_full', 'Unknown Student')
        student_email   = params.get('lis_person_contact_email_primary', '')
        assignment_name = params.get('resource_link_title', 'Assignment')
        course_id       = params.get('custom_canvas_course_id',
                          params.get('context_id', ''))
        assignment_id   = params.get('custom_canvas_assignment_id',
                          params.get('resource_link_id', ''))

        session['lti_version'] = '1.1'

        save_student_to_session(
            student_name, student_email, canvas_user_id,
            assignment_name, course_id, assignment_id
        )

        return render_template('homepage.html')

    except Exception as e:
        print(f"LTI 1.1 launch error: {e}")
        return f"LTI Error: {str(e)}", 500