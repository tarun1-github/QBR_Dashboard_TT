@echo off
cd /d %~dp0
call venv\Scripts\activate
if not exist data\input\ServiceNow.xlsx (
 echo Put ServiceNow.xlsx in data\input first.
 pause
 exit /b 1
)
python -m app.ingest
pause
