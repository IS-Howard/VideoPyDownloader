@echo off
setlocal enabledelayedexpansion

:: Read Config
set "configFile=./config"
if not exist "%configFile%" (
    echo Config file not found: %configFile%
    pause
    exit /b 1
)

:: Initialize variables
set "venvDir="
set "initDone="

for /f "tokens=*" %%a in ('type "%configFile%"') do (
    set "line=%%a"
    if "!line:~0,15!" == "python venvDir:" (
        set "venvDir=!line:~15!"
        set "venvDir=!venvDir: =!"
        echo Found venvDir in config.txt: !venvDir!
    ) else if "!line!" == "Init: done" (
        set "initDone=true"
        echo Found 'Init: done' in config.txt
    )
)

:: Activate the virtual environment and run main.py only if 'Init: done' is found
if defined initDone (
    if defined venvDir (
        :: Activate the virtual environment
        call "!venvDir!\Scripts\activate.bat"
        echo Virtual environment activated from config.txt

        :: Run main.py
        python main.py

        :: Deactivate the virtual environment when done (optional)
        call "!venvDir!\Scripts\deactivate.bat"
        echo Virtual environment deactivated
    ) else (
        echo Error: 'venvDir' not found in config.txt
        pause
        exit /b 1
    )
) else (
    echo 'Init: done' not found in config.txt, skipping virtual environment activation and script execution
)

endlocal
pause





