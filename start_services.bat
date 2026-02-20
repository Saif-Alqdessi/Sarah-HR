@echo off
echo Starting Sarah HR Project Services...
echo.

echo Starting Backend Service...
start cmd /k "cd backend && python -m uvicorn app.main:app --reload --port 8001"

echo Starting Frontend Service...
start cmd /k "cd frontend && npm run dev"

echo.
echo Services started successfully!
echo Backend running at: http://localhost:8001
echo Frontend running at: http://localhost:3000
echo.
echo Press any key to close this window (services will continue running)
pause > nul
