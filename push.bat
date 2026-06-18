@echo off
set PATH=C:\Program Files\Git\bin;%PATH%
cd /d "%~dp0"

echo.
set /p MSG="Commit message (e.g. 'added feature X'): "

git add .
git commit -m "%MSG%"
git push origin main

echo.
echo Done! Render will auto-deploy in ~2 minutes.
echo Live URL: https://dashboard.onrender.com
echo.
pause
