@echo off
echo ==========================================
echo   Network Diagnosis for Streamlit
echo ==========================================
echo.

echo [1] Checking listening ports...
netstat -an | findstr LISTENING | findstr "8501 8515 8502"
echo.

echo [2] Checking Windows Firewall status...
netsh advfirewall show currentprofile | findstr "State"
echo.

echo [3] Checking firewall rules for 8501/8515/8502...
netsh advfirewall firewall show rule name="Streamlit-DCF" 2>nul || echo Rule Streamlit-DCF: NOT FOUND
netsh advfirewall firewall show rule name="Streamlit-Format" 2>nul || echo Rule Streamlit-Format: NOT FOUND
netsh advfirewall firewall show rule name="Streamlit-Trade" 2>nul || echo Rule Streamlit-Trade: NOT FOUND
netsh advfirewall firewall show rule name="Streamlit-8501" 2>nul || echo Rule Streamlit-8501: NOT FOUND
echo.

echo [4] Testing localhost:8501...
curl -s -o nul -w "%%{http_code}" http://localhost:8501 2>nul || powershell -Command "try { $r=Invoke-WebRequest -Uri 'http://localhost:8501' -UseBasicParsing -TimeoutSec 3; $r.StatusCode } catch { 'FAILED' }"
echo.

echo [5] Local IP addresses...
ipconfig | findstr "IPv4"
echo.

echo [6] Public IP from metadata (if available)...
powershell -Command "try { (Invoke-WebRequest -Uri 'http://100.100.100.200/latest/meta-data/eipv4-ipv4' -TimeoutSec 3 -UseBasicParsing).Content } catch { 'N/A' }"
echo.

echo ==========================================
echo   Diagnosis complete. Copy output above.
echo ==========================================
pause
