@echo off
setlocal
set "ROOT=%~dp0.."

cd /d "%ROOT%"
docker compose up -d
if errorlevel 1 (
  echo Failed to start Milvus. Check Docker Desktop and docker compose.
  exit /b 1
)

start "Backend - FastAPI" cmd /k "cd /d ""%ROOT%\backend"" && call .venv\Scripts\activate.bat && uvicorn main:app --reload"
start "Frontend - Vite" cmd /k "cd /d ""%ROOT%\frontend"" && npm run dev"

echo Development services are starting.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo Milvus:   localhost:19530
endlocal
