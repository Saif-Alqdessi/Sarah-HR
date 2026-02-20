#!/bin/bash

echo "Starting Sarah HR Project Services..."
echo ""

# Start backend service
echo "Starting Backend Service..."
cd backend && python -m uvicorn app.main:app --reload --port 8001 &
BACKEND_PID=$!

# Start frontend service
echo "Starting Frontend Service..."
cd ../frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "Services started successfully!"
echo "Backend running at: http://localhost:8001"
echo "Frontend running at: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user to press Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
