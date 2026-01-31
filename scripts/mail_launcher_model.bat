@ECHO OFF
SETLOCAL EnableExtensions

REM -----------------------------------------------------------------------------
REM Resolve make.bat
REM -----------------------------------------------------------------------------
SET "MAKE=%~dp0..\make.bat"
IF NOT EXIST "%MAKE%" (
  ECHO ERROR: make.bat not found: "%MAKE%"
  EXIT /B 1
)

REM -----------------------------------------------------------------------------
REM Resolve paths
REM -----------------------------------------------------------------------------
SET "MYPATH=%~dp0"
CD /D "%MYPATH%" || (ECHO ERROR: cannot cd to "%MYPATH%" & EXIT /B 1)

SET "ARGUMENT=%~n0"

REM mailing.py absolute path
FOR %%I IN ("%MYPATH%..\scripts\mailing.py") DO SET "MAIL=%%~fI"
IF NOT EXIST "%MAIL%" (
  ECHO ERROR: mailing.py not found: "%MAIL%"
  EXIT /B 1
)

REM conf file absolute path
FOR %%I IN ("%MYPATH%%ARGUMENT%.conf") DO SET "CONF=%%~fI"
IF NOT EXIST "%CONF%" (
  ECHO ERROR: conf file not found: "%CONF%"
  EXIT /B 1
)

CALL "%MAKE%" python "%MAIL%" --conf "%CONF%"
EXIT /B %ERRORLEVEL%