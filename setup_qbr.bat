@echo off
cd /d %~dp0
if not exist venv\Scripts\python.exe python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m app.init_db
python -m app.seed_demo
pause
