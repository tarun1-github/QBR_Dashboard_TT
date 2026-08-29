@echo off
cd /d %~dp0
echo ==========================================================
echo QBR V4 SQL MIGRATION
echo ==========================================================
echo Open SQL Server Management Studio.
echo Select the QBR database.
echo Run: sql\04_v4_tower_login_access.sql
echo.
echo DO NOT run this batch as-is; it is a reminder because
echo database server/credentials are not hard-coded.
pause
