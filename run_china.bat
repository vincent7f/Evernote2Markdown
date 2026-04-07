@echo off
setlocal
cd /d "%~dp0"

REM Reject missing or whitespace-only EVERNOTE_TOKEN before calling Python
if not defined EVERNOTE_TOKEN goto :no_token
set "_T=%EVERNOTE_TOKEN%"
set "_T=%_T: =%"
if "%_T%"=="" goto :no_token

REM Output folder: set OUTPUT_DIR before running, or default exported_md
if "%OUTPUT_DIR%"=="" set "OUTPUT_DIR=exported_md"

where python >nul 2>&1
if %errorlevel%==0 (
    python export_recent_md_titles.py "%OUTPUT_DIR%" --china --days 7 --title md %*
) else (
    py -3 export_recent_md_titles.py "%OUTPUT_DIR%" --china --days 7 --title md %*
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
