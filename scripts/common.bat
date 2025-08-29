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
:PRINT_LINE <textVar>
(
    SET "LINE_TO_PRINT=%~1"
    SETLOCAL EnableDelayedExpansion
    @ECHO !LINE_TO_PRINT!
    ENDLOCAL
    exit /b
)
REM -------------------------------------------------------------------------------
:CONFIGURE_DISPLAY
(
    CHCP 65001
    MODE 100,40
    exit /b
)
REM -------------------------------------------------------------------------------
:CLEAR_SCREEN
(
	CLS
    CALL :PRINT_LINE "╔══════════════════════════════════════════════════════════════════════════════════════════════════╗"
    CALL :PRINT_LINE "║                                                                                                  ║"
    CALL :PRINT_LINE "║                                            FT                                                    ║"
    CALL :PRINT_LINE "║                                                                                                  ║"
    CALL :PRINT_LINE "╚══════════════════════════════════════════════════════════════════════════════════════════════════╝"
    IF EXIST "%~dp0/logo.bat" (
        CALL "%~dp0/logo.bat" :PRINT_LOGO
    )
    exit /b
)
REM -------------------------------------------------------------------------------
:LINE_BREAK
(
	CALL :PRINT_LINE "├──────────────────────────────────────────────────────────────────────────────────────────────────┤"
    exit /b
)
REM -------------------------------------------------------------------------------
:UPDATE_PIP
(
    python -V
    pip -V
    python -m pip install --upgrade pip wheel setuptools
    exit /b
)
REM -------------------------------------------------------------------------------
:INSTALL_REQUIREMENTS <requirementsFile>
(
    SET "REQUIRE_FILE=%~1"
    SETLOCAL EnableDelayedExpansion
    CALL :PRINT_LINE "   Install requirements !REQUIRE_FILE!" 
    CALL :UPDATE_PIP
    pip install -r !REQUIRE_FILE!
    exit /b
)
REM -------------------------------------------------------------------------------
:INSTALL_EDITABLE
(
    CALL :PRINT_LINE "   Install editable version" 
    CALL :UPDATE_PIP
    pip install -e .
    exit /b
)
REM -------------------------------------------------------------------------------
:PYTHON_SETUP <setupAction>
(
    SET "SETUP_ACTION=%~1"
    SETLOCAL EnableDelayedExpansion
    CALL :PRINT_LINE "   Launch python setup !SETUP_ACTION!" 
    python setup.py !SETUP_ACTION!
    exit /b
)
REM -------------------------------------------------------------------------------
:PYTHON_LAUNCH <filename>
(
    SET "PY_FILE=%~1"
    SETLOCAL EnableDelayedExpansion
    CALL :PRINT_LINE "   python !PY_FILE!" 
    python !PY_FILE!
    exit /b
)
:EOF