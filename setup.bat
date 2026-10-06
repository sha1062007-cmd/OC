@echo off
REM ========================================================
REM Adaptive Study Tutor - Automated Windows Setup
REM ========================================================
echo [1/3] Installing Python dependencies...
python -m pip install -r requirements.txt

echo.
echo [2/3] Running automated curriculum bootstrap and data ingestion...
python scripts\setup.py

echo.
echo [3/3] Running test suite verification...
python -m pytest tests -v

echo.
echo ========================================================
echo Setup finished successfully!
echo To run the automated demo:     run_demo.bat
echo To run the Streamlit web app:  run_app.bat
echo To run tests anytime:          test.bat
echo ========================================================
pause
