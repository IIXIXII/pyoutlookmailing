@ECHO OFF
SETLOCAL EnableExtensions DisableDelayedExpansion

IF "%~1"=="" (
  ECHO Usage: run_mailmd.bat "invitation.mailmd" [options]
  GOTO :INVALID
)
IF /I NOT "%~x1"==".mailmd" (
  ECHO ERROR: a .mailmd file is required.
  GOTO :INVALID
)
IF NOT EXIST "%~f1" (
  ECHO ERROR: file not found: "%~f1"
  GOTO :INVALID
)

SET "PYTHON=%~dp0..\.venv\Scripts\python.exe"
IF NOT EXIST "%PYTHON%" SET "PYTHON=%~dp0..\..\pyoutlookmailing.venv\Scripts\python.exe"
IF DEFINED PYOUTLOOKMAILING_PYTHON SET "PYTHON=%PYOUTLOOKMAILING_PYTHON%"
IF NOT EXIST "%PYTHON%" (
  ECHO ERROR: Python environment not found. Install the project first.
  GOTO :INVALID
)

TITLE [pyoutlookmailing] MAILMD

REM Display the shared logo once when opening the console, before any retries.
IF EXIST "%~dp0common.bat" IF EXIST "%~dp0logo.bat" (
  CALL "%~dp0common.bat" :CONFIGURE_DISPLAY
  CALL "%~dp0logo.bat" :PRINT_LOGO
)

:STARTAGAIN
ECHO ================================================================================
ECHO    PYOUTLOOKMAILING - traitement du courriel
ECHO    Fichier : "%~f1"
ECHO    Python  : "%PYTHON%"
ECHO --------------------------------------------------------------------------------

REM Reread the selected file on every run, including its configuration and resources.
REM Do not CALL: it would expand percent signs in file names a second time.
ECHO "%PYTHON%" -I -m pyoutlookmailing --conf "%~f1" %2 %3 %4 %5 %6 %7 %8 %9
"%PYTHON%" -I -m pyoutlookmailing --conf "%~f1" %2 %3 %4 %5 %6 %7 %8 %9
SET "RESULT=%ERRORLEVEL%"
ECHO --------------------------------------------------------------------------------
IF "%RESULT%"=="0" (
  ECHO    Traitement termine.
) ELSE (
  ECHO    ERROR: echec du traitement, code %RESULT%.
)
ECHO ================================================================================

REM N, Ctrl+C or unavailable input exits; only an explicit O starts another run.
CHOICE /C ON /M "Relancer le traitement du meme fichier ?"
IF ERRORLEVEL 2 EXIT /B %RESULT%
IF ERRORLEVEL 1 GOTO :STARTAGAIN
EXIT /B %RESULT%

:INVALID
PAUSE
EXIT /B 2
