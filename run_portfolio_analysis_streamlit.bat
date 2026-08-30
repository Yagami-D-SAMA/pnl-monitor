@echo off
setlocal

cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" -m streamlit run "%~dp0portfolio_analysis_streamlit.py"
) else (
    python -m streamlit run "%~dp0portfolio_analysis_streamlit.py"
)

pause
