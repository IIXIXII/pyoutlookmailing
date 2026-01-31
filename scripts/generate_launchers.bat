@ECHO OFF
SETLOCAL EnableExtensions EnableDelayedExpansion

REM =============================================================================
REM  Generate mail launcher scripts (.bat) from mail configuration files (.conf)
REM
REM  Location:
REM    - This generator script is located in:  <repo>\scripts\
REM    - The launcher model is located in:     <repo>\scripts\mail_launcher_model.bat
REM    - Mail definitions are located in:      <repo>\mails\
REM
REM  Rules:
REM    - For each *.conf file found in <repo>\mails\
REM    - If a corresponding *.md file exists
REM    - And if a corresponding *.bat launcher does NOT already exist
REM      => Create the launcher from mail_launcher_model.bat
REM
REM  Existing launchers are preserved.
REM  Missing markdown files cause the mail to be skipped.
REM =============================================================================

REM -----------------------------------------------------------------------------
REM Resolve common.bat (same directory)
REM -----------------------------------------------------------------------------
SET "SCRIPTS_DIR=%~dp0"
SET "FUN=%SCRIPTS_DIR%common.bat"

IF NOT EXIST "%FUN%" (
  ECHO ERROR: common.bat not found: "%FUN%"
  EXIT /B 1
)

REM -----------------------------------------------------------------------------
REM Resolve paths
REM -----------------------------------------------------------------------------
SET "MAILS_DIR=%SCRIPTS_DIR%..\mails"
SET "MODEL=%SCRIPTS_DIR%mail_launcher_model.bat"

FOR %%I IN ("%MAILS_DIR%") DO SET "MAILS_DIR=%%~fI"
FOR %%I IN ("%MODEL%") DO SET "MODEL=%%~fI"

IF NOT EXIST "%MAILS_DIR%" (
  ECHO ERROR: mails directory not found: "%MAILS_DIR%"
  EXIT /B 1
)

IF NOT EXIST "%MODEL%" (
  ECHO ERROR: launcher model not found: "%MODEL%"
  EXIT /B 1
)

REM -----------------------------------------------------------------------------
REM Main loop (interactive)
REM -----------------------------------------------------------------------------
:STARTAGAIN
CALL "%FUN%" :CONFIGURE_DISPLAY
CALL "%FUN%" :CLEAR_SCREEN
CALL "%FUN%" :PRINT_LINE "    Generate mail launchers (.bat)"
CALL "%FUN%" :PRINT_LINE "    Mails directory = %MAILS_DIR%"
CALL "%FUN%" :PRINT_LINE "    Model file      = %MODEL%"
CALL "%FUN%" :LINE_BREAK

REM -----------------------------------------------------------------------------
REM Counters
REM -----------------------------------------------------------------------------
SET /A FOUND=0
SET /A CREATED=0
SET /A SKIPPED=0
SET /A NOMD=0

CALL "%FUN%" :PRINT_LINE "    Scanning *.conf files..."
CALL "%FUN%" :LINE_BREAK

REM -----------------------------------------------------------------------------
REM Scan mails directory
REM -----------------------------------------------------------------------------
FOR %%F IN ("%MAILS_DIR%\*.conf") DO (
  SET /A FOUND+=1

  SET "BASE=%%~nF"
  SET "CONF=%MAILS_DIR%\!BASE!.conf"
  SET "MD=%MAILS_DIR%\!BASE!.md"
  SET "BAT=%MAILS_DIR%\!BASE!.bat"

  CALL "%FUN%" :PRINT_LINE "    [CONF] !BASE!"

  IF NOT EXIST "!MD!" (
    SET /A NOMD+=1
    CALL "%FUN%" :PRINT_LINE "      [SKIP] missing markdown file"
    CALL "%FUN%" :LINE_BREAK
  ) ELSE (
    CALL "%FUN%" :PRINT_LINE "      [OK]   markdown found"

    IF EXIST "!BAT!" (
      SET /A SKIPPED+=1
      CALL "%FUN%" :PRINT_LINE "      [KEEP] launcher already exists"
      CALL "%FUN%" :LINE_BREAK
    ) ELSE (
      CALL "%FUN%" :PRINT_LINE "      [CREATE] creating launcher"
      COPY /Y "%MODEL%" "!BAT!" >NUL
      IF ERRORLEVEL 1 (
        CALL "%FUN%" :PRINT_LINE "      [ERROR] failed to create launcher"
        CALL "%FUN%" :LINE_BREAK
        EXIT /B 1
      )
      SET /A CREATED+=1
      CALL "%FUN%" :PRINT_LINE "      [OK] launcher created"
      CALL "%FUN%" :LINE_BREAK
    )
  )
)

REM -----------------------------------------------------------------------------
REM Summary
REM -----------------------------------------------------------------------------
CALL "%FUN%" :LINE_BREAK
CALL "%FUN%" :PRINT_LINE "    SUMMARY"
CALL "%FUN%" :PRINT_LINE "    conf files found      = %FOUND%"
CALL "%FUN%" :PRINT_LINE "    launchers created    = %CREATED%"
CALL "%FUN%" :PRINT_LINE "    launchers kept       = %SKIPPED%"
CALL "%FUN%" :PRINT_LINE "    skipped (no .md)     = %NOMD%"
CALL "%FUN%" :LINE_BREAK

REM -----------------------------------------------------------------------------
REM Interactive loop
REM -----------------------------------------------------------------------------
CHOICE /C YN /M "Do it again ? (Y/N)"
IF ERRORLEVEL 2 GOTO :EOF
GOTO :STARTAGAIN

:EOF
CALL "%FUN%" :LINE_BREAK
CALL "%FUN%" :PRINT_LINE "    End of launcher generation"
CALL "%FUN%" :LINE_BREAK
EXIT /B 0
