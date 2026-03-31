# AI-Powered Autograder Feedback System

> Transforming raw autograder errors into clear pedagogically-driven feedback — delivered directly to students through Canvas.

---

## Overview

Introductory programming students often receive unhelpful autograder messages like *"Test Failed"* — complex stack traces that are hard to interpret and act on. This system bridges that gap by using **Large Language Models (LLMs)** to convert autograder output into clear, beginner-friendly feedback delivered automatically through **Canvas LMS**.

Students access the tool directly through Canvas via an **LTI-integrated web app**, where they can upload their code, run the autograder, see their results in real time, and submit — all without ever leaving their course workflow. 
---

## Key Features

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

The SQLite database (`tpch.sqlite`) tracks the full student results:
```
results_filtered - name, unit test name, status (failed/passed), output
submissions - name, status
```
---

## Full System Architecture


---

## AI / LLM Pipeline

### 1. Data Ingestion
- Submissions are graded inside a **Dockerized local replica** of the Gradescope environment
- A Bash script mounts each student's folder and runs the autograder
- Output is collected as structured **JSON files per student**

### 2. ETL & Preprocessing
- A Python ETL script strips metadata and loads only **failed test cases + error messages** into SQLite

### 3. Rule-Augmented Context Injection
- A **regex-based NLP layer** classifies each error into predefined categories (e.g. `OUTPUT_MISMATCH`, `TYPE_NONE`, `MATH_OPS_INCORRECT`)
- If an error category has recurred across prior submissions, this history is injected into the prompt
- Enables **personalized, longitudinal feedback** that acknowledges individual student patterns

### 4. LLM Feedback Generation
- The prompt is sent to **OpenAI GPT** via API
- The model guides students toward the correct answer **without revealing the solution**

### 5. Canvas Delivery
- Feedback is posted to Canvas via the **REST API** as a submission comment in SpeedGrader
- Rubric is updated with student scores

---

## Tech Stack

| Category | Tools |
|---|---|
| Language | Python 3.13 |
| Web Framework | Flask |
| LTI Integration | pylti1p3 (LTI 1.3 + 1.1 fallback) |
| Containerization | Docker |
| Database | SQLite |
| AI / LLM | OpenAI API (GPT) |
| LMS Integration | Canvas REST API |

---

### Prerequisites
- Python 3.13+
- Docker
- OpenAI API key
- Canvas API token
- Canvas LTI external tool credentials
- to download requirements: pip install -r requirements.txt

## Project Structure
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

## Future Work
Still work in-progress, will be deploying in a Intro Python course.

---
