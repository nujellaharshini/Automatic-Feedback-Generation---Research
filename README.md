# AI-Powered Autograder Feedback System

> Transforming raw autograder errors into clear pedagogically-driven feedback — delivered directly to students through Canvas.

---

## Overview

Introductory programming students often receive unhelpful autograder messages like *"Test Failed"* — complex stack traces that are hard to interpret and act on. This system bridges that gap by using **Large Language Models (LLMs)** to convert autograder output into clear, beginner-friendly feedback delivered automatically through **Canvas LMS**.

Students access the tool directly through Canvas via an **LTI-integrated web app**, where they can upload their code, run the autograder, see their results in real time, and submit — all without ever leaving their course workflow. 
---

## ✨ Key Features

- **LTI-integrated web app** — students launch directly from Canvas, no separate login needed
- **End-to-end automated pipeline** — upload → grade → AI feedback → submit to Canvas, all in one flow
- **Dockerized grading environment** — mirrors Gradescope locally for reproducibility
- **ETL data pipeline** — reduces dataset size by over 80% by filtering only failed test cases
- **LLM-generated feedback** — using OpenAI GPT with optimized prompt engineering (tested 3 prompts, and evaluated them using a rubric measuring accuracy, clarity, and pedagogical value)
- **Rule-Augmented NLP** — tracks recurring student errors across submissions for personalized feedback
- **SQLite database** — stores students, assignments, submissions, results, and feedback
- **Secure credential management** — all API tokens stored as environment variables
- **Dry-run mode** — test feedback as instructor-only drafts before publishing to students

---

## Web Application (LTI Tool)

The web app is a **Flask-based LTI tool** that embeds directly into Canvas as an external tool. When a student clicks the assignment link in Canvas, they are authenticated automatically via LTI and land on the submission portal.

### Student Flow
```
Canvas Assignment Page
        ↓  (LTI Launch — student auto-authenticated)
Web App Homepage
        ↓  (Upload .py file)
Run Autograder (Docker)
        ↓  (Live test results shown)
AI Feedback Generated (OpenAI GPT)
        ↓  (Feedback shown inline)
Submit to Canvas (REST API)
        ↓
Grade + Feedback posted to Canvas SpeedGrader
```

### LTI Integration Details

The app supports both **LTI 1.3** (primary) and **LTI 1.1** (fallback):

- **LTI 1.3** uses the OIDC login flow with RSA public/private key signing
- **LTI 1.1** uses OAuth consumer key + shared secret as a fallback
- On launch, Canvas passes the student's name, email, Canvas user ID, course ID, and assignment ID — all stored in the Flask session and SQLite database

### API Endpoints

| Method | Route | Description |
|---|---|---|
| `GET/POST` | `/lti13/login` | LTI 1.3 OIDC login initiation |
| `POST` | `/lti13/launch` | LTI 1.3 JWT token launch |
| `GET` | `/lti13/jwks` | Serves public JWKS for Canvas verification |
| `POST` | `/lti-launch` | LTI 1.1 fallback launch |
| `POST` | `/upload` | Student file upload (.py or .pdf) |
| `POST` | `/grade` | Runs Docker autograder, returns test results + AI feedback |
| `POST` | `/submit` | Submits file + feedback comment to Canvas via REST API |

### Database Schema

The SQLite database (`website.db`) tracks the full student lifecycle:
```
students       — canvas_id, name, email
assignments    — name, canvas_course_id, canvas_assignment_id
submissions    — student_id, assignment_id, filename, submitted_at
results        — student_id, assignment_id, test_name, status, score, output
feedback       — student_id, assignment_id, feedback_text, generated_at
lti_state      — state, nonce, created_at (for LTI 1.3 OIDC flow)
```

---

## 🏗️ Full System Architecture


---

## 🤖 AI / LLM Pipeline (Deep Dive)

### 1. 🐳 Data Ingestion
- Submissions are graded inside a **Dockerized local replica** of the Gradescope environment
- A Bash script mounts each student's folder and runs the autograder
- Output is collected as structured **JSON files per student**

### 2. 🧹 ETL & Preprocessing
- A Python ETL script strips metadata and loads only **failed test cases + error messages** into SQLite
- Reduces dataset size by **over 80%**, improving LLM query speed and reducing token usage

### 3. 🧠 Rule-Augmented Context Injection
- A **regex-based NLP layer** classifies each error into predefined categories (e.g. `OUTPUT_MISMATCH`, `TYPE_NONE`, `MATH_OPS_INCORRECT`)
- If an error category has recurred across prior submissions, this history is injected into the prompt
- Enables **personalized, longitudinal feedback** that acknowledges individual student patterns

### 4. 💬 LLM Feedback Generation
- The enriched prompt is sent to **OpenAI GPT** via API
- Three prompt strategies were tested — **Few-Shot + Role-Based + Instructional** achieved the best mean score of **3.97/5**
- The model guides students toward the correct answer **without revealing the solution**

### 5. 📬 Canvas Delivery
- Feedback is posted to Canvas via the **REST API** as a submission comment in SpeedGrader
- The student's file is also submitted to Canvas programmatically via `submit_file_to_canvas()`
- A **dry-run mode** lets instructors review AI output before publishing

---

## 🧰 Tech Stack

| Category | Tools |
|---|---|
| Language | Python 3.13 |
| Web Framework | Flask |
| LTI Integration | pylti1p3 (LTI 1.3 + 1.1 fallback) |
| Containerization | Docker |
| Database | SQLite |
| AI / LLM | OpenAI API (GPT) |
| LMS Integration | Canvas REST API |
| Autograder | Gradescope |
| Scripting | Bash |
| Config | YAML, `.env` |

---

## 🔬 Prompt Engineering Experiments

Three prompt strategies evaluated on 49 student submissions, rated on a 5-point rubric:

| Prompt Strategy | Clarity | Correctness | Actionability | Mean Score |
|---|---|---|---|---|
| Zero-Shot + Role-Based | 4.2 | 3.73 | 2.8 | 3.43 |
| **Few-Shot + Role-Based + Instructional** | **4.67** | **4.67** | **3.73** | **3.97** ✅ |
| Meta Prompt + Contextual + Few-Shot | 4.07 | 4.47 | 3.67 | 3.80 |

---

## 🧠 Rule-Augmented NLP

| Error Code | Category | Example |
|---|---|---|
| `OUTPUT_MISMATCH` | Output format | Did not find expected output |
| `TYPE_NONE` | None handling | Unsupported operand for NoneType |
| `MATH_OPS_INCORRECT` | Math syntax | Used `^` instead of `**` |
| `LOOP_NEVER_UPDATES` | Loops | Infinite loop detected |
| `FUNC_MISSING_RETURN` | Return values | Returned None |

When a student repeats the same error type across submissions:
> *"compute_power misuses resistance and returns wrong value. **We've noticed this has recurred** — please review equation to code concepts before resubmitting."*

---

## 📊 Results

### Pilot Study — EE 021, Fall 2025

- 📬 **9 out of 34 students** received feedback (others had perfect scores)
- ✅ **5 out of 9 (55%)** resubmitted and achieved full marks after receiving feedback
- 📈 Majority rated feedback **4–5/5 for clarity and helpfulness**

> ```
> ![Clarity vs Helpfulness](images/clarity_helpfulness.png)  ← Figure 8
> ```

### Student Quotes
> *"It's a nice addition to what we have on Gradescope already."*

> *"Love the AI feedback — lets me know where to improve!"*

> *"I enjoy the idea behind autograder comments that can help students verify what's wrong."*

---

## ⚙️ How to Run

### Prerequisites
- Python 3.13+
- Docker
- OpenAI API key
- Canvas API token
- Canvas LTI external tool credentials

### Setup
```bash
git clone https://github.com/nujellaharshini/Automatic-Feedback-Generation---Research.git
cd Automatic-Feedback-Generation---Research

pip install -r requirements.txt

cp .env.example .env
# Fill in: OPENAI_API_KEY, CANVAS_API_TOKEN, BASE_URL, COURSE_ID, ASSIGNMENT_ID,
#          LTI13_CLIENT_ID, LTI13_ISSUER, LTI13_AUTH_LOGIN_URL, LTI13_DEPLOYMENT_ID,
#          SECRET_KEY
```

### Generate LTI Keys
```bash
openssl genrsa -out website/private.key 2048
openssl rsa -in website/private.key -pubout -out website/public.key
```

### Run the Web App
```bash
cd website
python server.py
# App runs at http://localhost:5000
```

### Run the Pipeline Manually
```bash
# Grade all submissions
./local_autograder/grade_all.sh

# Generate AI feedback
python generate_feedback.py

# Post feedback to Canvas (dry-run)
DRY_RUN=1 python canvas_connection.py

# Publish to students
DRY_RUN=0 python canvas_connection.py
```

---

## 📁 Project Structure
```
├── website/
│   ├── server.py             # Flask app + all API routes
│   ├── lti_routes.py         # LTI 1.3 and 1.1 launch routes
│   ├── lti_config.py         # LTI config, key loading, OIDC state mgmt
│   ├── website.db            # SQLite database
│   ├── private.key           # RSA private key (LTI 1.3 signing)
│   ├── public.key            # RSA public key (served as JWKS)
│   ├── templates/            # HTML templates (homepage, etc.)
│   └── static/               # CSS, logo
├── local_autograder/
│   ├── Dockerfile
│   ├── grade_all.sh          # Batch grading script
│   ├── json_to_sqlite.py     # ETL pipeline
│   └── autograder/           # Test files
├── generate_feedback.py      # LLM feedback generation
├── canvas_connection.py      # Canvas REST API integration
├── error_bank.json           # Rule-augmented NLP error categories
├── run_all.sh                # Master pipeline script
└── README.md
```

---

## 🔭 Future Work

- [ ] Real-time feedback triggered automatically on each submission
- [ ] Email/notification alerts when feedback is posted
- [ ] Expand error bank with more categories
- [ ] Reduce LLM hallucinations when student code is included as context
- [ ] Deploy across multiple courses and institutions

---

## 📄 Publication

Submitted to the **ASEE (American Society for Engineering Education) Annual Conference**.

> *"Beyond Pass or Fail: Integrating AI-based Directed Feedback in Canvas to Augment Static Autograder Unit Tests"*

---

## 👩‍💻 Author

**Harshini Nujella**
University of California, Merced
[GitHub](https://github.com/nujellaharshini)
