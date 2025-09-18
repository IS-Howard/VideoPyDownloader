@echo off
setlocal enabledelayedexpansion

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Please download python first
    echo https://www.microsoft.com/store/productid/9MSSZTT1N39L?ocid=pdpshare
    pause
    exit /b 1
)

:: Set venvDir
set "venvDir=Tmp\venv"
echo Using venvDir: !venvDir!

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

echo Setup completed successfully!

endlocal
pause