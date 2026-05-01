@echo off
echo ================================
echo   StartWise - Lancement complet
echo   Django + Next.js + Agents A2A
echo ================================

cd /d %~dp0

REM Variables heritees par tous les processus enfants
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set A2A_BUS_URL=http://localhost:8765
set INVESTMENT_AGENT_URL=http://localhost:8002

REM Copie le .env racine dans backend/ pour les sous-agents ideation
copy /Y .env backend\.env >nul 2>&1

REM Qdrant optionnel - Product Audit uniquement
where docker >nul 2>&1
if %errorlevel% equ 0 (
    echo [Docker] Qdrant port 6333...
    start "Qdrant" cmd /k "docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant"
    timeout /t 5 /nobreak >nul
) else (
    echo [SKIP] Docker absent - Qdrant ignore
)

echo [1/5] Bus A2A port 8765...
start "A2A Bus" cmd /k "venv\Scripts\activate && uvicorn a2a_bus.bus_server:app --port 8765"
timeout /t 3 /nobreak >nul

echo [2/5] Agents Ideation ports 8101-8103...
start "Ideation Agents" cmd /k "venv\Scripts\activate && cd backend && start /B python -m ideation.agents.question_agent && start /B python -m ideation.agents.research_agent && python -m ideation.agents.formulator_agent"
timeout /t 4 /nobreak >nul

echo [3/5] Finance + Investment Agents ports 8001-8002...
start "Finance Agents" cmd /k "venv\Scripts\activate && start /B uvicorn finagents.finance.a2a_server:app --port 8001 --reload && start /B uvicorn finagents.investment.a2a_server:app --port 8002 --reload && python -m a2a_bus.dev.run_mocks --real-investment"
timeout /t 4 /nobreak >nul

echo [4/5] Django Backend port 8000...
start "Django Backend" cmd /k "venv\Scripts\activate && cd backend && python manage.py migrate --run-syncdb && daphne -p 8000 --http-timeout 120 startwise.asgi:application"
timeout /t 4 /nobreak >nul

echo [5/5] Next.js Frontend port 3000...
start "Next.js Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Tout est lance !
echo   Frontend      : http://localhost:3000
echo   Backend       : http://localhost:8000
echo   Finance A2A   : http://localhost:8001
echo   Investment A2A: http://localhost:8002
echo   A2A Bus       : http://localhost:8765
echo   Question Agent: http://localhost:8101
echo   Research Agent: http://localhost:8102
echo   Formulator    : http://localhost:8103
echo   Redis         : localhost:6379
echo.
echo Ferme cette fenetre.
