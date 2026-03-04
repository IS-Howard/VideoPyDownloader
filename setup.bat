@echo off
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)
uv sync
echo Setup completed successfully!
pause
