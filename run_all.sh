#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_AG="$SCRIPT_DIR/local_autograder"
STUDENT_FOLDER="${1:-}" 

set -e  # Stop on any error

# #------------------------
# HELPER
# #------------------------
check_error() {
  local step="$1"
  local exit_code="$2"
  if [ $exit_code -ne 0 ]; then
    echo "Failed at step: $step"
    exit 1
  fi
}
#------------------------
# STEP 0: Clear old data before running
#------------------------
echo "Step 0: Clearing old data..."

# Clear results folder contents
if [ -d "$LOCAL_AG/results" ]; then
  # rm -rf "$LOCAL_AG/results/*"
  rm -rf "$LOCAL_AG"/results/*
  echo "Cleared results/ folder"
else
  echo "results/ folder not found, skipping"
fi

# Delete results_all.json
if [ -f "$LOCAL_AG/results_all.json" ]; then
  rm "$LOCAL_AG/results_all.json"
  echo "Deleted results_all.json"
else
  echo "results_all.json not found, skipping"
fi

# Clear feedback.json contents
if [ -f "$SCRIPT_DIR/feedback.json" ]; then
  echo "[]" > "$SCRIPT_DIR/feedback.json"
  echo "Cleared feedback.json"
else
  echo "eedback.json not found, skipping"
fi

# Delete tpch.sqlite
if [ -f "$LOCAL_AG/tpch.sqlite" ]; then
  rm "$LOCAL_AG/tpch.sqlite"
  echo "Deleted tpch.sqlite"
else
  echo "pch.sqlite not found, skipping"
fi

echo "Step 0 passed."
echo "#------------------------"

echo "Starting autograder pipeline..."
echo "#------------------------"

# #------------------------
# STEP 1: Navigate into local_autograder
# #------------------------
# cd "$SCRIPT_DIR/local_autograder"
cd "$LOCAL_AG"
check_error "Navigate to local_autograder" $?

# #------------------------
# STEP 2: Detect chip and build Docker image
# #------------------------
echo "Detecting chip architecture..."
ARCH=$(uname -m)

if [ "$ARCH" = "arm64" ]; then
  echo "Apple Silicon detected — using --platform=linux/amd64"
  docker build --platform=linux/amd64 -t my-autograder .
else
  echo "Intel chip detected"
  docker build -t my-autograder .
fi
check_error "Docker build" $?

# #------------------------
# STEP 3: Verify Docker image exists
# #------------------------
echo "Verifying Docker image..."
docker images | grep my-autograder
check_error "Verify Docker image" $?

# #------------------------
# STEP 4: Make grade_all.sh executable and run it
# #------------------------
echo "Running grade_all.sh..."
chmod +x grade_all.sh
check_error "chmod grade_all.sh" $?

./grade_all.sh "$STUDENT_FOLDER"
check_error "Run grade_all.sh" $?

# #------------------------
# STEP 5: Run aggregate_results.py
# #------------------------
echo "Running aggregate_results.py..."
python3 tools/aggregate_results.py
check_error "aggregate_results.py" $?

# #------------------------
# STEP 6: Run json_to_sqlite.py
# #------------------------
echo "Running json_to_sqlite.py..."
python3 json_to_sqlite.py
check_error "json_to_sqlite.py" $?

# #------------------------
# STEP 9: Run generate_feedback.py
# #------------------------
cd "$SCRIPT_DIR"
echo "Running generate_feedback_1.py..."

python3 generate_feedback_1.py
check_error "generate_feedback_1.py" $?

# #------------------------
# STEP 10: Run canvas_connection.py
# #------------------------
# echo "Running canvas_connection.py..."
# python3 canvas_connection.py
# check_error "canvas_connection.py" $?

# #------------------------
echo "#------------------------"
echo "All steps completed successfully!"