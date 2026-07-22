import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from src.ui.main_window import VideoCutterApp
import src.core.metadata as metadata

def main():
    app = QApplication(sys.argv)
    metadata.FORCE_CAPS_LOCK_DEBUG = True
    
    win = VideoCutterApp()
    win.resize(1100, 700)
    
    # Configure info_overlay with SubWindow flags
    player = win.player_widget
    player.info_overlay.setParent(win)
    player.info_overlay.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
    player.info_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    player.info_overlay.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    
    win.show()
    
    # Load actual video if exists
    test_video = r"C:\Users\iseoh\OneDrive\카멜리아_20260712\1. Origin\GX010182.MP4"
    if os.path.exists(test_video):
        win.fileInput.setText(test_video)
        print("[TEST] Loaded real video:", test_video)
    else:
        player.has_video_loaded = True
        player.video_info = {
            'width': 1920, 'height': 1080, 'nickname': 'FHD (1080p)',
            'aspect_ratio': '16:9', 'fps': 30.0, 'duration': '00:00:20.87',
            'bitrate': '14500 kb/s', 'bit_depth': '8-bit', 'pix_fmt': 'yuv420p',
            'metadata': {'title': 'GX010182.MP4'}
        }
        player.video_path_cached = 'GX010182.MP4'
        player.update_hud()

    debug_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
    os.makedirs(debug_dir, exist_ok=True)
    snap_path = os.path.join(debug_dir, "subwindow_overlay_test.png")

    def capture():
        pixmap = win.grab()
        pixmap.save(snap_path)
        print(f"[TEST] Captured screenshot: {snap_path}")
        print(f"[TEST] Overlay flags: {player.info_overlay.windowFlags()}")
        print(f"[TEST] Overlay isVisible: {player.info_overlay.isVisible()}")
        app.quit()

    QTimer.singleShot(1000, capture)
    app.exec()

if __name__ == "__main__":
    main()
