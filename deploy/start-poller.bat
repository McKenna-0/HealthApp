@echo off
rem Starts the GitHub issue poller minimized at logon.
rem Put a shortcut to this file in shell:startup (Win+R -> shell:startup).
if not exist "%LOCALAPPDATA%\health-app" mkdir "%LOCALAPPDATA%\health-app"
cd /d "C:\Users\conor\Health app"
start "github-poller" /min cmd /c "python scripts/github_poller.py >> "%LOCALAPPDATA%\health-app\poller.log" 2>&1"
