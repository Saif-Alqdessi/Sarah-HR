@echo off
title HR Project Mega Launcher

:: 1. تشغيل ngrok في نافذة منفصلة
start cmd /k "title NGROK && ngrok http 8001"

:: 2. تشغيل الـ Backend
start cmd /k "title BACKEND && cd backend && uvicorn app.main:app --reload --port 8001"

:: 3. تشغيل الـ Frontend
start cmd /k "title FRONTEND && cd frontend && npm run dev"

:: انتظر 5 ثواني لضمان تشغيل السيرفرات قبل التحديث
timeout /t 5

:: 4. تحديث إعدادات سارة في Vapi
start cmd /k "title VAPI_UPDATE && cd backend && python dev_starter.py"

echo 🚀 تم إطلاق جميع المحركات! تأكد من تحديث رابط ngrok في ملف .env إذا تغير.
pause