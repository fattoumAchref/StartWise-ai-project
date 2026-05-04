@echo off
setlocal EnableExtensions
echo ================================================
echo   StartWise - Lancement complet
echo   CFO + Legal + Marketing + Ideation + Audit
echo ================================================

pushd "%~dp0"
set "ROOT=%cd%"
popd
set "SW=%ROOT%\StartWise-integration"
set "SW_BACKEND=%SW%\backend"
set "SW_FRONTEND=%SW%\frontend"

set "VENV_ACT=%ROOT%\.venv\Scripts\activate.bat"
if not exist "%VENV_ACT%" set "VENV_ACT=%ROOT%\venv\Scripts\activate.bat"
if not exist "%VENV_ACT%" goto no_venv

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "A2A_BUS_URL=http://localhost:8765"
set "INVESTMENT_AGENT_URL=http://localhost:8002"
set "INVESTMENT_EMBED_BUS_ADAPTER=1"
set "INVESTMENT_BUS_ADAPTER_IN_DJANGO=0"
set "RISK_AGENT_URL=http://localhost:8003"
set "CHROMA_PATH=%ROOT%\chroma_db"
set "PYTHONPATH=%SW%"

copy /Y "%ROOT%\.env" "%SW_BACKEND%\.env" >nul 2>&1

echo [0/6] Redis port 6379...
where docker >nul 2>&1
if not errorlevel 1 goto redis_docker
echo [WARN] Docker absent - Redis doit tourner manuellement
goto after_redis
:redis_docker
docker start redis 2>nul
if errorlevel 1 docker run -d --name redis -p 6379:6379 redis >nul 2>&1
timeout /t 2 /nobreak >nul
:after_redis

where docker >nul 2>&1& "C:\Redis\redis-cli.exe" ping
if not errorlevel 1 goto qdrant_docker
echo [SKIP] Qdrant ignore - Docker absent
goto after_qdrant
:qdrant_docker
echo [Docker] Qdrant port 6333...
docker start qdrant 2>nul
if errorlevel 1 docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant >nul 2>&1
timeout /t 3 /nobreak >nul
:after_qdrant

echo [1/6] Bus A2A port 8765...
start "A2A Bus" cmd /k cd /d "%SW%" ^&^& call "%VENV_ACT%" ^&^& uvicorn a2a_bus.bus_server:app --port 8765
timeout /t 3 /nobreak >nul

echo [2/6] Finance A2A :8001 + Investment A2A :8002 ^(bus consumer integre^) + Risk :8003...
start "Finance A2A" cmd /k cd /d "%SW%" ^&^& call "%VENV_ACT%" ^&^& uvicorn finagents.finance.a2a_server:app --port 8001 --reload
timeout /t 2 /nobreak >nul
start "Investment A2A" cmd /k cd /d "%SW%" ^&^& call "%VENV_ACT%" ^&^& uvicorn finagents.investment.a2a_server:app --port 8002 --reload
timeout /t 2 /nobreak >nul
start "Risk A2A" cmd /k cd /d "%SW_BACKEND%" ^&^& call "%VENV_ACT%" ^&^& uvicorn riskAgent.a2a_server:app --port 8003 --reload
timeout /t 2 /nobreak >nul

echo [3/6] Ideation Agents ports 8101-8103...
start "Ideation Agents" cmd /k cd /d "%SW_BACKEND%" ^&^& call "%VENV_ACT%" ^&^& start /B python -m ideation.agents.question_agent ^&^& start /B python -m ideation.agents.research_agent ^&^& python -m ideation.agents.formulator_agent
timeout /t 4 /nobreak >nul

echo [4/6] Django Backend port 8000...
start "Django Backend" cmd /k cd /d "%SW_BACKEND%" ^&^& call "%VENV_ACT%" ^&^& python manage.py migrate --run-syncdb ^&^& daphne -p 8000 --http-timeout 120 startwise.asgi:application
timeout /t 5 /nobreak >nul

echo [5/6] Next.js Frontend port 3000...
start "Next.js Frontend" cmd /k cd /d "%SW_FRONTEND%" ^&^& npm run dev

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
goto :eof

:no_venv
echo [ERROR] Aucun venv trouve (.venv ou venv).
echo         Cree un environnement virtuel a la racine puis relance.
exit /b 1
