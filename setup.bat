@echo off
setlocal enabledelayedexpansion

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    python
    pause
    exit /b 1
)

:: Read Config
set "configFile=./config"
if not exist "%configFile%" (
    echo Config file not found: %configFile%
    pause
    exit /b 1
)

for /f "tokens=*" %%a in ('type "%configFile%"') do (
    set "line=%%a"
    if "!line:~0,15!" == "python venvDir:" (
        set "venvDir=!line:~15!"
	set "venvDir=!venvDir: =!"
        echo Found venvDir in config.txt: !venvDir!
        goto create_venv
    )
)

echo Config entry 'python venvDir:' not found in config.txt
pause
exit /b 1

:create_venv
:: Create a Python virtual environment in the specified directory
python -m venv "!venvDir!"
if %errorlevel% neq 0 (
    echo Failed to create virtual environment in !venvDir!
    pause
    exit /b 1
)

echo Virtual environment created in !venvDir!

:: Activate the virtual environment
call "!venvDir!\Scripts\activate"

:: Install dependencies from requirements.txt
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies from requirements.txt
    pause
    exit /b 1
)

echo Init: done>>"%configFile%"

endlocal
pause