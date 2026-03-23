@echo off
REM Park Analyzer - Master Build (calls build_all.ps1)
powershell -ExecutionPolicy Bypass -File "%~dp0build_all.ps1"
pause
