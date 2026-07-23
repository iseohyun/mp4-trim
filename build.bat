@echo off
chcp 65001 > nul
echo ===================================================
echo   Movie Player Lite PyInstaller Build
echo ===================================================
echo   1. Light Version (without ffmpeg, ~7MB)
echo   2. Full Package (with ffmpeg.exe, ~100MB)
echo ===================================================
echo.

set "BUILD_TYPE=1"
set /p "BUILD_TYPE=Select (1 or 2) [default: 1]: "

if "%BUILD_TYPE%"=="2" (
    echo.
    echo Building Full Package with ffmpeg.exe...
    if not exist "ffmpeg.exe" (
        echo [ERROR] ffmpeg.exe not found in root directory.
        pause
        exit /b 1
    )
    python -m PyInstaller --name "movie-player-lite" --noupx --onefile --noconsole --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtMultimedia --hidden-import PyQt6.QtMultimediaWidgets --add-binary "ffmpeg.exe;." --add-data "icon.ico;." --icon="icon.ico" movie-player-lite.py
) else (
    echo.
    echo Building Light Version...
    python -m PyInstaller --name "movie-player-lite" --noupx --onefile --noconsole --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtMultimedia --hidden-import PyQt6.QtMultimediaWidgets --add-data "icon.ico;." --icon="icon.ico" movie-player-lite.py
)

echo.
echo Build complete! Output: dist/movie-player-lite.exe