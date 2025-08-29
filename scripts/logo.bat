@ECHO off
REM # -----------------------------------------------------------------------------
REM # 
REM # Copyright (c) 2018 Florent TOURNOIS
REM # 
REM # Permission is hereby granted, free of charge, to any person obtaining a copy
REM # of this software and associated documentation files (the "Software"), to deal
REM # in the Software without restriction, including without limitation the rights
REM # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
REM # copies of the Software, and to permit persons to whom the Software is
REM # furnished to do so, subject to the following conditions:
REM # 
REM # The above copyright notice and this permission notice shall be included in 
REM # all copies or substantial portions of the Software.
REM # 
REM # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
REM # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
REM # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
REM # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
REM # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
REM # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
REM # SOFTWARE.
REM # 
REM # -----------------------------------------------------------------------------
CALL %*
GOTO EOF
REM -------------------------------------------------------------------------------
:PRINT_LOGO
(
    SET "COMMON=%~dp0/common.bat"
    SETLOCAL EnableDelayedExpansion
    CALL !COMMON! :PRINT_LINE "╔══════════════════════════════════════════════════════════════════════════════════════════════════╗"
    CALL !COMMON! :PRINT_LINE "║                ____        _   _             _      __  __       _ _ _                           ║"
    CALL !COMMON! :PRINT_LINE "║               / __ \      | | | |           | |    |  \/  |     (_) (_)                          ║"
    CALL !COMMON! :PRINT_LINE "║              | |  | |_   _| |_| | ___   ___ | | __ | \  / | __ _ _| |_ _ __   __ _               ║"
    CALL !COMMON! :PRINT_LINE "║              | |  | | | | | __| |/ _ \ / _ \| |/ / | |\/| |/ _` | | | | '_ \ / _` |              ║"
    CALL !COMMON! :PRINT_LINE "║              | |__| | |_| | |_| | (_) | (_) |   <  | |  | | (_| | | | | | | | (_| |              ║"
    CALL !COMMON! :PRINT_LINE "║               \____/ \__,_|\__|_|\___/ \___/|_|\_\ |_|  |_|\__,_|_|_|_|_| |_|\__, |              ║"
    CALL !COMMON! :PRINT_LINE "║                                                                               __/ |              ║"
    CALL !COMMON! :PRINT_LINE "║                                                                              |___/               ║"
    CALL !COMMON! :PRINT_LINE "╚══════════════════════════════════════════════════════════════════════════════════════════════════╝"
    ENDLOCAL
    exit /b
)
:EOF