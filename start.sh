#!/bin/bash
# Start Evolution UI server

cd "$(dirname "$0")"

# Create venv if not exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
    uv pip install -r requirements.txt
fi

# Run server
PORT=${PORT:-8080}
echo "🧬 Starting Evolution UI on http://0.0.0.0:$PORT"
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port $PORT
