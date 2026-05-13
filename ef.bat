@echo off
setlocal
set ROOT_DIR=%~dp0
set PYTHONPATH=%ROOT_DIR%src;%PYTHONPATH%
python "%ROOT_DIR%src\embedforge\cli.py" %*
