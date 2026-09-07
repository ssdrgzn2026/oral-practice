@echo off
if not defined in_subprocess (
    set in_subprocess=1
    cmd /k "%~f0" %*
    exit /b
)

py -3 --version >nul 2>&1
if %errorlevel% == 0 (
    py -3 launcher.py
    exit /b
)

python --version >nul 2>&1
if %errorlevel% == 0 (
    python launcher.py
    exit /b
)

echo ERROR: Python not found.
pause
exit /b 1
