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
    win.show()
    
    player = win.player_widget
    player.has_video_loaded = True
    player.video_info = {
        'width': 3840, 'height': 2160, 'nickname': 'UHD (4K)',
        'aspect_ratio': '16:9', 'fps': 59.94, 'duration': '00:00:20.87',
        'bitrate': '89587 kb/s', 'bit_depth': '8-bit', 'pix_fmt': 'yuvj420p',
        'metadata': {'title': 'GX010182.MP4', 'encoder': 'GoPro H.265 encoder'}
    }
    player.video_path_cached = 'GX010182.MP4'
    player.update_hud()

    debug_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
    os.makedirs(debug_dir, exist_ok=True)
    snap_path = os.path.join(debug_dir, "fixed_hud_result.png")

    def capture():
        pixmap = win.grab()
        pixmap.save(snap_path)
        print(f"[TEST] Captured screenshot: {snap_path}")
        print(f"[TEST] HUD parent: {player.info_overlay.parent().metaObject().className()}")
        print(f"[TEST] HUD isVisible: {player.info_overlay.isVisible()}")
        print(f"[TEST] HUD pos relative to video_widget: {player.info_overlay.pos()}")
        app.quit()

    QTimer.singleShot(500, capture)
    app.exec()

if __name__ == "__main__":
    main()
