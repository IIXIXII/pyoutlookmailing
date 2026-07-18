@ECHO off
REM ===========================================================================
REM                   Author: Florent TOURNOIS | License: MIT                  
REM ===========================================================================

SETLOCAL EnableExtensions

REM ---------------------------------------------------------------------------
REM Entry point / command dispatcher
REM Usage:
REM   CALL common.bat :PRINT_LINE "hello"
REM   CALL common.bat PRINT_LINE "hello"
REM ---------------------------------------------------------------------------

IF "%~1"=="" (
  ECHO Usage: %~nx0 ^<COMMAND^> [args...]
  ECHO Commands:
  ECHO   PRINT_LINE CONFIGURE_DISPLAY CLEAR_SCREEN LINE_BREAK
  ECHO   UPDATE_PIP INSTALL_REQUIREMENTS INSTALL_EDITABLE
  ECHO   PYTHON_SETUP PYTHON_LAUNCH GET_PYTHON
  EXIT /B 2
)

SET "CMD=%~1"
IF "%CMD:~0,1%"==":" SET "CMD=%CMD:~1%"
SHIFT

REM Only initialize venv python for commands that actually need it
IF /I "%CMD%"=="UPDATE_PIP"           CALL :INIT_PYTHON || EXIT /B 1
IF /I "%CMD%"=="INSTALL_REQUIREMENTS" CALL :INIT_PYTHON || EXIT /B 1
IF /I "%CMD%"=="INSTALL_EDITABLE"     CALL :INIT_PYTHON || EXIT /B 1
IF /I "%CMD%"=="PYTHON_SETUP"         CALL :INIT_PYTHON || EXIT /B 1
IF /I "%CMD%"=="PYTHON_LAUNCH"        CALL :INIT_PYTHON || EXIT /B 1
IF /I "%CMD%"=="GET_PYTHON"           CALL :INIT_PYTHON || EXIT /B 1

CALL :%CMD% %1 %2 %3 %4 %5 %6 %7 %8 %9
EXIT /B %ERRORLEVEL%

REM ---------------------------------------------------------------------------
:PRINT_LINE
SETLOCAL EnableDelayedExpansion
SET "LINE_TO_PRINT=%~1"
ECHO(!LINE_TO_PRINT!
ENDLOCAL & EXIT /B 0

:CONFIGURE_DISPLAY
CHCP 65001 >NUL 2>&1
MODE 100,40 >NUL 2>&1
EXIT /B 0

:CLEAR_SCREEN
CLS
CALL :PRINT_LINE "╔══════════════════════════════════════════════════════════════════════════════════════════════════╗"
CALL :PRINT_LINE "║                                                                                                  ║"
CALL :PRINT_LINE "║                                            FT                                                    ║"
CALL :PRINT_LINE "║                                                                                                  ║"
CALL :PRINT_LINE "╚══════════════════════════════════════════════════════════════════════════════════════════════════╝"
IF EXIST "%~dp0logo.bat" (
  CALL "%~dp0logo.bat" :PRINT_LOGO
)
EXIT /B 0

:LINE_BREAK
CALL :PRINT_LINE "├──────────────────────────────────────────────────────────────────────────────────────────────────┤"
EXIT /B 0

REM ---------------------------------------------------------------------------
REM Initialize venv python
REM - common.bat is located in <repo>\scripts\common.bat
REM - venv is located in <repo>\.venv
REM ---------------------------------------------------------------------------
:INIT_PYTHON
IF /I "%PYTHON_READY%"=="1" EXIT /B 0

REM Normalize repo root
FOR %%I IN ("%~dp0..") DO SET "REPO_ROOT=%%~fI"
SET "VENV_DIR=%REPO_ROOT%\.venv"
SET "PYTHON=%VENV_DIR%\Scripts\python.exe"

IF NOT EXIST "%PYTHON%" (
  CALL :PRINT_LINE "      venv not found, creating it: %VENV_DIR%"

  REM Bootstrap relies on python.exe in PATH (once, only to create venv)
  python.exe -V >NUL 2>&1
  IF ERRORLEVEL 1 (
    ECHO ERROR: python.exe not available in PATH to create the venv.
    EXIT /B 1
  )

  python.exe -m venv "%VENV_DIR%"
  IF ERRORLEVEL 1 (
    ECHO ERROR: failed to create venv at "%VENV_DIR%".
    EXIT /B 1
  )
)

IF NOT EXIST "%PYTHON%" (
  ECHO ERROR: venv python not found: "%PYTHON%"
  EXIT /B 1
)

SET "PYTHON_READY=1"
CALL :PRINT_LINE "   using python PYTHON=%PYTHON%"
EXIT /B 0

:GET_PYTHON
ECHO %PYTHON%
EXIT /B 0

REM ---------------------------------------------------------------------------
:UPDATE_PIP
"%PYTHON%" -m pip -V >NUL 2>&1
IF ERRORLEVEL 1 (
  ECHO ERROR: pip not available in venv.
  EXIT /B 1
)

"%PYTHON%" -m pip install --upgrade pip wheel setuptools
IF ERRORLEVEL 1 (
  ECHO ERROR: pip upgrade failed.
  EXIT /B 1
)

EXIT /B 0

REM ---------------------------------------------------------------------------
:INSTALL_REQUIREMENTS
SETLOCAL EnableExtensions
SET "REQUIRE_FILE=%~1"

IF "%REQUIRE_FILE%"=="" (
  ECHO ERROR: Missing requirements file.
  ENDLOCAL & EXIT /B 2
)

IF NOT EXIST "%REQUIRE_FILE%" (
  ECHO ERROR: Requirements file not found: "%REQUIRE_FILE%"
  ENDLOCAL & EXIT /B 2
)

CALL :UPDATE_PIP
IF ERRORLEVEL 1 (ENDLOCAL & EXIT /B 1)

"%PYTHON%" -m pip install -r "%REQUIRE_FILE%"
IF ERRORLEVEL 1 (
  ECHO ERROR: pip install failed.
  ENDLOCAL & EXIT /B 1
)

ENDLOCAL & EXIT /B 0

REM ---------------------------------------------------------------------------
:INSTALL_EDITABLE
CALL :PRINT_LINE "   Install editable version (venv)"

CALL :UPDATE_PIP
IF ERRORLEVEL 1 EXIT /B 1

"%PYTHON%" -m pip install --editable .
IF ERRORLEVEL 1 (
  ECHO ERROR: editable install failed.
  EXIT /B 1
)

EXIT /B 0

REM ---------------------------------------------------------------------------
:PYTHON_SETUP
CALL :INIT_PYTHON
IF ERRORLEVEL 1 EXIT /B 1

SETLOCAL EnableExtensions
SET "SETUP_ACTION=%~1"

IF "%SETUP_ACTION%"=="" (
  ECHO ERROR: Missing setup action.
  ENDLOCAL & EXIT /B 2
)

CALL :PRINT_LINE "   Launch python setup %SETUP_ACTION%"
"%PYTHON%" setup.py %SETUP_ACTION%
IF ERRORLEVEL 1 (
  ECHO ERROR: setup.py failed.
  ENDLOCAL & EXIT /B 1
)

ENDLOCAL & EXIT /B 0

REM ---------------------------------------------------------------------------
:PYTHON_LAUNCHER
REM Usage: CALL common.bat :PYTHON_LAUNCHER "<script.py>" [args...]
CALL :INIT_PYTHON
IF ERRORLEVEL 1 EXIT /B 1

SETLOCAL EnableExtensions
SET "PY_FILE=%~1"
SHIFT

IF "%PY_FILE%"=="" (
  ECHO ERROR: Missing python file.
  ENDLOCAL & EXIT /B 2
)

IF NOT EXIST "%PY_FILE%" (
  ECHO ERROR: Python file not found: "%PY_FILE%"
  ENDLOCAL & EXIT /B 2
)

REM After SHIFT, args start at %1
CALL :PRINT_LINE "   %PYTHON% %PY_FILE% %1 %2 %3 %4"
"%PYTHON%" "%PY_FILE%" %1 %2 %3 %4
SET "RC=%ERRORLEVEL%"

ENDLOCAL & EXIT /B %RC%


REM ---------------------------------------------------------------------------
:PYTHON_FROM_MAKE
REM Called as: :PYTHON_FROM_MAKE python file.py [args...]
CALL :INIT_PYTHON
IF ERRORLEVEL 1 EXIT /B 1

SETLOCAL EnableExtensions

IF /I "%~1" NEQ "python" (
  ECHO ERROR: PYTHON_FROM_MAKE expects first arg "python".
  ENDLOCAL & EXIT /B 2
)

IF "%~2"=="" (
  ECHO ERROR: Missing python file.
  ENDLOCAL & EXIT /B 2
)

SET "PY_FILE=%~2"

REM Forward up to 8 args after the file (adjust if needed)
CALL :_PYTHON_FROM_MAKE_CALL "%PY_FILE%" %3 %4 %5 %6 %7 %8 %9
SET "RC=%ERRORLEVEL%"

ENDLOCAL & EXIT /B %RC%

:_PYTHON_FROM_MAKE_CALL
REM %1 = file, %2.. = remaining args
CALL :PYTHON_LAUNCHER "%~1" %2 %3 %4 %5 %6 %7 %8 %9
EXIT /B %ERRORLEVEL%
REM ---------------------------------------------------------------------------
