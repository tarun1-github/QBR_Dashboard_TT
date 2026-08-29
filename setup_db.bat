@echo off
REM ============================================================
REM QBR Dashboard - Database Setup Batch File
REM ============================================================
REM Run this file to set up the database schema and load sample data.
REM 
REM Prerequisites:
REM   - SQL Server with CPDB database
REM   - sqlcmd utility installed
REM ============================================================

echo.
echo ============================================
echo QBR Dashboard - Database Setup
echo ============================================
echo.

SET SERVER=HQ-AD-DNS-CLONE\SQLEXPRESS
SET DATABASE=CPDB

echo Server: %SERVER%
echo Database: %DATABASE%
echo.

REM Step 1: Create Schema
echo [1/5] Creating schema and tables...
sqlcmd -S %SERVER% -d %DATABASE% -i "sql\01_create_qbr_schema_v2.sql" -b
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create schema
    pause
    exit /b 1
)
echo.

REM Step 2: Seed Reference Data
echo [2/5] Inserting reference data (Towers, Tracks, Customers)...
sqlcmd -S %SERVER% -d %DATABASE% -i "sql\02_seed_reference_data.sql" -b
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to seed reference data
    pause
    exit /b 1
)
echo.

REM Step 3: Insert Sample Data
echo [3/5] Inserting sample tickets and alerts...
sqlcmd -S %SERVER% -d %DATABASE% -i "sql\03_insert_sample_data.sql" -b
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to insert sample data
    pause
    exit /b 1
)
echo.

REM Step 4: Create Analytics Views
echo [4/5] Creating analytics views and procedures...
sqlcmd -S %SERVER% -d %DATABASE% -i "sql\05_analytics_views.sql" -b
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create analytics views
    pause
    exit /b 1
)
echo.

REM Step 5: Verify Setup
echo [5/5] Verifying setup...
sqlcmd -S %SERVER% -d %DATABASE% -Q "SELECT 'Towers' AS Item, COUNT(*) AS Count FROM qbr.Tower UNION ALL SELECT 'Tracks', COUNT(*) FROM qbr.Track UNION ALL SELECT 'Customers', COUNT(*) FROM qbr.Customer UNION ALL SELECT 'Tickets', COUNT(*) FROM qbr.Ticket UNION ALL SELECT 'Alerts', COUNT(*) FROM qbr.Alert UNION ALL SELECT 'KPIs', COUNT(*) FROM qbr.DashboardKPI" -b
echo.

echo ============================================
echo Database setup completed successfully!
echo ============================================
echo.
echo Next steps:
echo   1. Run: streamlit run app/dashboard.py
echo   2. Or load your own data: python load_data.py
echo.
pause
