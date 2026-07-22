import sys
import os
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import Qt, QPoint, QTimer
from src.ui.main_window import VideoCutterApp
import src.core.metadata as metadata

def main():
    app = QApplication(sys.argv)
    metadata.FORCE_CAPS_LOCK_DEBUG = True
    
    win = VideoCutterApp()
    win.resize(1100, 700)
    win.show()
    
    # 1. Native DWM overlay window (ToolTip / FramelessWindowHint / WindowStaysOnTopHint)
    overlay = QLabel(win)
    overlay.setWindowFlags(
        Qt.WindowType.ToolTip |
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.WindowStaysOnTopHint
    )
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    overlay.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    overlay.setStyleSheet("""
        QLabel {
            background-color: rgba(0, 0, 0, 0.85);
            color: #ffeb3b;
            border-radius: 6px;
            padding: 8px 12px;
            font-family: Consolas, monospace;
            font-size: 11px;
            border: 1px solid rgba(255, 235, 59, 0.4);
        }
    """)
    
    text = (
        "[ 동영상 상세 정보 - DWM NATIVE OVERLAY ]\n"
        "• 파일명: GX010182.MP4\n"
        "• 해상도: 3840x2160 (UHD (4K))\n"
        "• 비율: 16:9\n"
        "• 프레임: 59.94 fps\n"
        "• 총길이: 00:00:20.87\n"
        "• 현재시각: 00:00:02.83 + 50f\n"
        "• 데이터레이트: 89587 kb/s\n"
        "• 비트심도: 8-bit (yuvj420p)"
    )
    overlay.setText(text)
    overlay.adjustSize()
    
    def update_overlay_pos():
        if win.isVisible() and win.player_widget.video_widget.isVisible():
            gpos = win.player_widget.video_widget.mapToGlobal(QPoint(12, 12))
            overlay.move(gpos)
            overlay.show()
            overlay.raise_()
            
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(update_overlay_pos)
    timer.start()
    
    print("[TEST] DWM Native Overlay running. Close window to exit.")
    app.exec()

if __name__ == "__main__":
    main()
