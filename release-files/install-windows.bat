@echo off
setlocal
set "DEST=%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns"
echo Installing VV Generator to:
echo   %DEST%\VVGenerator
if not exist "%DEST%" mkdir "%DEST%"
if exist "%DEST%\VVGenerator" rmdir /s /q "%DEST%\VVGenerator"
xcopy "%~dp0VVGenerator" "%DEST%\VVGenerator\" /E /I /Y >nul
if errorlevel 1 (
  echo.
  echo Installation FAILED. Copy the VVGenerator folder to the path above by hand.
  pause
  exit /b 1
)
if exist "%DEST%\VoronoiStructure" (
  echo.
  echo NOTE: old add-in folder found: %DEST%\VoronoiStructure
  echo       Delete it by hand to avoid two buttons.
)
echo.
echo Done. In Fusion: Utilities ^> Add-Ins ^(Shift+S^) ^> VV Generator ^> Run.
echo If Fusion was already running the add-in, Stop it and Run again.
echo If the toolbar icon looks wrong after an update, restart Fusion once.
pause
