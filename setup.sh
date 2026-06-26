#!/usr/bin/env bash
# Copies your profile into the spots the skill + app read from.
set -e
cp profile/config.json skill/config.json
mkdir -p app/data
cp profile/config.json app/data/config.json
cp profile/base_cv.md  app/data/base_cv.md
echo "Setup done."
echo "1) Discover:  python skill/scripts/poll_jobs.py"
echo "2) Dashboard: cd app && pip install -r requirements.txt && uvicorn app:app --reload  ->  http://localhost:8000"
