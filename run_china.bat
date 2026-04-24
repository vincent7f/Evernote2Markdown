@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM Reject missing or whitespace-only EVERNOTE_TOKEN before calling Python
if not defined EVERNOTE_TOKEN goto :no_token
set "_T=%EVERNOTE_TOKEN%"
set "_T=%_T: =%"
if "%_T%"=="" goto :no_token

REM Output folder: set OUTPUT_DIR before running, or default output
if "%OUTPUT_DIR%"=="" set "OUTPUT_DIR=output"

REM Optional first arg: days window. Default 7; <=0 means all notes.
set "DAYS=7"
if not "%~1"=="" (
    set "ARG1_NONNUM="
    for /f "delims=0123456789-" %%A in ("%~1") do set "ARG1_NONNUM=1"
    if not defined ARG1_NONNUM if not "%~1"=="-" (
        set "DAYS=%~1"
        shift
    )
)
set "EXTRA_ARGS=%1 %2 %3 %4 %5 %6 %7 %8 %9"

where python >nul 2>&1
if %errorlevel%==0 (
    set "PYTHON_CMD=python"
) else (
    set "PYTHON_CMD=py -3"
)

if %DAYS% LEQ 0 (
    %PYTHON_CMD% export_recent_md_titles.py "%OUTPUT_DIR%" --china --title md !EXTRA_ARGS!
) else (
    %PYTHON_CMD% export_recent_md_titles.py "%OUTPUT_DIR%" --china --days %DAYS% --title md !EXTRA_ARGS!
)
if errorlevel 1 pause
goto :eof

:no_token
echo.
echo  === EVERNOTE_TOKEN not set or only spaces ===
echo.
echo  For China 印象笔记 ^(Yinxiang Biji^), log in in your browser, then open:
echo    https://app.yinxiang.com/api/DeveloperToken.action
echo.
echo  In this Command Prompt, before run_china.bat:
echo    set EVERNOTE_TOKEN=paste_your_token_here
echo.
echo  Or set a User environment variable ^(Win+R -^> sysdm.cpl -^> Advanced
echo  -^> Environment Variables -^> New for your user^): name EVERNOTE_TOKEN
echo.
echo  Optional: edit this .bat and add a line after setlocal:
echo    set EVERNOTE_TOKEN=your_token_here
echo.
pause
exit /b 1
