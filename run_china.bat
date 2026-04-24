@echo off
setlocal
cd /d "%~dp0"

if not defined EVERNOTE_TOKEN goto :no_token
set "_T=%EVERNOTE_TOKEN%"
set "_T=%_T: =%"
if "%_T%"=="" goto :no_token

if defined MARKDOWN_OUTPUT_FOLDER (
    if exist "%MARKDOWN_OUTPUT_FOLDER%\NUL" (
        set "OUTPUT_DIR=%MARKDOWN_OUTPUT_FOLDER%"
    ) else (
        if "%OUTPUT_DIR%"=="" set "OUTPUT_DIR=output"
    )
) else (
    if "%OUTPUT_DIR%"=="" set "OUTPUT_DIR=output"
)

set "DAYS=7"
if not "%~1"=="" (
    echo(%~1| findstr /R "^-*[0-9][0-9]*$" >nul
    if not errorlevel 1 (
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
    %PYTHON_CMD% export_recent_md_titles.py "%OUTPUT_DIR%" --china --title md %EXTRA_ARGS%
) else (
    %PYTHON_CMD% export_recent_md_titles.py "%OUTPUT_DIR%" --china --days %DAYS% --title md %EXTRA_ARGS%
)
set "EXPORT_EXIT=%errorlevel%"
if not "%EXPORT_EXIT%"=="0" (
    pause
    exit /b %EXPORT_EXIT%
)
goto :eof

:no_token
echo.
echo === EVERNOTE_TOKEN not set or only spaces ===
echo.
echo Get token from:
echo   https://app.yinxiang.com/api/DeveloperToken.action
echo.
echo Before run_china.bat:
echo   set EVERNOTE_TOKEN=paste_your_token_here
echo.
pause
exit /b 1
