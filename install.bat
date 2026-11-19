@echo off
setlocal
cd /d "%~dp0"
if not exist "starter\pack.lock.json" (
  echo Extract the complete Flux starter ZIP before running this installer.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Install Python 3.10 or newer from python.org, including the Python launcher.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Available serial devices:
".venv\Scripts\python.exe" -m serial.tools.list_ports -v
echo.
echo Check the COM port in Windows Device Manager. Verify your radio model and chip.
set "FLUX_PORT="
set /p "FLUX_PORT=Enter the programming cable COM port (for example COM5): "
if not defined FLUX_PORT goto failed
rem Pass the environment value through Python to avoid cmd interpreting user input.
".venv\Scripts\python.exe" -c "import os,sys; sys.path.insert(0,'tools'); import k6; sys.exit(k6.main(['starter-install','starter','--port',os.environ['FLUX_PORT']]))"
if errorlevel 1 goto failed
echo Installation completed.
pause
exit /b 0
:failed
echo Installation did not complete. Read the output above before retrying.
pause
exit /b 1
