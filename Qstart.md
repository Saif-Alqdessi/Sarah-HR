cd backend && uvicorn app.main:app --port 8001 --reload

cd backend && python start_worker.py

cd frontend && npm run dev