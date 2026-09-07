@echo off
echo ==========================================
echo     File Format Converter
echo ==========================================
echo.
echo Starting Streamlit server...
echo Please wait...
echo.
streamlit run app.py
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start.
    echo Please run: pip install -r requirements.txt
    echo.
    pause
)
