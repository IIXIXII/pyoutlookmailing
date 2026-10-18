@ECHO OFF
SETLOCAL EnableExtensions DisableDelayedExpansion
REM Tail-call the shared installer without CALL's second argument expansion.
"%~dp0mailmd_association.bat" install %*
