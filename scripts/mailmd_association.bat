@ECHO OFF
SETLOCAL EnableExtensions DisableDelayedExpansion
SET "PYTHON=%~dp0..\.venv\Scripts\python.exe"
IF NOT EXIST "%PYTHON%" SET "PYTHON=%~dp0..\..\pyoutlookmailing.venv\Scripts\python.exe"
IF DEFINED PYOUTLOOKMAILING_PYTHON SET "PYTHON=%PYOUTLOOKMAILING_PYTHON%"
IF NOT EXIST "%PYTHON%" (
  ECHO ERROR: Python environment not found. Install the project first.
  PAUSE
  EXIT /B 1
)
"%PYTHON%" -I -m pyoutlookmailing.windows_association --launcher "%~dp0run_mailmd.bat" %*
SET "RESULT=%ERRORLEVEL%"
PAUSE
EXIT /B %RESULT%
