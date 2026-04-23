@echo off
echo ================================
echo   StartWise — Lancement complet
echo   Django + Next.js + Agents A2A
echo ================================

cd /d %~dp0

echo [1/6] Bus A2A (port 8765)...
start "A2A Bus" cmd /k "venv\Scripts\activate && uvicorn a2a_bus.bus_server:app --port 8765"
timeout /t 3 /nobreak >nul

echo [2/6] Investment Agent A2A Server (port 8002)...
start "Investment A2A" cmd /k "venv\Scripts\activate && set PYTHONIOENCODING=utf-8 && set A2A_BUS_URL=http://localhost:8765 && uvicorn agents.investment.a2a_server:app --port 8002 --reload"
timeout /t 3 /nobreak >nul

echo [3/6] Investment Agent (Redis bus listener)...
start "Investment Agent" cmd /k "venv\Scripts\activate && set PYTHONIOENCODING=utf-8 && set A2A_BUS_URL=http://localhost:8765 && python -m a2a_bus.run_mocks --real-investment"
timeout /t 2 /nobreak >nul

echo [4/6] Finance Agent A2A Server (port 8001)...
start "Finance A2A" cmd /k "venv\Scripts\activate && set A2A_BUS_URL=http://localhost:8765 && uvicorn agents.finance.a2a_server:app --port 8001 --reload"
timeout /t 2 /nobreak >nul

echo [5/6] Django Backend (port 8000)...
start "Django Backend" cmd /k "venv\Scripts\activate && set A2A_BUS_URL=http://localhost:8765 && set INVESTMENT_AGENT_URL=http://localhost:8002 && cd backend && python manage.py migrate --run-syncdb && daphne -p 8000 --http-timeout 120 startwise.asgi:application"
timeout /t 4 /nobreak >nul

echo [6/6] Next.js Frontend (port 3000)...
start "Next.js Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Tout est lance !
echo   Frontend  : http://localhost:3000
echo   Backend   : http://localhost:8000
echo   Finance A2A  : http://localhost:8001
echo   Investment A2A : http://localhost:8002
echo   A2A Bus   : http://localhost:8765
echo.
echo Ferme cette fenetre.
