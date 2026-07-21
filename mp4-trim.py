import sys
import os
import shutil
import json
import subprocess
import ctypes
import re
import tempfile
import logging
import traceback
from datetime import datetime, timedelta

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(APP_DIR, "debug.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)
logging.info("=== MP4-Trim App Loaded ===")

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

sys.excepthook = custom_excepthook
from PyQt6.QtGui import QKeyEvent, QIcon, QPainter, QPixmap, QAction, QColor, QPen, QBrush, QKeySequence
from PyQt6.QtCore import Qt, QStandardPaths, pyqtSignal, QEvent, QTimer, QUrl, QThread, QRectF, QPropertyAnimation, QEasingCurve
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QCheckBox,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QSlider,
    QFrame,
    QSizePolicy,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyle,
    QStackedWidget,
    QScrollArea,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)


class ArrowKeyLineEdit(QLineEdit):
    """커서의 위치에 따라 시, 분, 초, 소수점 이하(단위)를 위/아래 화살표 키로 증감하는 커스텀 입력창"""
    focused = pyqtSignal()

    def __init__(self, contents, parent=None):
        super().__init__(contents, parent)
        self.setInputMask("00:00:00.00;0")
        self.setText(contents)
        self.max_val_cs = 35999999
        self.prev_line_edit = None
        self.next_line_edit = None
        self.last_field = -1
        self.digit_count = 0

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focused.emit()
        self.digit_count = 0
        self.last_field = -1
        
        reason = event.reason()
        if reason == Qt.FocusReason.TabFocusReason:
            self.setCursorPosition(0)
        elif reason == Qt.FocusReason.BacktabFocusReason:
            self.setCursorPosition(9)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        text = self.displayText()
        total_cs = self.time_to_centiseconds(text)
        if total_cs > self.max_val_cs:
            total_cs = self.max_val_cs
            self.setText(self.centiseconds_to_time(total_cs))

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Tab:
                cursor_pos = self.cursorPosition()
                if cursor_pos < 9:
                    self.keyPressEvent(event)
                    return True
            elif key == Qt.Key.Key_Backtab:
                cursor_pos = self.cursorPosition()
                if cursor_pos >= 3:
                    self.keyPressEvent(event)
                    return True
                if hasattr(self, 'prev_line_edit') and self.prev_line_edit:
                    self.keyPressEvent(event)
                    return True
        return super().event(event)

    def time_to_centiseconds(self, time_str: str) -> int:
        try:
            time_str = time_str.replace(' ', '0')
            parts = time_str.split(':')
            if len(parts) != 3:
                return 0
            hh = int(parts[0])
            mm = int(parts[1])
            
            ss_parts = parts[2].split('.')
            if len(ss_parts) != 2:
                return 0
            ss = int(ss_parts[0])
            cs = int(ss_parts[1])
            
            return (((hh * 60) + mm) * 60 + ss) * 100 + cs
        except ValueError:
            return 0

    def centiseconds_to_time(self, total_cs: int) -> str:
        if total_cs < 0:
            total_cs = 0
        cs = total_cs % 100
        total_seconds = total_cs // 100
        ss = total_seconds % 60
        total_minutes = total_seconds // 60
        mm = total_minutes % 60
        hh = total_minutes // 60
        return f"{hh:02d}:{mm:02d}:{ss:02d}.{cs:02d}"

    def get_field_info(self, cursor_pos: int):
        if 0 <= cursor_pos <= 2:
            return 0, 0, 2
        elif 3 <= cursor_pos <= 5:
            return 1, 3, 5
        elif 6 <= cursor_pos <= 8:
            return 2, 6, 8
        else:
            return 3, 9, 11

    def update_field_text(self, text: str, start_idx: int, new_val: str) -> str:
        return text[:start_idx] + new_val + text[start_idx+2:]

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            text = self.displayText()
            cursor_pos = self.cursorPosition()

            total_cs = self.time_to_centiseconds(text)

            # HH:MM:SS.CS (00:00:00.00)
            # HH -> 0, 1, 2
            # MM -> 3, 4, 5
            # SS -> 6, 7, 8
            # CS -> 9, 10, 11
            if 0 <= cursor_pos <= 2:
                delta = 360000  # 1 hour
            elif 3 <= cursor_pos <= 5:
                delta = 6000    # 1 minute
            elif 6 <= cursor_pos <= 8:
                delta = 100     # 1 second
            else:
                delta = 1       # 1 centisecond

            if key == Qt.Key.Key_Up:
                total_cs += delta
            else:
                total_cs -= delta

            if total_cs < 0:
                total_cs = self.max_val_cs
            elif total_cs > self.max_val_cs:
                total_cs = 0

            new_text = self.centiseconds_to_time(total_cs)
            self.setText(new_text)
            self.setCursorPosition(cursor_pos)
            event.accept()
        elif key == Qt.Key.Key_Right or key == Qt.Key.Key_Tab:
            cursor_pos = self.cursorPosition()
            if 0 <= cursor_pos <= 2:
                self.setCursorPosition(3)
            elif 3 <= cursor_pos <= 5:
                self.setCursorPosition(6)
            elif 6 <= cursor_pos <= 8:
                self.setCursorPosition(9)
            elif cursor_pos >= 9:
                if key == Qt.Key.Key_Tab:
                    super().keyPressEvent(event)
                else:
                    self.setCursorPosition(11)
            event.accept()
        elif key == Qt.Key.Key_Left or key == Qt.Key.Key_Backtab:
            cursor_pos = self.cursorPosition()
            if 9 <= cursor_pos <= 11:
                self.setCursorPosition(6)
            elif 6 <= cursor_pos <= 8:
                self.setCursorPosition(3)
            elif 3 <= cursor_pos <= 5:
                self.setCursorPosition(0)
            elif cursor_pos <= 2:
                if key == Qt.Key.Key_Backtab:
                    if hasattr(self, 'prev_line_edit') and self.prev_line_edit:
                        self.prev_line_edit.setFocus()
                        self.prev_line_edit.setCursorPosition(9)
                    else:
                        super().keyPressEvent(event)
                else:
                    self.setCursorPosition(0)
            event.accept()
        elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            digit_char = str(key - Qt.Key.Key_0)
            text = self.displayText()
            cursor_pos = self.cursorPosition()
            
            field_idx, start_idx, end_idx = self.get_field_info(cursor_pos)
            
            if field_idx != self.last_field:
                self.last_field = field_idx
                self.digit_count = 0
                
            if self.digit_count == 0:
                new_val = "0" + digit_char
                new_text = self.update_field_text(text, start_idx, new_val)
                self.setText(new_text)
                self.setCursorPosition(start_idx + 1)
                self.digit_count = 1
            else:
                prev_char = text[start_idx + 1]
                new_val = prev_char + digit_char
                new_text = self.update_field_text(text, start_idx, new_val)
                self.setText(new_text)
                
                # Auto-advance to the next field
                if field_idx == 0:
                    self.setCursorPosition(3)
                elif field_idx == 1:
                    self.setCursorPosition(6)
                elif field_idx == 2:
                    self.setCursorPosition(9)
                else:
                    self.setCursorPosition(11)
                self.digit_count = 0
                
            event.accept()
        else:
            super().keyPressEvent(event)


def get_unique_filename(file_path: str) -> str:
    if not os.path.exists(file_path):
        return file_path
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    name, ext = os.path.splitext(base_name)
    
    # Match trailing " (number)" at the end of the name
    match = re.search(r"\s+\((?P<num>\d+)\)$", name)
    if match:
        prefix = name[:match.start()]
        start_num = int(match.group('num'))
    else:
        prefix = name
        start_num = 1
        
    counter = start_num + 1
    while True:
        new_name = f"{prefix} ({counter}){ext}"
        new_path = os.path.join(dir_name, new_name).replace('\\', '/')
        if not os.path.exists(new_path):
            return new_path
        counter += 1


def show_file_properties(file_path: str):
    import ctypes.wintypes
    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD),
            ("fMask", ctypes.wintypes.ULONG),
            ("hwnd", ctypes.wintypes.HWND),
            ("lpVerb", ctypes.wintypes.LPCWSTR),
            ("lpFile", ctypes.wintypes.LPCWSTR),
            ("lpParameters", ctypes.wintypes.LPCWSTR),
            ("lpDirectory", ctypes.wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", ctypes.wintypes.LPCWSTR),
            ("hkeyClass", ctypes.wintypes.HKEY),
            ("dwHotKey", ctypes.wintypes.DWORD),
            ("hIconOrMonitor", ctypes.c_void_p),
            ("hProcess", ctypes.wintypes.HANDLE)
        ]

    SEE_MASK_INVOKEIDLIST = 0x0000000c
    SW_SHOW = 5
    
    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_INVOKEIDLIST
    sei.lpVerb = "properties"
    sei.lpFile = os.path.abspath(file_path)
    sei.nShow = SW_SHOW
    
    ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))


def open_source_file_dir(file_path: str):
    if file_path and os.path.isfile(file_path):
        try:
            # Highlight the file in Windows Explorer
            subprocess.run(['explorer', '/select,', os.path.normpath(file_path)], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print("Failed to open folder:", e)


def get_ffmpeg_path() -> str:
    """시스템 환경변수(PATH), 로컬/번들 디렉터리 순으로 ffmpeg 경로를 탐색합니다."""
    system_ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if system_ffmpeg:
        return system_ffmpeg

    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    local_ffmpeg = os.path.join(base_path, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    return "ffmpeg.exe"


def get_ffplay_path() -> str:
    """시스템 환경변수(PATH), 로컬/번들 디렉터리 순으로 ffplay 경로를 탐색합니다."""
    system_ffplay = shutil.which("ffplay") or shutil.which("ffplay.exe")
    if system_ffplay:
        return system_ffplay

    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    local_ffplay = os.path.join(base_path, "ffplay.exe")
    if os.path.exists(local_ffplay):
        return local_ffplay

    return "ffplay.exe"


def ms_to_time_str(ms: int) -> str:
    total_sec = ms // 1000
    cs = (ms % 1000) // 10
    hh = total_sec // 3600
    mm = (total_sec % 3600) // 60
    ss = total_sec % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{cs:02d}"


def get_media_creation_time_and_duration(video_path: str):
    ffmpeg_bin = get_ffmpeg_path()
    
    cmd = [ffmpeg_bin, "-i", video_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    output = res.stderr
    
    # Parse duration
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)(?:\.(\d+))?", output)
    duration_cs = 35999999
    if duration_match:
        hh = int(duration_match.group(1))
        mm = int(duration_match.group(2))
        ss = int(duration_match.group(3))
        cs_str = duration_match.group(4)
        if cs_str:
            cs = int(cs_str.ljust(2, '0')[:2])
        else:
            cs = 0
        duration_cs = (((hh * 60) + mm) * 60 + ss) * 100 + cs
        
    # Parse creation_time metadata
    creation_match = re.search(r"creation_time\s*:\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?[Z]?)", output, re.IGNORECASE)
    creation_dt = None
    if creation_match:
        time_str = creation_match.group(1)
        # Parse ISO formats
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
            try:
                clean_str = time_str
                if clean_str.endswith('Z'):
                    clean_str = clean_str[:-1]
                if '.' in clean_str:
                    parts = clean_str.split('.')
                    clean_str = parts[0] + '.' + parts[1][:6]
                creation_dt = datetime.fromisoformat(clean_str)
                break
            except ValueError:
                continue
                
    if not creation_dt:
        try:
            ctime = os.path.getctime(video_path)
            creation_dt = datetime.fromtimestamp(ctime)
        except:
            creation_dt = datetime.now()
            
    return duration_cs, creation_dt


class FilmstripWidget(QWidget):
    """동영상 재생 바 배경에 그려지는 대표 씬 썸네일 스트립"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.pixmaps = []
        self.setStyleSheet("background-color: #111; border-radius: 4px;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_thumbnail_files(self, paths):
        pixmaps = []
        for p in paths:
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    pixmaps.append(pm)
        self.pixmaps = pixmaps
        self.update()

    def set_thumbnails(self, pixmaps):
        self.pixmaps = pixmaps
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        if not self.pixmaps:
            painter.setPen(Qt.GlobalColor.darkGray)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "썸네일 바 로딩 중...")
            return

        n = len(self.pixmaps)
        w = float(self.width()) / float(n)
        h = float(self.height())

        for i, pm in enumerate(self.pixmaps):
            rect = QRectF(i * w, 0, w, h)
            scaled = pm.scaled(int(w), int(h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(rect.toRect(), scaled)


class ThumbnailGeneratorThread(QThread):
    """FFmpeg를 이용하여 동영상의 주요 씬 썸네일을 비동기로 생성하는 스레드"""
    thumbnails_ready = pyqtSignal(list)

    def __init__(self, video_path: str, count: int = 10, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.count = count

    def run(self):
        try:
            logging.info(f"[ThumbThread] Target video: {self.video_path}")
            duration_cs, _ = get_media_creation_time_and_duration(self.video_path)
            duration_sec = duration_cs / 100.0
            logging.info(f"[ThumbThread] Duration: {duration_sec}s")
            if duration_sec <= 0:
                logging.warning("[ThumbThread] Invalid duration_sec <= 0")
                return

            ffmpeg_bin = get_ffmpeg_path()
            logging.info(f"[ThumbThread] Using ffmpeg_bin: {ffmpeg_bin}")
            temp_dir = os.path.join(tempfile.gettempdir(), "mp4_trim_thumbs")
            os.makedirs(temp_dir, exist_ok=True)

            paths = []
            interval = max(0.5, duration_sec / float(self.count))
            vid_hash = abs(hash(self.video_path)) % 100000
            for i in range(self.count):
                seek_time = i * interval
                out_path = os.path.join(temp_dir, f"thumb_{vid_hash}_{i}.jpg")
                cmd = [
                    ffmpeg_bin, "-ss", f"{seek_time:.2f}",
                    "-i", self.video_path, "-vframes", "1",
                    "-s", "120x68", "-y", out_path
                ]
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    paths.append(out_path)
                else:
                    err = res.stderr.decode('utf-8', 'ignore') if res.stderr else "file empty"
                    logging.warning(f"[ThumbThread] Frame {i} failed: {err}")

            logging.info(f"[ThumbThread] Extracted {len(paths)} / {self.count} thumbnails")
            if paths:
                self.thumbnails_ready.emit(paths)
        except Exception as e:
            logging.error(f"[ThumbThread] Exception: {e}", exc_info=True)


class JumpSlider(QSlider):
    """클릭한 위치로 타임스탬프가 즉시 이동하는 슬라이더"""
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            val = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(event.position().x()), self.width()
            )
            self.setValue(val)
            self.sliderMoved.emit(val)
        super().mousePressEvent(event)


class TrimmingSliderWidget(QWidget):
    """
    100% 비디오 플레이어 너비에 맞춰 표시되는 필름스트립 타임라인 바.
    - 10개 대표 씬 썸네일 타일링
    - 선택 구간 [Start, End] 밝게 표시 / 구간 밖은 반투명 어둡게 표시
    - 1px 녹색 편집점 시작/종료 세로선 (전체 높이)
    - 1px 빨간색 현재 재생 시점 세로선 (전체 높이)
    - 마커 클릭 선택 후 좌우 화살표키(← / →) 미세 조작 지원
    - 마우스 드래그로 시작점/종료점/재생 헤드 자유 이동
    """
    position_changed = pyqtSignal(int)   # ms
    start_changed = pyqtSignal(int)      # ms
    end_changed = pyqtSignal(int)        # ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.pixmaps = []

        self.duration_ms = 1000
        self.position_ms = 0
        self.start_ms = 0
        self.end_ms = 1000

        self.active_marker = None     # 'start', 'end', 'playhead'
        self.dragging_marker = None

    def set_thumbnail_files(self, paths):
        pixmaps = []
        for p in paths:
            if os.path.exists(p):
                pm = QPixmap(p)
                if not pm.isNull():
                    pixmaps.append(pm)
        self.pixmaps = pixmaps
        self.update()

    def set_thumbnails(self, pixmaps):
        self.pixmaps = pixmaps
        self.update()

    def set_duration(self, dur_ms: int):
        if dur_ms > 0:
            old_dur = self.duration_ms
            self.duration_ms = dur_ms
            if self.end_ms == old_dur or self.end_ms > dur_ms or self.end_ms == 0:
                self.end_ms = dur_ms
            self.update()

    def set_position(self, pos_ms: int):
        self.position_ms = max(0, min(self.duration_ms, pos_ms))
        self.update()

    def set_start_ms(self, start_ms: int):
        val = max(0, min(self.end_ms, start_ms))
        if self.start_ms != val:
            self.start_ms = val
            self.update()

    def set_end_ms(self, end_ms: int):
        val = max(self.start_ms, min(self.duration_ms, end_ms))
        if self.end_ms != val:
            self.end_ms = val
            self.update()

    def ms_to_x(self, ms: int) -> float:
        if self.duration_ms <= 0:
            return 0.0
        return (ms / float(self.duration_ms)) * float(self.width())

    def x_to_ms(self, x: float) -> int:
        if self.width() <= 0:
            return 0
        ratio = max(0.0, min(1.0, x / float(self.width())))
        return int(ratio * self.duration_ms)

    def paintEvent(self, event):
        super().paintEvent(event)
        w = float(self.width())
        h = float(self.height())
        if w <= 0 or h <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 0. 배경 썸네일 타일링 그리기
        if self.pixmaps:
            n = len(self.pixmaps)
            tw = w / float(n)
            for i, pm in enumerate(self.pixmaps):
                rect = QRectF(i * tw, 0, tw, h)
                scaled = pm.scaled(int(tw), int(h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                painter.drawPixmap(rect.toRect(), scaled)
        else:
            painter.fillRect(QRectF(0, 0, w, h), QColor(17, 17, 17))
            painter.setPen(QColor(128, 128, 128))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "썸네일 로딩 중...")

        sx = self.ms_to_x(self.start_ms)
        ex = self.ms_to_x(self.end_ms)
        px = self.ms_to_x(self.position_ms)

        # 1. 선택 영역 밖 (0 ~ start_ms, end_ms ~ duration_ms) 반투명 블랙 딤(Dim) 처리
        dim_color = QColor(0, 0, 0, 160)
        if sx > 0:
            painter.fillRect(QRectF(0, 0, sx, h), dim_color)
        if ex < w:
            painter.fillRect(QRectF(ex, 0, w - ex, h), dim_color)

        # 2. 선택된 유효 구간 [start_ms, end_ms] 테두리 강조
        border_pen = QPen(QColor(0, 120, 215, 220), 1)
        painter.setPen(border_pen)
        painter.drawRect(QRectF(sx, 1, max(1.0, ex - sx), h - 2))

        # 3. 편집점 시작 마커 (재생바 전체 높이 1px 녹색 세로선)
        start_color = QColor(0, 230, 118) if self.active_marker == 'start' else QColor(0, 200, 83)
        painter.setPen(QPen(start_color, 1))
        painter.drawLine(int(sx), 0, int(sx), int(h))

        # 4. 편집점 종료 마커 (재생바 전체 높이 1px 녹색 세로선)
        end_color = QColor(0, 230, 118) if self.active_marker == 'end' else QColor(0, 200, 83)
        painter.setPen(QPen(end_color, 1))
        painter.drawLine(int(ex), 0, int(ex), int(h))

        # 5. 현재 재생 헤드 (재생바 전체 높이 1px 빨간색 세로선)
        playhead_color = QColor(255, 59, 48)
        painter.setPen(QPen(playhead_color, 1))
        painter.drawLine(int(px), 0, int(px), int(h))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            sx = self.ms_to_x(self.start_ms)
            ex = self.ms_to_x(self.end_ms)
            px = self.ms_to_x(self.position_ms)

            # 재생 중에 재생바를 클릭/조작 시 일시 정지
            if hasattr(self.parent(), 'media_player') and self.parent().media_player:
                if self.parent().media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self.parent().media_player.pause()

            if abs(x - sx) <= 10:
                self.active_marker = 'start'
                self.dragging_marker = 'start'
            elif abs(x - ex) <= 10:
                self.active_marker = 'end'
                self.dragging_marker = 'end'
            elif abs(x - px) <= 8:
                self.active_marker = 'playhead'
                self.dragging_marker = 'playhead'
            else:
                self.active_marker = 'playhead'
                self.dragging_marker = 'playhead'
                new_ms = self.x_to_ms(x)
                self.position_ms = new_ms
                self.position_changed.emit(new_ms)
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.setFocus()
            self.update()

    def mouseMoveEvent(self, event):
        x = event.position().x()
        sx = self.ms_to_x(self.start_ms)
        ex = self.ms_to_x(self.end_ms)
        px = self.ms_to_x(self.position_ms)

        if self.dragging_marker:
            # 드래그 중 재생 일시 정지
            if hasattr(self.parent(), 'media_player') and self.parent().media_player:
                if self.parent().media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    self.parent().media_player.pause()
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            new_ms = self.x_to_ms(x)
            if self.dragging_marker == 'start':
                self.start_ms = max(0, min(self.end_ms, new_ms))
                self.start_changed.emit(self.start_ms)
            elif self.dragging_marker == 'end':
                self.end_ms = max(self.start_ms, min(self.duration_ms, new_ms))
                self.end_changed.emit(self.end_ms)
            elif self.dragging_marker == 'playhead':
                self.position_ms = new_ms
                self.position_changed.emit(self.position_ms)
            self.update()
        else:
            if abs(x - sx) <= 10 or abs(x - ex) <= 10 or abs(x - px) <= 8:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.dragging_marker = None
        x = event.position().x()
        sx = self.ms_to_x(self.start_ms)
        ex = self.ms_to_x(self.end_ms)
        px = self.ms_to_x(self.position_ms)
        if abs(x - sx) <= 10 or abs(x - ex) <= 10 or abs(x - px) <= 8:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def leaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        step_ms = 1000  # 1초 기본 이동
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step_ms = 5000  # Shift: 5초
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step_ms = 100   # Ctrl: 0.1초

        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            delta = step_ms if event.key() == Qt.Key.Key_Right else -step_ms
            if self.active_marker == 'start':
                self.start_ms = max(0, min(self.end_ms, self.start_ms + delta))
                self.start_changed.emit(self.start_ms)
            elif self.active_marker == 'end':
                self.end_ms = max(self.start_ms, min(self.duration_ms, self.end_ms + delta))
                self.end_changed.emit(self.end_ms)
            else:
                self.position_ms = max(0, min(self.duration_ms, self.position_ms + delta))
                self.position_changed.emit(self.position_ms)
            self.update()
        else:
            super().keyPressEvent(event)

class EmbeddedVideoPlayer(QWidget):
    """내장 미디어 플레이어 위젯 (상단 비디오, 하단 100% 타임라인 바, 호버 오버레이 컨트롤)"""

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

    def update_video_aspect(self):
        pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        vw_w = self.video_widget.width()
        vw_h = self.video_widget.height()
        ov_h = 100
        self.overlay.setGeometry(10, vw_h - ov_h - 10, max(10, vw_w - 20), ov_h)
        self.overlay.raise_()

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

    def load_video(self, file_path: str, auto_play=True):
        if file_path and os.path.isfile(file_path):
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            if auto_play:
                self.media_player.play()
            self.show_overlay()

            # 썸네일 필름스트립 스레드 시작
            if hasattr(self, 'thumb_thread') and self.thumb_thread and self.thumb_thread.isRunning():
                self.thumb_thread.terminate()
                self.thumb_thread.wait()

            self.trimming_slider.set_thumbnails([])
            self.thumb_thread = ThumbnailGeneratorThread(file_path, count=10, parent=self)
            self.thumb_thread.thumbnails_ready.connect(self.trimming_slider.set_thumbnail_files)
            self.thumb_thread.start()

    def toggle_play(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
        self.show_overlay()

    def on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.center_play_btn.setText("⏸")
        else:
            self.center_play_btn.setText("▶")
            self.overlay.show()

    def set_position(self, position):
        self.media_player.setPosition(position)

    def on_position_changed(self, position_ms):
        self.trimming_slider.set_position(position_ms)
        dur_ms = self.media_player.duration()
        self.time_label.setText(f"{self.ms_to_time_str(position_ms)} / {self.ms_to_time_str(dur_ms)}")

    def on_duration_changed(self, duration_ms):
        self.trimming_slider.set_duration(duration_ms)
        pos_ms = self.media_player.position()
        self.time_label.setText(f"{self.ms_to_time_str(pos_ms)} / {self.ms_to_time_str(duration_ms)}")

    def ms_to_time_str(self, ms: int) -> str:
        total_sec = ms // 1000
        cs = (ms % 1000) // 10
        hh = total_sec // 3600
        mm = (total_sec % 3600) // 60
        ss = total_sec % 60
        return f"{hh:02d}:{mm:02d}:{ss:02d}.{cs:02d}"

    def on_set_start(self):
        pos_ms = self.media_player.position()
        self.set_start_requested.emit(self.ms_to_time_str(pos_ms))

    def on_set_end(self):
        pos_ms = self.media_player.position()
        self.set_end_requested.emit(self.ms_to_time_str(pos_ms))

    def toggle_fullscreen(self):
        w = self.window()
        if w:
            if w.isFullScreen():
                w.showNormal()
            else:
                w.showFullScreen()


DEFAULT_HOTKEYS = {
    "toggle_option": {"name": "옵션 패널 토글", "primary": "[", "secondary": ""},
    "toggle_playlist": {"name": "재생목록 토글", "primary": "]", "secondary": ""},
    "play_pause": {"name": "재생 / 일시정지", "primary": "Space", "secondary": "K"},
    "step_1s_prev": {"name": "1초 뒤로 이동", "primary": "Left", "secondary": "J"},
    "step_1s_next": {"name": "1초 앞으로 이동", "primary": "Right", "secondary": "L"},
    "step_5s_prev": {"name": "5초 뒤로 이동", "primary": "Shift+Left", "secondary": ""},
    "step_5s_next": {"name": "5초 앞으로 이동", "primary": "Shift+Right", "secondary": ""},
    "step_frame_prev": {"name": "1프레임 뒤로 이동", "primary": "Ctrl+Left", "secondary": ""},
    "step_frame_next": {"name": "1프레임 앞으로 이동", "primary": "Ctrl+Right", "secondary": ""},
    "toggle_fullscreen": {"name": "전체화면 토글", "primary": "F", "secondary": "F11"},
    "exit_fullscreen": {"name": "전체화면 해제", "primary": "Esc", "secondary": ""},
    "show_properties": {"name": "동영상 정보 보기", "primary": "?", "secondary": ""},
    "delete_playlist_item": {"name": "재생목록 항목 삭제", "primary": "Delete", "secondary": ""},
}

def event_to_key_str(event: QKeyEvent) -> str:
    key = event.key()
    if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return ""
    mods = event.modifiers()
    parts = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append("Ctrl")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("Shift")
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("Alt")

    if key == Qt.Key.Key_Left:
        k = "Left"
    elif key == Qt.Key.Key_Right:
        k = "Right"
    elif key == Qt.Key.Key_Up:
        k = "Up"
    elif key == Qt.Key.Key_Down:
        k = "Down"
    elif key == Qt.Key.Key_Space:
        k = "Space"
    elif key == Qt.Key.Key_BracketLeft:
        k = "["
    elif key == Qt.Key.Key_BracketRight:
        k = "]"
    elif key == Qt.Key.Key_Question or (key == Qt.Key.Key_Slash and (mods & Qt.KeyboardModifier.ShiftModifier)):
        k = "?"
    elif key == Qt.Key.Key_Delete:
        k = "Delete"
    elif key == Qt.Key.Key_Escape:
        k = "Esc"
    else:
        k = QKeySequence(key).toString().upper()

    if not parts or (parts == ["Shift"] and k == "?"):
        if k == "?":
            parts = []

    parts.append(k)
    return "+".join(parts)


class KeyCaptureDialog(QDialog):
    """새로운 단축키 조합을 감지하고 저장하는 대화상자"""
    def __init__(self, action_name: str, key_type: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단축키 지정")
        self.setFixedSize(320, 140)
        self.captured_key_str = None

        layout = QVBoxLayout(self)
        label = QLabel(f"<b>{action_name}</b> ({key_type})<br><br>사용할 단축키 조합을 누르세요...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        btn_box = QHBoxLayout()
        self.clear_btn = QPushButton("지우기 (해제)")
        self.cancel_btn = QPushButton("취소")
        self.clear_btn.clicked.connect(self.on_clear)
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.clear_btn)
        btn_box.addWidget(self.cancel_btn)
        layout.addLayout(btn_box)

    def on_clear(self):
        self.captured_key_str = ""
        self.accept()

    def keyPressEvent(self, event: QKeyEvent):
        key_str = event_to_key_str(event)
        if key_str:
            self.captured_key_str = key_str
            self.accept()
        else:
            super().keyPressEvent(event)


class VideoCutterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.history_file = os.path.join(APP_DIR, "trim_history.json")
        self.task_history_file = os.path.join(APP_DIR, "task_history.json")
        self.task_histories = []
        self.create_history_flag = True
        self.is_loading_history = False
        self.is_loading_file = False
        self.last_enter_name = ""
        self.original_duration_cs = 35999999
        self.original_creation_dt = None
        # 기본 경로 설정 (시스템 비디오 폴더 -> 없을 시 홈 폴더)
        self.default_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MoviesLocation
        )
        if not self.default_dir:
            self.default_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.HomeLocation
            )

        self.load_hotkeys()
        self.initUI()
        self.load_history()
        self.load_task_history()
        self.load_playlist_history()

        if len(sys.argv) > 1:
            initial_file = sys.argv[1].strip('"\'')
            if os.path.isfile(initial_file):
                self.fileInput.setText(initial_file)
                QTimer.singleShot(300, lambda: self.player_widget.load_video(initial_file, auto_play=True))

    def load_hotkeys(self):
        self.hotkeys_file = os.path.join(APP_DIR, "hotkeys.json")
        import copy
        self.hotkeys = copy.deepcopy(DEFAULT_HOTKEYS)
        if os.path.exists(self.hotkeys_file):
            try:
                with open(self.hotkeys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if k in self.hotkeys and isinstance(v, dict):
                                self.hotkeys[k]["primary"] = v.get("primary", self.hotkeys[k]["primary"])
                                self.hotkeys[k]["secondary"] = v.get("secondary", self.hotkeys[k]["secondary"])
            except Exception as e:
                logging.error(f"Failed to load hotkeys: {e}")

    def save_hotkeys(self):
        try:
            with open(self.hotkeys_file, "w", encoding="utf-8") as f:
                json.dump(self.hotkeys, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save hotkeys: {e}")

    def initUI(self):
        self.setWindowIcon(QIcon("dist/icon.ico"))
        self.setWindowTitle("초고속 무손실 영상 분할기 v1.0.5")
        self.setAcceptDrops(True)

        screen = QApplication.primaryScreen()
        if screen:
            rect = screen.availableGeometry()
            w = max(850, rect.width() // 2)
            h = max(600, rect.height() // 2)
            x = rect.x() + (rect.width() - w) // 2
            y = rect.y() + (rect.height() - h) // 2
            self.setGeometry(x, y, w, h)
        else:
            self.resize(850, 600)
        self.setMinimumSize(700, 480)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # 1. 좌측 옵션 사이드바 패널
        self.option_sidebar = QFrame()
        self.option_sidebar.setMinimumWidth(0)
        self.option_sidebar.setMaximumWidth(270)
        self.option_sidebar.setStyleSheet("""
            QFrame { background-color: #252526; border-radius: 6px; }
            QLabel { color: white; font-weight: bold; }
            QLineEdit { background-color: #1e1e1e; color: white; border: 1px solid #333; border-radius: 4px; padding: 4px; }
            QComboBox { background-color: #1e1e1e; color: white; border: 1px solid #333; border-radius: 4px; padding: 4px; }
            QCheckBox, QRadioButton { color: #dcdcdc; }
            QPushButton { background-color: #3e3e42; color: white; border-radius: 4px; padding: 4px 8px; }
            QPushButton:hover { background-color: #0078d7; }
        """)

        opt_sidebar_layout = QVBoxLayout(self.option_sidebar)
        opt_sidebar_layout.setContentsMargins(4, 4, 4, 4)

        self.option_stack = QStackedWidget()
        opt_sidebar_layout.addWidget(self.option_stack)

        # Page 0: 메인 옵션 설정 페이지
        opt_main_page = QWidget()
        opt_layout = QVBoxLayout(opt_main_page)
        opt_layout.setContentsMargins(6, 6, 6, 6)
        opt_layout.setSpacing(8)

        opt_header = QHBoxLayout()
        opt_title = QLabel("옵션 & 설정 (단축키: [)")
        opt_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2d89ef;")
        
        self.hotkey_btn = QPushButton("⌨")
        self.hotkey_btn.setToolTip("단축키 안내 / 설정")
        self.hotkey_btn.setFixedSize(26, 26)
        self.hotkey_btn.setStyleSheet("""
            QPushButton { background-color: #333; color: white; border-radius: 4px; font-size: 14px; font-weight: bold; border: 1px solid #444; padding: 0; }
            QPushButton:hover { background-color: #0078d7; border-color: #0078d7; }
        """)
        self.hotkey_btn.clicked.connect(lambda: self.option_stack.setCurrentIndex(1))

        opt_header.addWidget(opt_title, 1)
        opt_header.addWidget(self.hotkey_btn, 0)
        opt_layout.addLayout(opt_header)

        # 1-1. 저장 파일명
        name_box = QHBoxLayout()
        self.nameInput = QLineEdit("output.mp4")
        self.nameInput.textChanged.connect(self.update_output_play_btn_state)
        self.nameInput.returnPressed.connect(self.on_name_input_enter)
        self.nameInput.textChanged.connect(self.update_name_input_style)
        self.playOutBtn = QPushButton("재생")
        self.playOutBtn.setToolTip("편집영상 재생하기")
        self.playOutBtn.setEnabled(False)
        self.playOutBtn.clicked.connect(self.play_output_video)
        name_box.addWidget(self.nameInput, 1)
        name_box.addWidget(self.playOutBtn, 0)

        opt_layout.addWidget(QLabel("저장 파일명"))
        opt_layout.addLayout(name_box)

        # 1-2. 저장 옵션
        self.muteCheck = QCheckBox("음소거 (영상만 가져오기)")
        self.copyMetaCheck = QCheckBox("속성 복사")
        self.copyMetaCheck.setChecked(True)
        self.autoNumberCheck = QCheckBox("자동 넘버링")
        self.autoNumberCheck.setChecked(True)
        opt_layout.addWidget(self.muteCheck)
        opt_layout.addWidget(self.copyMetaCheck)
        opt_layout.addWidget(self.autoNumberCheck)

        # 1-3. 저장 위치
        opt_layout.addWidget(QLabel("저장 위치"))
        self.radioSame = QRadioButton("동일 경로 (../)")
        self.radioOutput = QRadioButton("output 폴더 (../output/)")
        self.radioCustom = QRadioButton("사용자 지정 (custom)")
        self.radioGroup = QButtonGroup(self)
        self.radioGroup.addButton(self.radioSame)
        self.radioGroup.addButton(self.radioOutput)
        self.radioGroup.addButton(self.radioCustom)
        opt_layout.addWidget(self.radioSame)
        opt_layout.addWidget(self.radioOutput)
        opt_layout.addWidget(self.radioCustom)

        dir_box = QHBoxLayout()
        self.dirInput = QLineEdit()
        self.dirInput.textChanged.connect(self.update_output_play_btn_state)
        self.dirBtn = QPushButton("선택")
        self.dirBtn.clicked.connect(self.openDirDialog)
        dir_box.addWidget(self.dirInput, 1)
        dir_box.addWidget(self.dirBtn, 0)
        opt_layout.addWidget(QLabel("저장 경로"))
        opt_layout.addLayout(dir_box)

        # 1-4. 작업 히스토리 및 최근 작업 폴더
        opt_layout.addWidget(QLabel("작업 히스토리"))
        self.taskHistoryCombo = QComboBox()
        self.taskHistoryCombo.currentIndexChanged.connect(self.on_task_history_selected)
        opt_layout.addWidget(self.taskHistoryCombo)

        opt_layout.addWidget(QLabel("최근 작업 폴더"))
        hist_box = QHBoxLayout()
        self.historyCombo = QComboBox()
        self.historyCombo.currentIndexChanged.connect(self.on_history_combo_changed)
        self.openDirBtn = QPushButton("열기")
        self.openDirBtn.clicked.connect(self.open_current_directory)
        hist_box.addWidget(self.historyCombo, 1)
        hist_box.addWidget(self.openDirBtn, 0)
        opt_layout.addLayout(hist_box)

        opt_layout.addStretch()

        # 1-5. 무손실 컷팅 실행 버튼
        self.runBtn = QPushButton("무손실 컷팅 실행")
        self.runBtn.setStyleSheet("font-weight: bold; background-color: #2b579a; color: white; padding: 10px; border-radius: 4px;")
        self.runBtn.clicked.connect(self.executeCutter)
        opt_layout.addWidget(self.runBtn)

        # Page 1: 단축키 설정 페이지
        opt_hotkey_page = self.build_hotkey_settings_page()

        self.option_stack.addWidget(opt_main_page)
        self.option_stack.addWidget(opt_hotkey_page)

        # 2. 중앙 메인 플레이어 영역
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self.player_widget = EmbeddedVideoPlayer(self)
        center_layout.addWidget(self.player_widget, 1)

        # 숨김 입력 필드 유지
        self.fileInput = QLineEdit()
        self.fileInput.textChanged.connect(self.on_file_changed)
        self.startInput = ArrowKeyLineEdit("00:00:00.00")
        self.endInput = ArrowKeyLineEdit("00:00:00.00")

        self.player_widget.trimming_slider.start_changed.connect(self.on_trim_start_changed)
        self.player_widget.trimming_slider.end_changed.connect(self.on_trim_end_changed)
        self.startInput.textChanged.connect(self.on_start_input_text_changed)
        self.endInput.textChanged.connect(self.on_end_input_text_changed)

        # 3. 우측 재생 목록 사이드바 패널
        self.playlist_files = []
        self.playlist_sidebar = QFrame()
        self.playlist_sidebar.setMinimumWidth(0)
        self.playlist_sidebar.setMaximumWidth(240)
        self.playlist_sidebar.setStyleSheet("""
            QFrame { background-color: #252526; border-radius: 6px; }
            QLabel { color: white; font-weight: bold; }
            QListWidget { background-color: #1e1e1e; color: #dcdcdc; border: 1px solid #333; border-radius: 4px; }
            QListWidget::item { padding: 3px 5px; margin: 0px; border-bottom: 1px solid #2a2a2a; font-size: 12px; }
            QListWidget::item:hover { background-color: #2a2d32; }
            QListWidget::item:selected { background-color: #0078d7; color: white; }
        """)

        sidebar_layout = QVBoxLayout(self.playlist_sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)

        sb_header = QHBoxLayout()
        sb_title = QLabel("재생 목록 (단축키: ])")
        self.add_file_btn = QPushButton("+ 추가")
        self.add_file_btn.setStyleSheet("background-color: #2d89ef; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;")
        self.add_file_btn.clicked.connect(self.openFileDialog)
        sb_header.addWidget(sb_title)
        sb_header.addStretch()
        sb_header.addWidget(self.add_file_btn)
        sidebar_layout.addLayout(sb_header)

        self.playlist_widget = QListWidget()
        self.playlist_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.on_playlist_context_menu)
        self.playlist_widget.itemDoubleClicked.connect(self.on_playlist_item_double_clicked)
        sidebar_layout.addWidget(self.playlist_widget)

        root_layout.addWidget(self.option_sidebar, 0)
        root_layout.addWidget(center_container, 1)
        root_layout.addWidget(self.playlist_sidebar, 0)

        # Radio buttons connections
        self.radioSame.toggled.connect(self.on_radio_changed)
        self.radioOutput.toggled.connect(self.on_radio_changed)
        self.radioCustom.toggled.connect(self.on_radio_changed)

        self.radioOutput.setChecked(True)

        self.fileInput.textChanged.connect(self.on_input_modified)
        self.startInput.textChanged.connect(self.on_input_modified)
        self.endInput.textChanged.connect(self.on_input_modified)
        self.nameInput.textChanged.connect(self.on_input_modified)
        self.dirInput.textChanged.connect(self.on_input_modified)
        self.muteCheck.stateChanged.connect(self.on_input_modified)
        self.copyMetaCheck.stateChanged.connect(self.on_input_modified)
        self.autoNumberCheck.stateChanged.connect(self.on_input_modified)
        self.radioSame.toggled.connect(self.on_input_modified)
        self.radioOutput.toggled.connect(self.on_input_modified)
        self.radioCustom.toggled.connect(self.on_input_modified)

    def build_hotkey_settings_page(self):
        opt_hotkey_page = QWidget()
        hk_layout = QVBoxLayout(opt_hotkey_page)
        hk_layout.setContentsMargins(6, 6, 6, 6)
        hk_layout.setSpacing(6)

        hk_header = QHBoxLayout()
        self.hk_back_btn = QPushButton("← 뒤로")
        self.hk_back_btn.setStyleSheet("""
            QPushButton { background-color: #383838; color: white; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }
            QPushButton:hover { background-color: #0078d7; }
        """)
        self.hk_back_btn.clicked.connect(lambda: self.option_stack.setCurrentIndex(0))

        hk_title = QLabel("단축키 설정")
        hk_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #2d89ef;")

        self.hk_reset_btn = QPushButton("초기화")
        self.hk_reset_btn.setStyleSheet("""
            QPushButton { background-color: #552222; color: white; border-radius: 4px; padding: 3px 6px; font-size: 11px; }
            QPushButton:hover { background-color: #d13438; }
        """)
        self.hk_reset_btn.clicked.connect(self.reset_hotkeys_to_default)

        hk_header.addWidget(self.hk_back_btn, 0)
        hk_header.addStretch()
        hk_header.addWidget(hk_title, 0)
        hk_header.addStretch()
        hk_header.addWidget(self.hk_reset_btn, 0)
        hk_layout.addLayout(hk_header)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        self.hotkey_list_layout = QVBoxLayout(scroll_content)
        self.hotkey_list_layout.setContentsMargins(0, 0, 0, 0)
        self.hotkey_list_layout.setSpacing(4)

        scroll_area.setWidget(scroll_content)
        hk_layout.addWidget(scroll_area, 1)

        self.refresh_hotkey_table()
        return opt_hotkey_page

    def refresh_hotkey_table(self):
        while self.hotkey_list_layout.count():
            child = self.hotkey_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for action_id, info in self.hotkeys.items():
            row_frame = QFrame()
            row_frame.setStyleSheet("QFrame { background-color: #1e1e1e; border-radius: 4px; }")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(4)

            name_lbl = QLabel(info['name'])
            name_lbl.setStyleSheet("font-size: 11px; color: #dcdcdc; font-weight: normal;")
            row_layout.addWidget(name_lbl, 1)

            btn_p = QPushButton(info['primary'] if info['primary'] else "None")
            btn_p.setFixedWidth(55)
            btn_p.setToolTip("기본 단축키 변경")
            btn_p.setStyleSheet("""
                QPushButton { background-color: #333; color: #2d89ef; border: 1px solid #444; border-radius: 3px; font-size: 10px; font-weight: bold; padding: 2px; }
                QPushButton:hover { background-color: #0078d7; color: white; }
            """)
            btn_p.clicked.connect(lambda _, a=action_id, t='primary': self.change_hotkey(a, t))

            btn_s = QPushButton(info['secondary'] if info['secondary'] else "None")
            btn_s.setFixedWidth(55)
            btn_s.setToolTip("보조 단축키 변경")
            btn_s.setStyleSheet("""
                QPushButton { background-color: #333; color: #888; border: 1px solid #444; border-radius: 3px; font-size: 10px; padding: 2px; }
                QPushButton:hover { background-color: #0078d7; color: white; }
            """)
            btn_s.clicked.connect(lambda _, a=action_id, t='secondary': self.change_hotkey(a, t))

            row_layout.addWidget(btn_p, 0)
            row_layout.addWidget(btn_s, 0)

            self.hotkey_list_layout.addWidget(row_frame)

        self.hotkey_list_layout.addStretch()

    def change_hotkey(self, action_id: str, key_type: str):
        action_name = self.hotkeys[action_id]['name']
        type_str = "기본" if key_type == "primary" else "보조"
        dlg = KeyCaptureDialog(action_name, type_str, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.captured_key_str is not None:
            self.hotkeys[action_id][key_type] = dlg.captured_key_str
            self.save_hotkeys()
            self.refresh_hotkey_table()

    def reset_hotkeys_to_default(self):
        res = QMessageBox.question(
            self, "확인", "모든 단축키를 초기 설정으로 복원하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            import copy
            self.hotkeys = copy.deepcopy(DEFAULT_HOTKEYS)
            self.save_hotkeys()
            self.refresh_hotkey_table()

    def get_active_working_dir(self):
        """현재 타겟 뼈대가 될 탐색기 기준 경로 연동 제어 함수"""
        if self.historyCombo.currentIndex() >= 0:
            current_path = self.historyCombo.currentText()
            if os.path.exists(current_path):
                return current_path
        return self.default_dir

    def on_trim_start_changed(self, ms: int):
        new_str = ms_to_time_str(ms)
        if self.startInput.displayText() != new_str:
            self.startInput.blockSignals(True)
            self.startInput.setText(new_str)
            self.startInput.blockSignals(False)

    def on_trim_end_changed(self, ms: int):
        new_str = ms_to_time_str(ms)
        if self.endInput.displayText() != new_str:
            self.endInput.blockSignals(True)
            self.endInput.setText(new_str)
            self.endInput.blockSignals(False)

    def on_start_input_text_changed(self, txt: str):
        ms = self.startInput.time_to_centiseconds(txt) * 10
        if self.player_widget.trimming_slider.start_ms != ms:
            self.player_widget.trimming_slider.set_start_ms(ms)

    def on_end_input_text_changed(self, txt: str):
        ms = self.endInput.time_to_centiseconds(txt) * 10
        if self.player_widget.trimming_slider.end_ms != ms:
            self.player_widget.trimming_slider.set_end_ms(ms)

    def animate_sidebar(self, widget: QFrame, target_width: int):
        if hasattr(widget, '_anim') and widget._anim:
            try:
                if widget._anim.state() == QPropertyAnimation.State.Running:
                    widget._anim.stop()
            except RuntimeError:
                pass
            widget._anim = None

        is_closing = widget.isVisible() and widget.width() > 10

        anim = QPropertyAnimation(widget, b"maximumWidth", self)
        widget._anim = anim
        anim.setDuration(220)

        if is_closing:
            anim.setStartValue(widget.width())
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.Type.InQuad)
            def on_closed():
                widget.setVisible(False)
                widget.setMaximumWidth(target_width)
                widget._anim = None
            anim.finished.connect(on_closed)
        else:
            widget.setVisible(True)
            anim.setStartValue(widget.width() if widget.width() < target_width else 0)
            anim.setEndValue(target_width)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            def on_opened():
                widget.setMaximumWidth(target_width)
                widget._anim = None
            anim.finished.connect(on_opened)

        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def toggle_option_sidebar(self):
        self.animate_sidebar(self.option_sidebar, target_width=270)

    def toggle_playlist_sidebar(self):
        self.animate_sidebar(self.playlist_sidebar, target_width=240)

    def load_playlist_history(self):
        history_path = os.path.join(APP_DIR, "playlist_history.json")
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    saved_paths = json.load(f)
                    if isinstance(saved_paths, list):
                        self.playlist_files = []
                        self.playlist_widget.clear()
                        for path in saved_paths:
                            if isinstance(path, str):
                                norm_p = path.replace('\\', '/')
                                if os.path.isfile(norm_p):
                                    self.add_file_to_playlist(norm_p, load_immediately=False, save_history=False)
                        self.save_playlist_history()
            except Exception as e:
                logging.error(f"Failed to load playlist history: {e}")

    def save_playlist_history(self):
        history_path = os.path.join(APP_DIR, "playlist_history.json")
        try:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(self.playlist_files, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save playlist history: {e}")

    def add_file_to_playlist(self, file_path: str, load_immediately=True, save_history=True):
        file_path = file_path.replace('\\', '/')
        if file_path and os.path.isfile(file_path):
            if file_path not in self.playlist_files:
                self.playlist_files.append(file_path)
                item = QListWidgetItem(os.path.basename(file_path))
                item.setToolTip(file_path)
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                self.playlist_widget.addItem(item)
            
            for i in range(self.playlist_widget.count()):
                it = self.playlist_widget.item(i)
                if it.data(Qt.ItemDataRole.UserRole) == file_path:
                    self.playlist_widget.setCurrentItem(it)
                    break

            if save_history:
                self.save_playlist_history()

            if load_immediately:
                self.fileInput.setText(file_path)

    def remove_selected_playlist_item(self):
        item = self.playlist_widget.currentItem()
        if item:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            row = self.playlist_widget.row(item)
            self.playlist_widget.takeItem(row)
            if file_path in self.playlist_files:
                self.playlist_files.remove(file_path)
                self.save_playlist_history()

    def clear_playlist(self):
        self.playlist_widget.clear()
        self.playlist_files.clear()
        self.save_playlist_history()

    def on_playlist_item_double_clicked(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path and os.path.isfile(file_path):
            self.fileInput.setText(file_path)
            self.player_widget.load_video(file_path, auto_play=True)

    def on_playlist_context_menu(self, pos):
        item = self.playlist_widget.itemAt(pos)
        menu = QMenu(self)

        if item:
            file_path = item.data(Qt.ItemDataRole.UserRole)

            open_folder_act = QAction("폴더 열기", menu)
            open_folder_act.triggered.connect(lambda: open_source_file_dir(file_path))

            props_act = QAction("속성 보기 (단축키: ?)", menu)
            props_act.triggered.connect(lambda: show_file_properties(file_path))

            remove_act = QAction("목록에서 제거 (Del)", menu)
            remove_act.triggered.connect(self.remove_selected_playlist_item)

            menu.addAction(open_folder_act)
            menu.addAction(props_act)
            menu.addSeparator()
            menu.addAction(remove_act)

        clear_all_act = QAction("전체 목록 비우기", menu)
        clear_all_act.triggered.connect(self.clear_playlist)
        menu.addAction(clear_all_act)

        menu.exec(self.playlist_widget.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        first = None
        for u in urls:
            f = u.toLocalFile()
            if os.path.isfile(f) and f.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.webm')):
                self.add_file_to_playlist(f, load_immediately=False)
                if not first:
                    first = f
        if first:
            self.fileInput.setText(first)

    def openFileDialog(self):
        start_dir = self.get_active_working_dir()
        files, _ = QFileDialog.getOpenFileNames(
            self, "비디오 파일 선택", start_dir, "Video Files (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if files:
            for f in files:
                self.add_file_to_playlist(f, load_immediately=False)
            self.fileInput.setText(files[0])

    def on_file_changed(self, text):
        self.is_loading_file = True
        try:
            self.update_output_dir()
            is_exist = os.path.isfile(text)
            if is_exist:
                self.add_file_to_playlist(text, load_immediately=False)
                self.player_widget.load_video(text, auto_play=False)
                self.save_history(os.path.dirname(text))
                try:
                    duration_cs, creation_dt = get_media_creation_time_and_duration(text)
                    self.original_duration_cs = duration_cs
                    self.original_creation_dt = creation_dt
                    
                    # Update inputs max limits
                    self.startInput.max_val_cs = duration_cs
                    self.endInput.max_val_cs = duration_cs
                    
                    # Get current start and end times
                    start_cs = self.startInput.time_to_centiseconds(self.startInput.displayText())
                    end_cs = self.endInput.time_to_centiseconds(self.endInput.displayText())
                    
                    # Check bounds
                    if start_cs > duration_cs:
                        start_cs = duration_cs
                    if end_cs > duration_cs or end_cs == 0:
                        end_cs = duration_cs
                    
                    self.startInput.setText(self.startInput.centiseconds_to_time(start_cs))
                    self.endInput.setText(self.endInput.centiseconds_to_time(end_cs))
                except Exception as e:
                    import traceback
                    error_msg = traceback.format_exc()
                    print("Error parsing media:", error_msg)
                    QMessageBox.warning(
                        self,
                        "미디어 정보 분석 실패",
                        f"동영상 정보(재생 시간)를 가져오지 못했습니다.\n기본 제한 시간(99:59:59.99)이 적용됩니다.\n\n상세 에러:\n{str(e)}"
                    )
                    self.original_duration_cs = 35999999
                    self.original_creation_dt = None
                    self.startInput.max_val_cs = 35999999
                    self.endInput.max_val_cs = 35999999
            else:
                self.original_duration_cs = 35999999
                self.original_creation_dt = None
                self.startInput.max_val_cs = 35999999
                self.endInput.max_val_cs = 35999999
        finally:
            self.is_loading_file = False

    def openDirDialog(self):
        start_dir = self.get_active_working_dir()
        directory = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", start_dir)
        if directory:
            self.dirInput.setText(directory.replace('\\', '/'))

    def open_current_directory(self):
        """[위치 열기] 폴더 유재성 검증 및 OS 탐색기 호출 아키텍처"""
        target_dir = self.dirInput.text()
        if not target_dir or not os.path.exists(os.path.normpath(target_dir)):
            target_dir = self.get_active_working_dir()
            
        normalized_dir = os.path.normpath(target_dir) if target_dir else ""
        if not normalized_dir or not os.path.exists(normalized_dir):
            QMessageBox.warning(
                self, "경고", "지정된 저장 위치 경로가 하드디스크에 실재하지 않습니다."
            )
            return
        try:
            os.startfile(normalized_dir)
        except Exception as e:
            QMessageBox.critical(self, "에러", f"폴더 열기 실패:\n{str(e)}")

    def adjust_time_input(self, line_edit: ArrowKeyLineEdit, delta_sec: float):
        current_cs = line_edit.time_to_centiseconds(line_edit.displayText())
        new_cs = max(0, min(line_edit.max_val_cs, current_cs + int(delta_sec * 100)))
        line_edit.setText(line_edit.centiseconds_to_time(new_cs))

    def play_source_video(self):
        video_path = self.fileInput.text()
        if video_path and os.path.isfile(video_path):
            self.player_widget.load_video(video_path, auto_play=True)
            start_cs = self.startInput.time_to_centiseconds(self.startInput.displayText())
            if start_cs > 0:
                self.player_widget.set_position(start_cs * 10)
        else:
            QMessageBox.warning(self, "경고", "올바른 원본 파일이 선택되지 않았습니다.")

    def view_source_properties(self):
        video_path = self.fileInput.text()
        if video_path and os.path.isfile(video_path):
            show_file_properties(video_path)
        else:
            QMessageBox.warning(self, "경고", "올바른 원본 파일이 선택되지 않았습니다.")

    def open_source_folder(self):
        video_path = self.fileInput.text()
        if video_path and os.path.isfile(video_path):
            open_source_file_dir(video_path)
        else:
            QMessageBox.warning(self, "경고", "올바른 원본 파일이 선택되지 않았습니다.")

    def play_output_video(self):
        out_dir = self.dirInput.text()
        out_name = self.nameInput.text()
        output_file = os.path.join(out_dir, out_name)
        if output_file and os.path.isfile(output_file):
            self.player_widget.load_video(output_file, auto_play=True)
        else:
            QMessageBox.warning(self, "경고", "편집 영상 파일이 존재하지 않습니다.")

    def update_output_play_btn_state(self):
        out_dir = self.dirInput.text()
        out_name = self.nameInput.text()
        if out_dir and out_name:
            output_file = os.path.join(out_dir, out_name)
            is_exist = os.path.isfile(output_file)
        else:
            is_exist = False
        self.playOutBtn.setEnabled(is_exist)

    def update_output_dir(self):
        source_file = self.fileInput.text()
        if self.radioSame.isChecked():
            if source_file:
                self.dirInput.setText(os.path.dirname(source_file).replace('\\', '/'))
            else:
                self.dirInput.setText("")
        elif self.radioOutput.isChecked():
            if source_file:
                self.dirInput.setText(os.path.join(os.path.dirname(source_file), "output").replace('\\', '/'))
            else:
                self.dirInput.setText("")
        elif self.radioCustom.isChecked():
            if not self.dirInput.text():
                self.dirInput.setText(self.get_active_working_dir().replace('\\', '/'))
        self.update_output_play_btn_state()

    def on_radio_changed(self):
        is_custom = self.radioCustom.isChecked()
        self.dirInput.setEnabled(is_custom)
        self.dirBtn.setEnabled(is_custom)
        
        if is_custom:
            self.dirInput.setText(self.get_active_working_dir().replace('\\', '/'))
        else:
            self.update_output_dir()
        self.update_output_play_btn_state()

    def on_history_combo_changed(self, index):
        if self.is_loading_file:
            return
        if self.radioCustom.isChecked() and index >= 0:
            self.dirInput.setText(self.historyCombo.currentText().replace('\\', '/'))

    def check_end_time_focus(self):
        start_cs = self.startInput.time_to_centiseconds(self.startInput.displayText())
        end_cs = self.endInput.time_to_centiseconds(self.endInput.displayText())
        if start_cs > end_cs:
            self.endInput.setText(self.startInput.displayText())

    def executeCutter(self):
        video_in = self.fileInput.text()
        start_time = self.startInput.displayText()
        end_time = self.endInput.displayText()
        out_name = self.nameInput.text().strip()
        if not out_name.lower().endswith(".mp4"):
            out_name += ".mp4"
            self.nameInput.setText(out_name)
        out_dir = self.dirInput.text()

        if not video_in or not out_dir:
            QMessageBox.warning(
                self, "경고", "파일 경로 및 저장 위치를 모두 지정하십시오."
            )
            return

        # Ensure directory exists before execution
        os.makedirs(out_dir, exist_ok=True)

        video_out = os.path.join(out_dir, out_name).replace('\\', '/')
        if self.autoNumberCheck.isChecked():
            video_out = get_unique_filename(video_out)
            self.nameInput.setText(os.path.basename(video_out))

        ffmpeg_bin = get_ffmpeg_path()

        # Build command options
        cmd = [
            ffmpeg_bin,
            "-ss",
            start_time,
            "-to",
            end_time,
            "-i",
            video_in,
        ]

        if self.muteCheck.isChecked():
            cmd.extend(["-c:v", "copy", "-an"])
        else:
            cmd.extend(["-c:v", "copy", "-c:a", "copy"])

        if self.copyMetaCheck.isChecked():
            cmd.append("-map_metadata")
            cmd.append("0")
            if self.original_creation_dt:
                start_cs = self.startInput.time_to_centiseconds(start_time)
                offset_secs = start_cs / 100.0
                new_creation_dt = self.original_creation_dt + timedelta(seconds=offset_secs)
                new_creation_str = new_creation_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                cmd.append("-metadata")
                cmd.append(f"creation_time={new_creation_str}")
        else:
            cmd.append("-map_metadata")
            cmd.append("-1")

        cmd.extend(["-y", video_out])

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            QMessageBox.information(
                self,
                "완료",
                f"분할 완료",
            )
            if self.create_history_flag:
                self.add_task_history()
            self.update_output_play_btn_state()
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "에러", f"FFmpeg 분할 실패:\n{e.stderr}")

    def save_history(self, path):
        path = path.replace('\\', '/')
        history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = [p.replace('\\', '/') for p in json.load(f)]
            except:
                pass
        if path in history:
            history.remove(path)
        history.insert(0, path)
        history = history[:5]
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            self.refresh_history_combo(history)
        except:
            pass

    def load_history(self):
        history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = [p.replace('\\', '/') for p in json.load(f)]
            except:
                pass
        self.refresh_history_combo(history)

    def refresh_history_combo(self, history):
        self.historyCombo.clear()
        
        # Normalize history items to forward slashes to prevent duplicate mismatch
        history = [p.replace('\\', '/') for p in history]
        unique_history = []
        for p in history:
            if p not in unique_history:
                unique_history.append(p)
                
        self.historyCombo.addItems(unique_history)
        
        default_normalized = self.default_dir.replace('\\', '/')
        if default_normalized not in unique_history:
            self.historyCombo.addItem(default_normalized)
            
        if self.historyCombo.count() > 0:
            self.historyCombo.setCurrentIndex(0)

    def load_task_history(self):
        self.task_histories = []
        if os.path.exists(self.task_history_file):
            try:
                with open(self.task_history_file, "r", encoding="utf-8") as f:
                    self.task_histories = json.load(f)
            except:
                pass
        self.refresh_task_history_combo()

    def refresh_task_history_combo(self):
        self.taskHistoryCombo.blockSignals(True)
        self.taskHistoryCombo.clear()
        self.taskHistoryCombo.addItem("작업 히스토리 선택...")
        for task in self.task_histories:
            self.taskHistoryCombo.addItem(task['name'])
        self.taskHistoryCombo.blockSignals(False)

    def on_task_history_selected(self, index):
        if index <= 0:
            return
        task = self.task_histories[index - 1]
        
        self.is_loading_history = True
        
        self.fileInput.setText(task['video_in'])
        self.startInput.setText(task['start_time'])
        self.endInput.setText(task['end_time'])
        self.nameInput.setText(task['out_name'])
        self.muteCheck.setChecked(task['mute'])
        self.copyMetaCheck.setChecked(task['copy_meta'])
        self.autoNumberCheck.setChecked(task['auto_number'])
        
        radio_state = task.get('radio_state', 'custom')
        if radio_state == 'same':
            self.radioSame.setChecked(True)
        elif radio_state == 'output':
            self.radioOutput.setChecked(True)
        else:
            self.radioCustom.setChecked(True)
            
        self.dirInput.setText(task['out_dir'])
        
        self.create_history_flag = False
        self.is_loading_history = False

    def add_task_history(self):
        video_in = self.fileInput.text()
        start_time = self.startInput.displayText()
        end_time = self.endInput.displayText()
        out_name = self.nameInput.text()
        out_dir = self.dirInput.text()
        
        if self.radioSame.isChecked():
            radio_state = "same"
        elif self.radioOutput.isChecked():
            radio_state = "output"
        else:
            radio_state = "custom"
            
        base_video = os.path.basename(video_in)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        history_name = f"{base_video}_{start_time}_{timestamp}"
        
        task = {
            "name": history_name,
            "video_in": video_in,
            "start_time": start_time,
            "end_time": end_time,
            "out_name": out_name,
            "mute": self.muteCheck.isChecked(),
            "copy_meta": self.copyMetaCheck.isChecked(),
            "auto_number": self.autoNumberCheck.isChecked(),
            "out_dir": out_dir,
            "radio_state": radio_state
        }
        
        # Deduplicate tasks
        self.task_histories = [
            t for t in self.task_histories 
            if not (t['video_in'] == video_in and t['start_time'] == start_time and t['end_time'] == end_time and t['out_name'] == out_name and t['out_dir'] == out_dir)
        ]
        
        self.task_histories.insert(0, task)
        self.task_histories = self.task_histories[:50]
        
        try:
            with open(self.task_history_file, "w", encoding="utf-8") as f:
                json.dump(self.task_histories, f, ensure_ascii=False, indent=2)
            self.refresh_task_history_combo()
        except Exception as e:
            print("Failed to save task history:", e)

    def on_input_modified(self):
        if not self.is_loading_history:
            self.create_history_flag = True

    def on_name_input_enter(self):
        current_name = self.nameInput.text()
        if not current_name:
            return
            
        if self.last_enter_name and current_name == self.last_enter_name:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("확인")
            msg_box.setText("무손실컷팅실행을 수행할까요?")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
            msg_box.button(QMessageBox.StandardButton.Ok).setText("확인")
            msg_box.button(QMessageBox.StandardButton.Cancel).setText("취소")
            msg_box.button(QMessageBox.StandardButton.Ok).setFocus()
            
            result = msg_box.exec()
            if result == QMessageBox.StandardButton.Ok:
                self.executeCutter()
            else:
                self.nameInput.setFocus()
        else:
            self.last_enter_name = current_name
            self.update_name_input_style()

    def update_name_input_style(self):
        current_name = self.nameInput.text()
        if self.last_enter_name and current_name == self.last_enter_name:
            self.nameInput.setStyleSheet("border: 1px solid red;")
        else:
            self.nameInput.setStyleSheet("")

    def keyPressEvent(self, event: QKeyEvent):
        focus_w = QApplication.focusWidget()
        is_editing_text = isinstance(focus_w, QLineEdit)

        key_str = event_to_key_str(event)
        if not key_str:
            super().keyPressEvent(event)
            return

        matched_action = None
        for action_id, info in self.hotkeys.items():
            p = info.get("primary", "")
            s = info.get("secondary", "")
            if (p and p.upper() == key_str.upper()) or (s and s.upper() == key_str.upper()):
                matched_action = action_id
                break

        if not matched_action:
            super().keyPressEvent(event)
            return

        if is_editing_text and matched_action not in ("exit_fullscreen", "toggle_fullscreen"):
            super().keyPressEvent(event)
            return

        if matched_action == "toggle_option":
            self.toggle_option_sidebar()
        elif matched_action == "toggle_playlist":
            self.toggle_playlist_sidebar()
        elif matched_action == "play_pause":
            self.player_widget.toggle_play()
        elif matched_action == "step_1s_prev":
            self.player_widget.step_time(-1000)
        elif matched_action == "step_1s_next":
            self.player_widget.step_time(1000)
        elif matched_action == "step_5s_prev":
            self.player_widget.step_time(-5000)
        elif matched_action == "step_5s_next":
            self.player_widget.step_time(5000)
        elif matched_action == "step_frame_prev":
            self.player_widget.step_frame(forward=False)
        elif matched_action == "step_frame_next":
            self.player_widget.step_frame(forward=True)
        elif matched_action == "toggle_fullscreen":
            self.player_widget.toggle_fullscreen()
        elif matched_action == "exit_fullscreen":
            if self.isFullScreen():
                self.showNormal()
        elif matched_action == "show_properties":
            self.view_source_properties()
        elif matched_action == "delete_playlist_item":
            self.remove_selected_playlist_item()
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
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
