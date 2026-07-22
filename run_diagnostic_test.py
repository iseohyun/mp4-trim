import sys
import os
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from src.ui.main_window import VideoCutterApp
import src.core.metadata as metadata

def main():
    app = QApplication(sys.argv)
    
    # 1. Force Caps Lock DEBUG state ON
    metadata.FORCE_CAPS_LOCK_DEBUG = True
    print("[DIAGNOSTIC] Forced Caps Lock ON for testing")
    
    win = VideoCutterApp()
    win.resize(1100, 700)
    win.show()
    
    # Simulate video info loaded
    player = win.player_widget
    player.has_video_loaded = True
    player.video_info = {
        'width': 1920,
        'height': 1080,
        'nickname': 'FHD (1080p)',
        'aspect_ratio': '16:9',
        'fps': 30.0,
        'duration': '00:02:15.00',
        'bitrate': '14500 kb/s',
        'bit_depth': '8-bit',
        'pix_fmt': 'yuv420p',
        'metadata': {'title': 'Sample Diagnostic Video', 'encoder': 'FFmpeg'}
    }
    player.video_path_cached = 'C:/git/mp4-trim/sample_test_video.mp4'
    
    # Update HUD
    player.update_hud()
    
    # Capture window screenshot after 500ms
    debug_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
    os.makedirs(debug_dir, exist_ok=True)
    snap_path = os.path.join(debug_dir, "hud_diagnostic_result.png")
    
    def on_timeout():
        pixmap = win.grab()
        pixmap.save(snap_path)
        print(f"[DIAGNOSTIC] Screenshot saved to: {snap_path}")
        print(f"[DIAGNOSTIC] HUD label visible: {player.info_overlay.isVisible()}")
        print(f"[DIAGNOSTIC] HUD label pos: {player.info_overlay.pos()}")
        print(f"[DIAGNOSTIC] HUD label geometry: {player.info_overlay.geometry()}")
        app.quit()
        
    QTimer.singleShot(500, on_timeout)
    app.exec()

if __name__ == "__main__":
    main()
