import sys
import os
import logging
import traceback
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMessageBox

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # Pointing to root directory when running from source
    APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

LOG_FILE = os.path.join(APP_DIR, "debug.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

def custom_excepthook(exc_type, exc_value, exc_traceback):
    err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical(f"Uncaught Exception:\n{err_str}")
    try:
        with open(os.path.join(APP_DIR, "crash_fatal.log"), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}]\n{err_str}\n\n")
    except Exception:
        pass
    app = QApplication.instance()
    if app:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("프로그램 오류 발생")
        msg.setText(f"프로그램 실행 중 오류가 발생했습니다:\n\n{exc_value}")
        msg.setDetailedText(err_str)
        msg.exec()
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def setup_logging():
    sys.excepthook = custom_excepthook
    logging.info("=== MP4-Trim App Loaded ===")
