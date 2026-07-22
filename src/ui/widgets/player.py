import os
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QPoint
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

from src.ui.widgets.timeline import TrimmingSliderWidget, ThumbnailGeneratorThread
from src.utils.time_utils import ms_to_time_str

class EmbeddedVideoPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(280)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        # 1. 상단 동영상 화면
        self.video_widget = QVideoWidget(self)
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.media_player.setVideoOutput(self.video_widget)
        main_layout.addWidget(self.video_widget, 1)

        # 2. 하단 100% 필름스트립 타임라인 슬라이더
        self.trimming_slider = TrimmingSliderWidget(self)
        self.trimming_slider.position_changed.connect(self.media_player.setPosition)
        main_layout.addWidget(self.trimming_slider, 0)

        # 3. 비디오 화면 위 마우스 호버 오버레이 패널
        self.overlay = QFrame(self.video_widget)
        self.overlay.setStyleSheet("QFrame { background-color: rgba(15, 20, 28, 0.75); border-radius: 8px; }")

        ov_layout = QVBoxLayout(self.overlay)
        ov_layout.setContentsMargins(10, 8, 10, 8)

        # 중앙 큰 재생/일시정지 버튼
        btn_box = QHBoxLayout()
        self.center_play_btn = QPushButton("▶")
        self.center_play_btn.setFixedSize(48, 48)
        self.center_play_btn.setStyleSheet("""
            QPushButton {
                font-size: 22px; color: white; background-color: rgba(0, 0, 0, 0.6);
                border: 2px solid rgba(255, 255, 255, 0.7); border-radius: 24px;
            }
            QPushButton:hover { background-color: rgba(0, 120, 215, 0.85); border-color: #0078d7; }
        """)
        self.center_play_btn.clicked.connect(self.toggle_play)
        btn_box.addStretch()
        btn_box.addWidget(self.center_play_btn)
        btn_box.addStretch()
        ov_layout.addLayout(btn_box)

        # 하단 컨트롤 바 (시간표시, 전체화면)
        bottom_box = QHBoxLayout()
        bottom_box.setSpacing(8)

        self.time_label = QLabel("00:00:00.00 / 00:00:00.00")
        self.time_label.setStyleSheet("color: white; font-weight: bold; font-family: Consolas, monospace; font-size: 13px; background: rgba(0,0,0,0.5); padding: 4px 8px; border-radius: 4px;")

        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setStyleSheet("QPushButton { color: white; background-color: #444; padding: 4px 8px; border-radius: 4px; font-size: 14px; } QPushButton:hover { background-color: #666; }")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        bottom_box.addWidget(self.time_label)
        bottom_box.addStretch()
        bottom_box.addWidget(self.fullscreen_btn)

        ov_layout.addLayout(bottom_box)

        # 시그널 연결
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)
        self.media_player.playbackStateChanged.connect(self.on_playback_state_changed)
        if hasattr(self.video_widget, 'videoSink') and self.video_widget.videoSink():
            self.video_widget.videoSink().videoSizeChanged.connect(self.update_video_aspect)

        # 오버레이 자동 숨김 타이머
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(2500)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_overlay)

        self.drag_start_pos = None

        # 동영상 정보 반투명 노란색 오버레이 HUD (Native DWM Top-Level Window로 Direct3D 덮임 완벽 방지)
        self.info_overlay = QLabel(self)
        self.info_overlay.setWindowFlags(
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.info_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.info_overlay.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.info_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.85);
                color: #ffeb3b;  /* 노란색 */
                border-radius: 6px;
                padding: 8px 12px;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid rgba(255, 235, 59, 0.4);
            }
        """)
        self.info_overlay.hide()

        self.video_info = None
        self.has_video_loaded = False
        self.video_path_cached = ""
        self._last_hud_text = ""
        self._last_hud_visible = False
        self._hud_false_counter = 0
        self.force_hud_visible = False  # 수동 강제 표시 플래그

        # Caps Lock 감지 및 HUD 갱신 타이머 (100ms)
        self.hud_timer = QTimer(self)
        self.hud_timer.setInterval(100)
        self.hud_timer.timeout.connect(self.update_hud)
        self.hud_timer.start()

    def update_video_aspect(self):
        pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        vw_w = self.video_widget.width()
        vw_h = self.video_widget.height()
        ov_h = 100
        self.overlay.setGeometry(10, vw_h - ov_h - 10, max(10, vw_w - 20), ov_h)
        self.overlay.raise_()
        if self._last_hud_visible and self.video_widget.isVisible():
            gpos = self.video_widget.mapToGlobal(QPoint(12, 12))
            self.info_overlay.move(gpos)
            self.info_overlay.raise_()

    def mouseMoveEvent(self, event):
        self.show_overlay()
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_start_pos is not None:
            top_win = self.window()
            if top_win and not top_win.isFullScreen():
                top_win.move(top_win.pos() + event.globalPosition().toPoint() - self.drag_start_pos)
                self.drag_start_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.show_overlay()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.toggle_fullscreen()
        super().mouseDoubleClickEvent(event)

    def show_overlay(self):
        self.overlay.show()
        self.hide_timer.start()

    def hide_overlay(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.overlay.hide()

    def step_time(self, delta_ms: int):
        if self.media_player.duration() > 0:
            pos = self.media_player.position() + delta_ms
            pos = max(0, min(self.media_player.duration(), pos))
            self.media_player.setPosition(pos)

    def step_frame(self, forward=True):
        if self.media_player.duration() > 0:
            frame_ms = 33  # ~30fps 1프레임
            pos = self.media_player.position()
            pos = pos + frame_ms if forward else pos - frame_ms
            pos = max(0, min(self.media_player.duration(), pos))
            self.media_player.setPosition(pos)

    def unload_video(self):
        self.media_player.stop()
        self.media_player.setSource(QUrl())
        self.has_video_loaded = False
        self.video_info = None
        self.video_path_cached = None
        if hasattr(self, 'info_overlay') and self.info_overlay:
            self.info_overlay.hide()
        if hasattr(self, 'trimming_slider') and self.trimming_slider:
            self.trimming_slider.set_duration(0)
            self.trimming_slider.set_cut_history_regions([])

    def load_video(self, file_path: str, auto_play=True):
        if file_path and os.path.isfile(file_path):
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            if auto_play:
                self.media_player.play()
            else:
                self.media_player.setPosition(0)
                self.media_player.pause()
            self.show_overlay()

            from src.core.metadata import get_detailed_video_info
            try:
                self.video_info = get_detailed_video_info(file_path)
                self.has_video_loaded = True
                self.video_path_cached = file_path
            except Exception as e:
                logging.error(f"Failed to load video properties: {e}")
                self.video_info = None
                self.has_video_loaded = False

            # 썸네일 필름스트립 스레드 시작
            if hasattr(self, 'thumb_thread') and self.thumb_thread and self.thumb_thread.isRunning():
                self.thumb_thread.terminate()
                self.thumb_thread.wait()

            self.trimming_slider.set_thumbnails([])
            self.thumb_thread = ThumbnailGeneratorThread(file_path, count=10, parent=self)
            self.thumb_thread.thumbnails_ready.connect(self.trimming_slider.set_thumbnail_files)
            self.thumb_thread.start()
            self.setFocus()

    def toggle_play(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
        self.show_overlay()
        self.setFocus()

    def on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.center_play_btn.setText("⏸")
        else:
            self.center_play_btn.setText("▶")
            self.overlay.show()
        self.setFocus()

    def set_position(self, position):
        self.media_player.setPosition(position)

    def on_position_changed(self, position_ms):
        self.trimming_slider.set_position(position_ms)
        dur_ms = self.media_player.duration()
        self.time_label.setText(f"{ms_to_time_str(position_ms)} / {ms_to_time_str(dur_ms)}")

    def on_duration_changed(self, duration_ms):
        self.trimming_slider.set_duration(duration_ms)
        pos_ms = self.media_player.position()
        self.time_label.setText(f"{ms_to_time_str(pos_ms)} / {ms_to_time_str(duration_ms)}")

    def toggle_fullscreen(self):
        w = self.window()
        if w:
            if w.isFullScreen():
                w.showNormal()
            else:
                w.showFullScreen()
        self.setFocus()

    def update_hud(self):
        from src.core.metadata import is_caps_lock_on
        raw_should = (is_caps_lock_on() or self.force_hud_visible) and self.has_video_loaded and bool(self.video_info)
        
        if raw_should:
            self._hud_false_counter = 0
        else:
            self._hud_false_counter += 1

        # 5틱(500ms) 연속으로 OFF 상태일 때만 실제 hide 처리 (순간 깜빡임 방지 디바운스)
        should_show = (self._hud_false_counter < 5) if self._last_hud_visible else raw_should

        # 메인 윈도우가 포커스를 잃었거나(다른 앱 선택) 최소화/숨김 상태면 HUD 즉시 숨김
        top_win = self.window()
        if top_win:
            if not top_win.isActiveWindow() or top_win.isMinimized() or not top_win.isVisible() or not self.isVisible():
                should_show = False
                self._hud_false_counter = 5  # 포커스 해제 시 디바운스 없이 즉시 끄기

        if should_show:
            pos_ms = self.media_player.position()
            fps = self.video_info.get("fps", 0.0)
            
            # 현재 초 + 프레임 계산
            if fps > 0:
                sec_part = (pos_ms % 1000) / 1000.0
                frame_idx = int(round(sec_part * fps))
                frame_str = f"+ {frame_idx:02d}f"
            else:
                frame_str = ""

            time_str = ms_to_time_str(pos_ms)
            
            # Ctrl 키가 눌렸을 때 추가 정보 확장
            ctrl_pressed = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
            
            text = (
                f"[ 동영상 상세 정보 ]\n"
                f"• 파일명: {os.path.basename(self.video_path_cached)}\n"
                f"• 해상도: {self.video_info['width']}x{self.video_info['height']} ({self.video_info['nickname']})\n"
                f"• 비율: {self.video_info['aspect_ratio']}\n"
                f"• 프레임: {self.video_info['fps']:.2f} fps\n"
                f"• 총길이: {self.video_info['duration']}\n"
                f"• 현재시각: {time_str} {frame_str}\n"
                f"• 데이터레이트: {self.video_info['bitrate']}\n"
                f"• 비트심도: {self.video_info['bit_depth']} ({self.video_info['pix_fmt']})"
            )
            
            if ctrl_pressed:
                meta_lines = []
                for k, v in self.video_info.get("metadata", {}).items():
                    if len(meta_lines) >= 10:
                        break
                    meta_lines.append(f"{k}: {v}")
                meta_str = "\n  ".join(meta_lines) if meta_lines else "None"
                text += f"\n• 메타데이터 (확장):\n  {meta_str}"
            else:
                text += f"\n\n[💡 Ctrl 키를 누르면 상세 메타데이터가 표시됩니다]"

            if text != self._last_hud_text:
                self.info_overlay.setText(text)
                self.info_overlay.adjustSize()
                self._last_hud_text = text

            gpos = self.video_widget.mapToGlobal(QPoint(12, 12))
            self.info_overlay.move(gpos)
            self.info_overlay.raise_()

            if not self._last_hud_visible:
                self.info_overlay.show()
                self.info_overlay.raise_()
                self._last_hud_visible = True
                logging.info(f"[HUD DIAGNOSTIC] DWM ToolTip HUD Showed at {gpos}")
                
                # 영구 보존 디렉토리에 5초간 연속 5회 타임랩스 스크린샷 기록
                try:
                    save_dirs = [
                        r"C:\git\mp4-trim\debug_screenshots",
                        os.path.expanduser(r"~/.mp4-trim/debug_screenshots")
                    ]
                    for d in save_dirs:
                        os.makedirs(d, exist_ok=True)
                    
                    def capture_step(seq_num, delay_ms):
                        try:
                            w = self.window()
                            if w:
                                px = w.grab()
                                for d in save_dirs:
                                    p = os.path.join(d, f"hud_seq_{seq_num}_{delay_ms}ms.png")
                                    px.save(p)
                                logging.info(f"[HUD DIAGNOSTIC] Saved sequential snapshot #{seq_num} ({delay_ms}ms)")
                        except Exception as err:
                            logging.error(f"[HUD DIAGNOSTIC] Capture step error: {err}")

                    for seq, delay in enumerate([100, 300, 600, 1000, 1500], 1):
                        QTimer.singleShot(delay, lambda s=seq, d=delay: capture_step(s, d))
                except Exception as e:
                    logging.error(f"[HUD DIAGNOSTIC] Sequential screenshot trigger error: {e}")
        else:
            if self._last_hud_visible:
                self.info_overlay.hide()
                self._last_hud_visible = False
                self._last_hud_text = ""
                logging.info(f"[HUD DIAGNOSTIC] HUD Hidden after debounce.")
