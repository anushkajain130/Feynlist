#!/usr/bin/env bash
# Baseline API smoke check against a locally running backend (no Gemini key set).
# Usage: bash evals/evidence/baseline_api_smoke.sh [base_url]
B=${1:-http://127.0.0.1:8000}
run() { echo "### $*"; curl -s -w '\nHTTP %{http_code}\n' "$@"; echo; }
run "$B/health"
run "$B/api/tasks/today"
run "$B/api/analytics/today"
run -X POST "$B/api/tasks/schedule" -H 'Content-Type: application/json' \
  -d '{"tasks":[{"name":"Revise chapter 3","start_time":"00:00","end_time":"00:30","task_class":"Academics_Selfstudy"},{"name":"Sleep","start_time":"22:00","end_time":"06:00","task_class":"Sleep"}]}'
TID=$(curl -s "$B/api/tasks/today" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["tasks"][0]["id"])')
run -X POST "$B/api/tasks/toggle-subtask" -H 'Content-Type: application/json' \
  -d "{\"task_id\":\"$TID\",\"subtask_name\":\"Start_and_Sit_for_5_mins\",\"value\":true}"
run "$B/api/analytics/today"
run "$B/api/analytics/history?days=14"
run "$B/api/analytics/burnout"
run "$B/api/agents/status"
run -X POST "$B/api/agents/message" -H 'Content-Type: application/json' -d '{"message":"hi","agent_id":"freya"}'
run "$B/api/agents/tokens/today"
