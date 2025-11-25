#!/bin/bash

# Try to activate venv if it exists
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "Starting PC-1 Server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

