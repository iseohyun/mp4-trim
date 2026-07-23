import sys
import os
import ctypes
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from src.utils.logger import setup_logging, APP_DIR
from src.ui.main_window import VideoCutterApp

setup_logging()

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(APP_DIR, relative_path)

def main():
    try:
        try:
            myappid = "iseohyun.movieplayerlite.1.5"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logging.warning(f"Failed to set AppUserModelID: {e}")

        app = QApplication(sys.argv)
        
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        ex = VideoCutterApp()
        if os.path.exists(icon_path):
            ex.setWindowIcon(QIcon(icon_path))

        ex.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical("Fatal crash in main execution block!", exc_info=True)
        raise

if __name__ == "__main__":
    main()
