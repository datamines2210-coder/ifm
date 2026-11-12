@echo off
setlocal
cd /d "%~dp0.."
python scripts\organize_project_documents.py %*
exit /b %ERRORLEVEL%
