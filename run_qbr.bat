@echo off
cd /d %~dp0
call venv\Scripts\activate
start "QBR API" cmd /k "cd /d %~dp0 && call venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8001"
timeout /t 2 /nobreak >nul
start "QBR Dashboard" cmd /k "cd /d %~dp0 && call venv\Scripts\activate && python -m streamlit run app/dashboard.py --server.address 127.0.0.1 --server.port 8501"
echo Dashboard: http://localhost:8501
