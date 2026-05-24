#!/bin/bash

# Start uvicorn (API server) in background
python -m uvicorn src.api_server:app --host 0.0.0.0 --port 8010 &
UVICORN_PID=$!

# Start vite (frontend dev server) in background
cd /app/frontend
npm run dev -- --host &
VITE_PID=$!

# Wait for either process to exit
wait $UVICORN_PID $VITE_PID
