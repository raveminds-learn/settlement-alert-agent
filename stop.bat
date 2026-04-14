@echo off
title RaveMinds Settlement Alert Agent — Stop
color 0C

echo.
echo  ============================================================
echo   Stopping RaveMinds Settlement Alert Agent — RaveMinds Series 2
echo  ============================================================
echo.

:: ── Stop Streamlit ────────────────────────────────────────────
echo  [..] Stopping Streamlit...
taskkill /f /im streamlit.exe >nul 2>&1
taskkill /f /fi "windowtitle eq RaveMinds Settlement Alert Agent*" >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8501"') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo  [OK] Streamlit stopped

:: ── Stop Ollama ───────────────────────────────────────────────
echo  [..] Stopping Ollama server...
taskkill /f /im ollama.exe >nul 2>&1
echo  [OK] Ollama stopped

echo.
echo  All services stopped.
echo.
pause
