@echo off
setlocal enabledelayedexpansion

:: Read Config
set "configFile=./config"
if not exist "%configFile%" (
    echo Config file not found
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
    ) else if "!line!" == "Init: Y" (
        set "initDone=true"
    )
)

:: Activate the virtual environment and run main.py only if 'Init: done' is found
if defined initDone (
    if defined venvDir (
        call "!venvDir!\Scripts\activate.bat"
        :: Run main.py
        python main.py
        call "!venvDir!\Scripts\deactivate.bat"
    ) else (
        echo Error: venvDir not found
        pause
        exit /b 1
    )
) else (
    echo 'Run setup.bat first!'
)

endlocal
pause





