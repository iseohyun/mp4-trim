import sys
import os
import ctypes
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from src.utils.logger import setup_logging, APP_DIR
from src.ui.main_window import VideoCutterApp

setup_logging()

def main():
    try:
        try:
            myappid = "mycompany.mp4trimmer.cutter.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            logging.warning(f"Failed to set AppUserModelID: {e}")

        app = QApplication(sys.argv)
        ex = VideoCutterApp()

        icon_path = os.path.join(APP_DIR, "dist", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(APP_DIR, "icon.ico")
        if os.path.exists(icon_path):
            ex.setWindowIcon(QIcon(icon_path))

        ex.show()
        sys.exit(app.exec())
    except Exception as e:
        logging.critical("Fatal crash in main execution block!", exc_info=True)
        raise

if __name__ == "__main__":
    main()
