@ECHO OFF
SETLOCAL EnableExtensions

SET "MAKE=%~dp0..\make.bat"
IF NOT EXIST "%MAKE%" (
  ECHO ERROR: make.bat not found: "%MAKE%"
  EXIT /B 1
)

CALL "%MAKE%" "%~n0"
EXIT /B %ERRORLEVEL%