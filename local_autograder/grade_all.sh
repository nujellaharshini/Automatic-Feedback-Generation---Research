#!/usr/bin/env bash
set -euo pipefail

IMAGE="my-autograder"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$SCRIPT_DIR/results"

# Accept student folder name as argument
STUDENT_FOLDER="${1:-}"
if [ -z "$STUDENT_FOLDER" ]; then
  echo "❌ No student folder provided"
  exit 1
fi

ROOT="$SCRIPT_DIR/../website/Submissions/$STUDENT_FOLDER"

if [ ! -d "$ROOT" ]; then
  echo "❌ Student folder not found: $ROOT"
  exit 1
fi

mkdir -p "$OUT/$STUDENT_FOLDER"

echo "==> Grading $STUDENT_FOLDER"
docker run --rm \
  --platform=linux/amd64 \
  --mount type=bind,source="$ROOT",target=/autograder/submission,readonly \
  --mount type=bind,source="$OUT/$STUDENT_FOLDER",target=/autograder/results \
  "$IMAGE" /autograder/run_autograder || echo "   (failed for $STUDENT_FOLDER)"