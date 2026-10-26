@echo off
rem Timetabl.ai - start everything locally with one double-click.
rem Opens 3 windows (backend, assistant, web app) and then the browser.
rem Close those 3 windows to stop. Needs: backend\.venv, chatbot\.venv, frontend\node_modules (already set up).

cd /d "%~dp0"
rem Windows' own timeout (Git for Windows can put a different "timeout" first on the PATH).
set "WAIT=%SystemRoot%\System32\timeout.exe"

if not exist "backend\.venv\Scripts\python.exe" (
  echo Backend is not installed yet. See README.md - "Run it locally".
  pause
  exit /b 1
)

rem Already running? Then just open the browser.
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://localhost:3000/login).StatusCode } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
  echo Timetabl.ai is already running. Opening the browser...
  start "" http://localhost:3000
  %WAIT% /t 3 >nul
  exit /b 0
)

rem A port still held by an old window means the new one can't start.
powershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 3000,8000,8001 }) { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo Some Timetabl windows from last time are still open ^(port 3000, 8000 or 8001 is busy^).
  echo Close all "Timetabl" windows, or restart the laptop, then double-click start-local.bat again.
  pause
  exit /b 1
)

echo Starting the backend (port 8000)...
start "Timetabl - backend (8000)" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python -m uvicorn app.main:app --port 8000"

echo Starting the assistant (port 8001)...
start "Timetabl - assistant (8001)" cmd /k "cd /d "%~dp0chatbot" && .venv\Scripts\python -m uvicorn app.main:app --port 8001"

echo Building and starting the web app (port 3000). The first build takes 1-2 minutes...
rem Production build: uses far less memory than "npm run dev" and is what the live site runs.
start "Timetabl - web app (3000)" cmd /k "cd /d "%~dp0frontend" && npm run build && npm run start"

echo Waiting for the web app...
:wait
%WAIT% /t 5 /nobreak >nul
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://localhost:3000/login).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto wait

start "" http://localhost:3000
echo.
echo Timetabl.ai is running at http://localhost:3000  (demo password: demo1234)
echo Close the 3 Timetabl windows to stop it.
%WAIT% /t 8 >nul
