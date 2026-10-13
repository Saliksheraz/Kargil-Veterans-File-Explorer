@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto :error

if /i "%~1"=="--offline" goto :offline

echo Pulling latest changes...
git pull --ff-only
if errorlevel 1 goto :update_failed

echo Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
goto :prepare

:update_failed
echo.
echo The update failed. The latest changes have not been installed.
echo If Git reports "Could not resolve host", check your internet connection and DNS, then retry.
echo You can also start the existing local version with already installed dependencies.
choice /c CQ /n /m "[C] Continue with local version or [Q] Quit: "
if errorlevel 2 goto :error
if errorlevel 1 goto :offline
goto :error

:offline
echo Starting the existing local version. Skipping update and dependency installation.
python -c "import django; import PIL"
if errorlevel 1 goto :offline_dependencies_missing
goto :prepare

:offline_dependencies_missing
echo.
echo Offline launch requires Python, Django, and Pillow to be installed.
echo Reconnect to the internet and run this script again to install dependencies.
goto :error

:prepare
echo Creating database migrations...
python manage.py makemigrations
if errorlevel 1 goto :error

echo Running database migrations...
python manage.py migrate
if errorlevel 1 goto :error

echo Starting Django Development Server...
python manage.py runserver
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo A step failed. See the output above for details.
pause
exit /b 1
