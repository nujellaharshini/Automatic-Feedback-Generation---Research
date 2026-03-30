from flask import Flask, request, jsonify, render_template
import os

app = Flask(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'submissions')
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'py', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

    if reupload and original_name:
        old_path = os.path.join(UPLOAD_DIR, original_name)
        if os.path.exists(old_path):
            os.remove(old_path)
            print(f"Deleted old file: {original_name}")

    dest = os.path.join(UPLOAD_DIR, file.filename)
    file.save(dest)
    action = "Replaced" if reupload else "Saved"
    print(f"{action}: {original_name} → {file.filename} in Submissions/")
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)