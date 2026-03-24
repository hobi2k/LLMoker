#!/bin/sh

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

echo "[1/3] Ren'Py compile"
(cd "$ROOT" && ./5Drawminigame.sh . compile)

echo "[2/3] Ren'Py lint"
(cd "$ROOT" && ./5Drawminigame.sh . lint)

echo "[3/3] Python compile"
python3 -m py_compile \
    "$ROOT/backend/poker_engine.py" \
    "$ROOT/backend/policy_loop.py" \
    "$ROOT/backend/llm/agent.py" \
    "$ROOT/backend/llm/client.py" \
    "$ROOT/backend/llm/prompts.py" \
    "$ROOT/backend/llm/runtime.py" \
    "$ROOT/backend/llm/tasks.py"

echo
echo "Non-GUI validation completed."
