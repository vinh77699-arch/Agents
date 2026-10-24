@echo off
title ResearchGen Servers

echo Starting Backend (port 8000)...
start "Backend - FastAPI" cmd /k "cd /d D:\Agent\backend && python start.py"

echo Starting Frontend (port 3000)...
start "Frontend - Next.js" cmd /k "cd /d D:\Agent\frontend && npm run dev"

echo.
echo Both servers are starting...
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo.
echo Close the opened windows to stop the servers.
