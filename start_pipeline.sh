#!/bin/bash
echo "Stopping any existing pipeline processes..."
lsof -ti :8000 | xargs kill -9 2>/dev/null
pkill -f "ngrok http"
pkill -f "caffeinate"

echo "Preventing Mac from sleeping (caffeinate)..."
caffeinate -d &
CAFFEINATE_PID=$!

echo "Starting Backend API..."
PYTHONUNBUFFERED=1 venv312/bin/python -m uvicorn backend.main:app --port 8000 &
BACKEND_PID=$!

echo "Waiting for backend to spin up..."
sleep 3

echo "Starting Ngrok Tunnel on cross-thing-sinless.ngrok-free.dev..."
ngrok http --domain=cross-thing-sinless.ngrok-free.dev 8000 &
NGROK_PID=$!

echo ""
echo "✅ Pipeline is running! Your AI is now online and immortal."
echo "Press Ctrl+C to stop the pipeline and allow your Mac to sleep."

# Wait for user to press Ctrl+C, then kill child processes
trap "echo 'Stopping pipeline...'; kill -9 $CAFFEINATE_PID $BACKEND_PID $NGROK_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
