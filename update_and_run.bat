@echo off
echo Resetting local changes...
git reset --hard HEAD
if errorlevel 1 goto :error

echo Pulling latest changes...
git pull
if errorlevel 1 goto :error

echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 goto :error

echo Running database migrations...
python manage.py migrate
if errorlevel 1 goto :error

echo Starting Django Development Server...
python manage.py runserver
goto :eof

:error
echo.
echo A step failed. See the output above for details.
pause
