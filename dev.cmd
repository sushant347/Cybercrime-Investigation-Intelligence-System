@echo off
rem ===========================================================================
rem  CIIE launcher for Windows.
rem
rem  Double-click this file, or run it from cmd.exe / PowerShell:
rem
rem      dev.cmd            create/repair dependencies and start everything
rem      dev.cmd setup      prepare dependencies without starting
rem
rem  All it does is find Git Bash and hand over to dev.sh, which is the real
rem  launcher. dev.sh is a bash script, so it cannot run in cmd.exe or
rem  PowerShell directly - discovering that the hard way is the usual first
rem  hurdle on Windows.
rem
rem  Note it deliberately does NOT use WSL's bash even when installed: the
rem  virtualenvs are built for Windows Python and would not be usable from
rem  inside WSL.
rem ===========================================================================
setlocal enabledelayedexpansion

rem Run from the repo root so dev.sh (and the bash it starts) inherit it.
cd /d "%~dp0"

set "BASH="

rem Well-known Git for Windows locations, in order of likelihood.
for %%P in (
  "%ProgramFiles%\Git\bin\bash.exe"
  "%ProgramFiles(x86)%\Git\bin\bash.exe"
  "%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
  "%ProgramW6432%\Git\bin\bash.exe"
) do (
  if not defined BASH if exist "%%~P" set "BASH=%%~P"
)

rem Otherwise derive it from wherever git.exe lives (<git>\cmd\git.exe ->
rem <git>\bin\bash.exe), which covers custom install directories.
if not defined BASH (
  for /f "delims=" %%G in ('where git 2^>nul') do (
    if not defined BASH (
      for %%D in ("%%~dpG..") do (
        if exist "%%~fD\bin\bash.exe" set "BASH=%%~fD\bin\bash.exe"
      )
    )
  )
)

if not defined BASH (
  echo.
  echo   ERROR: Git Bash was not found on this computer.
  echo.
  echo   CIIE is started by dev.sh, a bash script. On Windows that needs
  echo   Git for Windows, which includes Git Bash:
  echo.
  echo       https://git-scm.com/download/win
  echo.
  echo   Install it ^(the default options are fine^), then run this file again.
  echo.
  pause
  exit /b 1
)

"%BASH%" ./dev.sh %*
set "RC=%ERRORLEVEL%"

rem Double-clicked windows vanish on exit, taking the error message with them.
if not "%RC%"=="0" pause
exit /b %RC%
