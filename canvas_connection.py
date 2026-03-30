import os, sys, time, json, requests
from pathlib import Path
from typing import List, Optional, Dict
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("CANVAS_BASE_URL", "https://catcourses.ucmerced.edu").rstrip("/")
COURSE_ID = os.getenv("COURSE_ID")
ASSIGNMENT_ID = os.getenv("ASSIGNMENT_ID")
CANVAS_TOKEN = os.getenv("CANVAS_API_KEY")
FEEDBACK_JSON = Path("feedback.json")
RATE_LIMIT_SLEEP = float(os.getenv("RATE_LIMIT_SLEEP", "0.35"))
DRY_RUN = os.environ.get('DRY_RUN', '1') == '1'
ASSIGNMENT_NAME = os.getenv("ASSIGNMENT_NAME")
CANVAS_BASE_URL = os.environ.get('CANVAS_BASE_URL', 'https://catcourses.ucmerced.edu').rstrip('/')
load_dotenv()
'''
# Initializing the session for making requests
S = requests.Session()
S.headers.update({"Authorization": f"Bearer {CANVAS_TOKEN}"})

# Handles API calls to Canvas and checks for errors
def canvas_request(method: str, path: str, params: Optional[Dict]=None, data: Optional[Dict]=None):
    url = f"{BASE_URL}{path}"
    r = S.request(method, url, params=params, data=data, timeout=30)
        
    if r.status_code >= 400:
        raise requests.HTTPError(f"API Error {r.status_code} for {path}: {r.text[:100]}", response=r)
    return r

def lookup_user(course_id: str, full_name: str) -> Optional[int]:
    path = f"/api/v1/courses/{course_id}/users"
    params = {"search_term": full_name, "per_page": 10}
    
    r = canvas_request("GET", path, params=params)
    users = r.json() or []

    # Filter for an exact match on the student's name.
    exacts = []
    for i in users:
        if i.get("name") == full_name:
            exacts.append(i)
    
    if len(exacts) == 1:
        print(f"Found unique match for '{full_name}'. User ID: {exacts[0].get('id')}", file=sys.stderr)
        return exacts[0].get("id")
    return None

def post_submission_comment(course_id: str, assignment_id: str, user_id: int, comment_text: str, dry_run: bool=True):    
    path = f"/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}"
    
    # dry run mode: do not actually post the comment
    if dry_run:
        return {"dry_run": True, "comment_length": len(comment_text)}
    
    data = {"comment[text_comment]": comment_text}
    r = canvas_request("PUT", path, data=data)
        
    return r.json()

def send_canvas_message(recipient_id: int, assignment_name: str):
    path = "/api/v1/conversations"
    subject = f"New Comment on {assignment_name}"
    body = f"""\
    Dear student,
    If you are receiving this message, it is because there is a new comment for your assignment:
    **{assignment_name}**

    Please log in to CatCourses to review the feedback. 
"""
    data = {
        "recipients[]": [recipient_id],
        "subject": subject,
        "body": body,
        "context_code": f"course_{COURSE_ID}"
    }
    
    try:
        r = canvas_request("POST", path, data=data)
        print(f"Notification sent to user {recipient_id}")
        return r.json()
    except Exception as e:
        print(f"Failed to send message to {recipient_id}: {e}", file=sys.stderr)
        return None

def main():
    rows: List[dict] = json.loads(FEEDBACK_JSON.read_text(encoding="utf-8"))
    sent = 0
    
    for i, row in enumerate(rows):
        student_name = (row.get("full_name") or "").strip()
        feedback = (row.get("feedback") or "").strip()
        
        # Skip rows that don't have enough data
        if not student_name or not feedback:
            continue
        
        try:
            # Step 1: Find the student's Canvas ID using their Full Name
            user_id = lookup_user(COURSE_ID, student_name)
            if user_id is None:
                continue
                
            # Step 2: Post the comment
            post_submission_comment(COURSE_ID, ASSIGNMENT_ID, user_id, feedback, dry_run=DRY_RUN)
            sent += 1
            time.sleep(RATE_LIMIT_SLEEP) 
            
            if not DRY_RUN:
                send_canvas_message(user_id, ASSIGNMENT_NAME)
                # Pause to respect Canvas rate limits
                time.sleep(RATE_LIMIT_SLEEP) 

        except Exception as e:
            # Any network or API errors
            print(f"Error for {student_name}")

    print(f"\n--- Process Complete ---")
    print(f"Total Sent: {sent}")
    print(f"DRY RUN was: {DRY_RUN}")
    
if __name__ == "__main__":
    main()
'''

def get_headers():
    return {'Authorization': f'Bearer {CANVAS_TOKEN}'}

def get_canvas_user_id_by_name(course_id, student_name):
    """Look up Canvas user ID by student name"""
    path = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/users"
    params = {
        'per_page':    100,
        'search_term': student_name
    }
    r = requests.get(path, headers=get_headers(), params=params, timeout=30)
    if r.status_code >= 400:
        raise Exception(f"Could not fetch course users: {r.status_code}")

    users = r.json()
    print(f"DEBUG searching for '{student_name}' — found {len(users)} users")

    for user in users:
        if user.get('name', '').strip().lower() == student_name.strip().lower():
            print(f"DEBUG matched: {user.get('name')} → id={user.get('id')}")
            return user['id']

    if len(users) == 1:
        print(f"DEBUG single result: {users[0].get('name')} → id={users[0].get('id')}")
        return users[0]['id']

    return None

def submit_file_to_canvas(course_id, assignment_id, lti_user_id, file_path, filename, student_name=None):
    """Submit a file as a Canvas assignment submission on behalf of a student"""
    if DRY_RUN:
        print(f"[DRY RUN] Would submit {filename} for {student_name}")
        return {'dry_run': True}

    canvas_user_id = get_canvas_user_id_by_name(course_id, student_name) if student_name else None
    if not canvas_user_id:
        raise Exception(f"Could not find Canvas user ID for student '{student_name}'")
    print(f"Resolved Canvas user ID: {canvas_user_id}")

    # Step 1 — Notify Canvas we want to upload a file
    upload_url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{canvas_user_id}/files"
    file_size  = os.path.getsize(file_path)

    notify_data = {
        'name':         filename,
        'size':         file_size,
        'content_type': 'text/x-python' if filename.endswith('.py') else 'application/pdf',
        'on_duplicate': 'overwrite'
    }

    r = requests.post(upload_url, headers=get_headers(), data=notify_data, timeout=30)
    if r.status_code >= 400:
        raise Exception(f"Canvas upload notify error: {r.status_code} — {r.text[:200]}")

    upload_info = r.json()

    # Step 2 — Upload the actual file
    upload_endpoint = upload_info['upload_url']
    upload_params   = upload_info['upload_params']

    with open(file_path, 'rb') as f:
        files = {'file': (filename, f)}
        r2 = requests.post(upload_endpoint, data=upload_params, files=files, timeout=60)

    if r2.status_code not in [200, 201, 301, 302]:
        raise Exception(f"Canvas file upload error: {r2.status_code}")

    # Step 3 — Get file ID
    if r2.status_code in [301, 302]:
        r3 = requests.get(r2.headers['Location'], headers=get_headers(), timeout=30)
        file_id = r3.json().get('id')
    else:
        file_id = r2.json().get('id')

    if not file_id:
        raise Exception("Could not get file ID from Canvas upload response")

    # Step 4 — Submit
    submit_url  = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
    submit_data = {
        'submission[submission_type]': 'online_upload',
        'submission[file_ids][]':      file_id,
        'submission[user_id]':         canvas_user_id
    }

    r4 = requests.post(submit_url, headers=get_headers(), data=submit_data, timeout=30)
    if r4.status_code >= 400:
        raise Exception(f"Canvas submission error: {r4.status_code} — {r4.text[:200]}")

    print(f"Submitted {filename} for user {canvas_user_id} to assignment {assignment_id}")
    return r4.json()

def post_feedback_comment(course_id, assignment_id, user_id, feedback_text):
    """Post feedback as a submission comment"""
    if DRY_RUN:
        print(f"[DRY RUN] Would post comment to user {user_id}: {feedback_text[:100]}")
        return {'dry_run': True}

    path = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}"
    data = {'comment[text_comment]': feedback_text}
    r = requests.put(path, headers=get_headers(), data=data, timeout=30)

    if r.status_code >= 400:
        raise Exception(f"Canvas comment error: {r.status_code} — {r.text[:100]}")

    return r.json()