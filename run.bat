@echo off
setlocal enabledelayedexpansion

:: Set venvDir
set "venvDir=Tmp\venv"

:: Check if virtual environment exists
if not exist "!venvDir!\Scripts\activate.bat" (
    echo Virtual environment not found. Run setup.bat first!
    pause
    exit /b 1
)

:: Activate the virtual environment and run main.py
call "!venvDir!\Scripts\activate.bat"
:: Run main.py
python main.py
call "!venvDir!\Scripts\deactivate.bat"

endlocal
pause





