@ECHO off
REM ===========================================================================
REM                   Author: Florent TOURNOIS | License: MIT                  
REM ===========================================================================
SET MYPATH=%~dp0
CD %MYPATH%
SET ARGUMENT=%~n0
SET MODULE=pyoutlookmailing
SET FUN=../scripts/common.bat
IF EXIST ..\%MODULE%\version.bat (
    CALL ..\%MODULE%\version.bat
) ELSE (
    SET VERSION=Not found
)
REM -------------------------------------------------------------------------------
:STARTAGAIN
CALL %FUN% :CONFIGURE_DISPLAY
CALL %FUN% :CLEAR_SCREEN
CALL %FUN% :PRINT_LINE "    VERSION=%VERSION%" 
CALL %FUN% :PRINT_LINE "    MYPATH=%MYPATH%" 
CALL %FUN% :LINE_BREAK

TITLE [%MODULE%] MAKE %ARGUMENT%
python ../scripts/mailing.py --conf="%ARGUMENT%.conf"

REM -------------------------------------------------------------------------------
CALL %FUN% :LINE_BREAK
CALL %FUN% :PRINT_LINE "   End of the make execution"
CALL %FUN% :LINE_BREAK
REM -------------------------------------------------------------------------------
CHOICE /C:YN /M "Do it again ? (Y/N)"
IF "%ERRORLEVEL%" EQU "1" GOTO :STARTAGAIN
IF "%ERRORLEVEL%" EQU "2" GOTO :EOF
REM -------------------------------------------------------------------------------
:EOF
