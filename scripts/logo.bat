@ECHO off
REM ===========================================================================
REM                   Author: Florent TOURNOIS | License: MIT                  
REM ===========================================================================

SETLOCAL EnableExtensions

REM -----------------------------------------------------------------------------
REM logo.bat
REM -----------------------------------------------------------------------------
REM This script exposes utility labels (functions) related to logo display.
REM It is designed to be called from another batch script using:
REM   CALL logo.bat :PRINT_LOGO
REM
REM It relies on common.bat for all output operations (PRINT_LINE),
REM in order to centralize console formatting and encoding logic.
REM -----------------------------------------------------------------------------

REM -----------------------------------------------------------------------------
REM Entry point / command dispatcher
REM -----------------------------------------------------------------------------
REM The first argument is expected to be the name of a label (function).
REM The label may optionally be prefixed with ':'.
REM Remaining arguments are forwarded to the label.
REM -----------------------------------------------------------------------------

IF "%~1"=="" (
  ECHO Usage: %~nx0 PRINT_LOGO
  EXIT /B 2
)

REM Normalize the command name (strip leading ':' if present)
SET "CMD=%~1"
IF "%CMD:~0,1%"==":" SET "CMD=%CMD:~1%"

REM Shift arguments so that label parameters start at %1
SHIFT

CALL :%CMD% %1 %2 %3 %4 %5 %6 %7 %8 %9
EXIT /B %ERRORLEVEL%

REM -----------------------------------------------------------------------------
REM PRINT_LOGO
REM -----------------------------------------------------------------------------
REM Displays the ASCII logo using PRINT_LINE from common.bat.
REM The logo is intentionally printed line by line to preserve alignment
REM and allow centralized formatting / encoding handling in common.bat.
REM -----------------------------------------------------------------------------

:PRINT_LOGO
SETLOCAL

REM Path to the shared common utilities script
SET "COMMON=%~dp0common.bat"

REM Ensure common.bat exists before calling it
IF NOT EXIST "%COMMON%" (
  ECHO ERROR: common.bat not found: "%COMMON%"
  ENDLOCAL & EXIT /B 1
)

CALL "%COMMON%" :PRINT_LINE "╔══════════════════════════════════════════════════════════════════════════════════════════════════╗"
CALL "%COMMON%" :PRINT_LINE "║                ____        _   _             _      __  __       _ _ _                           ║"
CALL "%COMMON%" :PRINT_LINE "║               / __ \      | | | |           | |    |  \/  |     (_) (_)                          ║"
CALL "%COMMON%" :PRINT_LINE "║              | |  | |_   _| |_| | ___   ___ | | __ | \  / | __ _ _| |_ _ __   __ _               ║"
CALL "%COMMON%" :PRINT_LINE "║              | |  | | | | | __| |/ _ \ / _ \| |/ / | |\/| |/ _` | | | | '_ \ / _` |              ║"
CALL "%COMMON%" :PRINT_LINE "║              | |__| | |_| | |_| | (_) | (_) |   <  | |  | | (_| | | | | | | | (_| |              ║"
CALL "%COMMON%" :PRINT_LINE "║               \____/ \__,_|\__|_|\___/ \___/|_|\_\ |_|  |_|\__,_|_|_|_|_| |_|\__, |              ║"
CALL "%COMMON%" :PRINT_LINE "║                                                                               __/ |              ║"
CALL "%COMMON%" :PRINT_LINE "║                                                                              |___/               ║"
CALL "%COMMON%" :PRINT_LINE "╚══════════════════════════════════════════════════════════════════════════════════════════════════╝"

ENDLOCAL & EXIT /B 0
