@echo off
title OVERLORD Tactical C2 Dashboard
color 0B

echo =================================================================
echo        OVERLORD // Autonomous UAV ^& UGV Tactical C2 System       
echo =================================================================

cd /d "%~dp0"

:: 1. Check Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in PATH. Please install Python 3.10+ and check 'Add Python to PATH'.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
if not exist ".venv" (
    echo [+] Creating virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [+] Virtual environment detected.
)

:: 3. Activate and Install Dependencies
call .venv\Scripts\activate.bat
echo [+] Verifying and installing dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

:: 4. Ensure directories exist
if not exist "storage\snapshots" mkdir "storage\snapshots"

echo.
echo =================================================================
echo  [OK] OVERLORD Tactical C2 Dashboard starting...
echo  [>] Opening http://localhost:8000 in default browser...
echo =================================================================
echo.

:: Launch browser in background after 2 seconds
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000"

:: 5. Run Server
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
