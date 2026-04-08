@echo off
setlocal
cd /d "%~dp0"

set "DEST=d:\MyNotebook\raw"
if not exist "%DEST%\" mkdir "%DEST%"

if exist "output\*.md" (
    move /Y "output\*.md" "%DEST%\"
    echo Moved output\*.md to %DEST%\
) else (
    echo No .md files in output\
)

endlocal
