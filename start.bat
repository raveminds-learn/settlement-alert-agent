@echo off
title RaveMinds Settlement Alert Agent — RaveMinds Series 2
color 0A

echo.
echo  ============================================================
echo   RaveMinds Settlement Alert Agent — RaveMinds Series 2
echo  ============================================================
echo.

:: ── Check Python ─────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)
echo  [OK] Python found

:: ── Check Ollama ─────────────────────────────────────────────
ollama --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Ollama not found. Install from https://ollama.com
    pause
    exit /b 1
)
echo  [OK] Ollama found

:: ── Start Ollama serve in background ─────────────────────────
echo  [..] Starting Ollama server...
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    start /min "" ollama serve
    timeout /t 3 /nobreak >nul
    echo  [OK] Ollama server started
) else (
    echo  [OK] Ollama server already running
)

:: ── Pull Mistral 7B if not present ───────────────────────────
echo  [..] Checking Mistral 7B model...
ollama list | find "mistral" >nul
if errorlevel 1 (
    echo  [..] Pulling Mistral 7B — this may take a few minutes on first run...
    ollama pull mistral
    echo  [OK] Mistral 7B ready
) else (
    echo  [OK] Mistral 7B already available
)

:: ── Install Python dependencies ───────────────────────────────
echo  [..] Installing Python dependencies...
echo      This can take a few minutes on first run.
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo  [OK] Dependencies installed

:: ── Launch Streamlit ──────────────────────────────────────────
echo.
echo  ============================================================
echo   Launching ops workbench at http://localhost:8501
echo   Press Ctrl+C in the browser tab or close this window to stop
echo  ============================================================
echo.

start "" http://localhost:8501
streamlit run ui/app.py --server.port 8501 --server.headless false

