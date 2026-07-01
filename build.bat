@echo off
python -m PyInstaller --onefile --noconsole --add-binary "ffmpeg.exe;." --icon="dist/icon.ico" mp4-trim.py