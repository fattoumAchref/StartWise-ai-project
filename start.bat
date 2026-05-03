@echo off
echo ================================================
echo   StartWise - Lancement complet
echo   CFO + Legal + Marketing + Ideation + Audit
echo ================================================

cd /d %~dp0
set ROOT=%~dp0
set SW=%ROOT%StartWise-integration

REM ── Variables d'environnement ─────────────────────────────────────────────
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set A2A_BUS_URL=http://localhost:8765
set INVESTMENT_AGENT_URL=http://localhost:8002
set RISK_AGENT_URL=http://localhost:8003
set CHROMA_PATH=%ROOT%chroma_db

REM ── Copie .env vers backend pour les sous-agents ideation ────────────────
copy /Y .env "%SW%\backend\.env" >nul 2>&1

REM ── Redis (Docker) — obligatoire pour sessions + A2A bus ─────────────────
echo [0/6] Redis port 6379...
where docker >nul 2>&1
if %errorlevel% equ 0 (
    docker start redis 2>nul || docker run -d --name redis -p 6379:6379 redis >nul 2>&1
    timeout /t 2 /nobreak >nul
) else (
    echo [WARN] Docker absent - Redis doit tourner manuellement
)

REM ── Qdrant (Docker) — Product Audit + Legal Agent ────────────────────────
where docker >nul 2>&1
if %errorlevel% equ 0 (
    echo [Docker] Qdrant port 6333...
    docker start qdrant 2>nul || docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant >nul 2>&1
    timeout /t 3 /nobreak >nul
) else (
    echo [SKIP] Qdrant ignore - Docker absent
)

REM ── [1/6] Bus A2A ─────────────────────────────────────────────────────────
echo [1/6] Bus A2A port 8765...
start "A2A Bus" cmd /k "%ROOT%venv\Scripts\activate && uvicorn a2a_bus.bus_server:app --port 8765"
timeout /t 3 /nobreak >nul

REM ── [2/6] Agents Finance + Investment + Risk (A2A servers) ───────────────
REM  Tourner depuis ROOT (%ROOT%) pour que data/ et chroma_db/ se resolvent correctement
echo [2/6] Finance A2A :8001 + Investment A2A :8002 + Risk A2A :8003...
start "Finance A2A" cmd /k "%ROOT%venv\Scripts\activate && uvicorn finagents.finance.a2a_server:app --port 8001 --reload"
timeout /t 2 /nobreak >nul
start "Investment A2A" cmd /k "%ROOT%venv\Scripts\activate && uvicorn finagents.investment.a2a_server:app --port 8002 --reload"
timeout /t 2 /nobreak >nul
start "Risk A2A" cmd /k "cd /d %SW%\backend && %ROOT%venv\Scripts\activate && uvicorn riskAgent.a2a_server:app --port 8003 --reload"
timeout /t 2 /nobreak >nul

REM ── [3/6] Agents Ideation (sous-agents ADK) ──────────────────────────────
echo [3/6] Ideation Agents ports 8101-8103...
start "Ideation Agents" cmd /k "cd /d %SW%\backend && %ROOT%venv\Scripts\activate && start /B python -m ideation.agents.question_agent && start /B python -m ideation.agents.research_agent && python -m ideation.agents.formulator_agent"
timeout /t 4 /nobreak >nul

REM ── [4/6] Django Backend ──────────────────────────────────────────────────
echo [4/6] Django Backend port 8000...
start "Django Backend" cmd /k "cd /d %SW%\backend && %ROOT%venv\Scripts\activate && python manage.py migrate --run-syncdb && daphne -p 8000 --http-timeout 120 startwise.asgi:application"
timeout /t 5 /nobreak >nul

REM ── [5/5] Next.js Frontend ────────────────────────────────────────────────
echo [5/5] Next.js Frontend port 3000...
start "Next.js Frontend" cmd /k "cd /d %SW%\frontend && npm run dev"

echo.
echo Tout est lance !
echo   Frontend         : http://localhost:3000
echo   Backend (Django) : http://localhost:8000
echo   Finance A2A      : http://localhost:8001
echo   Investment A2A   : http://localhost:8002
echo   Risk A2A         : http://localhost:8003
echo   Legal Advisor    : http://localhost:8000/legal/
echo   A2A Bus          : http://localhost:8765
echo   Question Agent   : http://localhost:8101
echo   Research Agent   : http://localhost:8102
echo   Formulator       : http://localhost:8103
echo   Redis            : localhost:6379
echo   Qdrant           : http://localhost:6333
echo.
echo Modules actifs :
echo   [CFO]       /dashboard/viability-assessment
echo   [LexWise]   /dashboard/lexwise
echo   [Marketing] /dashboard
echo   [Ideation]  /onboarding + /dashboard/ideation
echo   [Audit]     /dashboard/product-audit
echo.
echo Ferme cette fenetre pour arreter.
