@echo off
rem Starts the health app backend minimized at logon.
rem Put a shortcut to this file in shell:startup (Win+R -> shell:startup).
if not exist "%LOCALAPPDATA%\health-app" mkdir "%LOCALAPPDATA%\health-app"
cd /d "C:\Users\conor\Health app\backend"
start "health-app" /min cmd /c "uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "%LOCALAPPDATA%\health-app\uvicorn.log" 2>&1"
