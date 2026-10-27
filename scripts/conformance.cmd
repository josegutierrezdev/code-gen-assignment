@echo off
rem HAND-WRITTEN, NOT generated. Thin wrapper: all logic lives in conformance.py.
setlocal
if "%PYTHON%"=="" set PYTHON=python
"%PYTHON%" "%~dp0conformance.py" %*
exit /b %ERRORLEVEL%
