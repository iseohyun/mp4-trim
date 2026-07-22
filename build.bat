@echo off
chcp 65001 > nul
echo ===================================================
echo   MP4-Trim PyInstaller 빌드 옵션 선택
echo ===================================================
echo   1. 경량화 버전 (기본값: ffmpeg 미포함, ~7MB)
echo   2. 풀 패키지 버전 (ffmpeg.exe 포함, ~100MB)
echo ===================================================
echo.

set "BUILD_TYPE=1"
set /p "BUILD_TYPE=선택 (1 또는 2) [기본: 1]: "

if "%BUILD_TYPE%"=="2" (
    echo.
    echo [풀 패키지 빌드] ffmpeg.exe 포함 빌드를 시작합니다...
    if not exist "ffmpeg.exe" (
        echo [에러] ffmpeg.exe 파일이 현재 폴더에 없습니다.
        echo ffmpeg.exe를 프로젝트 폴더에 복사한 후 다시 시도하세요.
        pause
        exit /b 1
    )
    python -m PyInstaller --noupx --onefile --noconsole --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtMultimedia --hidden-import PyQt6.QtMultimediaWidgets --add-binary "ffmpeg.exe;." --add-data "icon.ico;." --icon="icon.ico" mp4-trim.py
) else (
    echo.
    echo [경량화 빌드] ffmpeg.exe 미포함 빌드를 시작합니다...
    python -m PyInstaller --noupx --onefile --noconsole --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets --hidden-import PyQt6.QtMultimedia --hidden-import PyQt6.QtMultimediaWidgets --add-data "icon.ico;." --icon="icon.ico" mp4-trim.py
)

echo.
echo 빌드가 완료되었습니다!