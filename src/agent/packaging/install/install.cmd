@echo off
REM HyperFileLens Agent installer wrapper (cmd.exe entry point; runs install.ps1 internally).
setlocal
set "PS1=%~dp0install.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "EC=%ERRORLEVEL%"
if /I "%~1"=="uninstall" cd /d "%TEMP%"
endlocal & exit /b %EC%
