@echo off
setlocal
cd /d "%~dp0"
title NetCDF Grid Interpolator

echo Checking Python...
where python >nul 2>nul
if errorlevel 1 goto python_missing

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in [(3,10),(3,11),(3,12),(3,13)] else 1)" >nul 2>nul
if errorlevel 1 goto python_unsupported

for /f "delims=" %%V in ('python -c "import sys; print(sys.version.split()[0])"') do set "PYTHON_VERSION=%%V"
echo Found Python %PYTHON_VERSION%.

echo Checking required packages...
python -c "import PyQt5, numpy, pandas, xarray, netCDF4, openpyxl, xlrd" >nul 2>nul
if not errorlevel 1 goto launch

echo Some required packages are missing. Installing them now...
python -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip is not available. Attempting to install pip...
    python -m ensurepip --upgrade
    if errorlevel 1 goto pip_failed
)

python -m pip install -r "%~dp0Requirements.txt"
if errorlevel 1 (
    echo.
    echo The default installation location was not writable.
    echo Retrying for the current Windows user...
    python -m pip install --user -r "%~dp0Requirements.txt"
    if errorlevel 1 goto install_failed
)

python -c "import PyQt5, numpy, pandas, xarray, netCDF4, openpyxl, xlrd" >nul 2>nul
if errorlevel 1 goto import_failed

:launch
echo Starting NetCDF Grid Interpolator...
python "%~dp0Main.py"
if errorlevel 1 goto app_failed
exit /b 0

:python_missing
echo.
echo Python is not installed or is not available in PATH.
echo Install Python 3.12 or 3.13 from https://www.python.org/downloads/
echo During installation, select "Add Python to PATH", then run this file again.
goto failure_pause

:python_unsupported
echo.
echo A supported Python installation was not found.
echo Install Python 3.12 or 3.13 from https://www.python.org/downloads/
echo During installation, select "Add Python to PATH", then run this file again.
goto failure_pause

:pip_failed
echo.
echo pip could not be installed for the default Python environment.
goto failure_pause

:install_failed
echo.
echo The required packages could not be installed.
echo Check the messages above and your internet connection, then try again.
goto failure_pause

:import_failed
echo.
echo Package installation completed, but the required packages cannot be loaded.
echo The default Python installation may be damaged or conflicting with another Python.
goto failure_pause

:app_failed
echo.
echo The application stopped with an error. Review the message above.

:failure_pause
echo.
pause
exit /b 1
