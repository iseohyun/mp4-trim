import sys
import os
import json
import subprocess
import ctypes
import re
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QGridLayout,
    QMessageBox,
    QCheckBox,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QHBoxLayout,
)
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtCore import Qt, QStandardPaths, pyqtSignal, QEvent
from PyQt6.QtGui import QIcon


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


def get_media_creation_time_and_duration(video_path: str):
    ffmpeg_bin = "ffmpeg.exe"
    if not os.path.exists(ffmpeg_bin):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ffmpeg_bin = os.path.join(base_path, "ffmpeg.exe")
    
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


class VideoCutterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.history_file = "trim_history.json"
        self.task_history_file = "task_history.json"
        self.task_histories = []
        self.create_history_flag = True
        self.is_loading_history = False
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

        self.initUI()
        self.load_history()
        self.load_task_history()

    def initUI(self):
        self.setWindowIcon(QIcon("dist/icon.ico"))
        self.setWindowTitle("초고속 무손실 영상 분할기")
        layout = QGridLayout()
        layout.setVerticalSpacing(10)

        # 1. 원본 파일 선택 영역 (행 0)
        layout.addWidget(QLabel("원본 파일"), 0, 0)
        self.fileInput = QLineEdit()
        self.fileInput.textChanged.connect(self.on_file_changed)
        layout.addWidget(self.fileInput, 0, 1)

        self.fileBtn = QPushButton("찾아보기")
        self.fileBtn.clicked.connect(self.openFileDialog)
        layout.addWidget(self.fileBtn, 0, 2)

        # 1-1. 원본 파일 액션 영역 (행 1)
        src_btn_layout = QHBoxLayout()
        self.playSrcBtn = QPushButton("재생")
        self.playSrcBtn.setEnabled(False)
        self.playSrcBtn.clicked.connect(self.play_source_video)
        src_btn_layout.addWidget(self.playSrcBtn)

        self.propertiesBtn = QPushButton("속성보기")
        self.propertiesBtn.setEnabled(False)
        self.propertiesBtn.clicked.connect(self.view_source_properties)
        src_btn_layout.addWidget(self.propertiesBtn)

        self.openSrcDirBtn = QPushButton("폴더 열기")
        self.openSrcDirBtn.setEnabled(False)
        self.openSrcDirBtn.clicked.connect(self.open_source_folder)
        src_btn_layout.addWidget(self.openSrcDirBtn)

        layout.addLayout(src_btn_layout, 1, 1, 1, 2)

        # 2. 시간 설정 영역 (커스텀 ArrowKey 라인 에디트) (행 2, 3)
        layout.addWidget(QLabel("시작"), 2, 0)
        self.startInput = ArrowKeyLineEdit("00:00:00.00")
        layout.addWidget(self.startInput, 2, 1, 1, 2)

        layout.addWidget(QLabel("종료"), 3, 0)
        self.endInput = ArrowKeyLineEdit("00:00:00.00")
        self.endInput.focused.connect(self.check_end_time_focus)
        layout.addWidget(self.endInput, 3, 1, 1, 2)
        self.startInput.next_line_edit = self.endInput
        self.endInput.prev_line_edit = self.startInput

        # 3. 저장 파일명 설정 영역 (행 4)
        layout.addWidget(QLabel("저장 파일명"), 4, 0)
        self.nameInput = QLineEdit("output.mp4")
        self.nameInput.textChanged.connect(self.update_output_play_btn_state)
        layout.addWidget(self.nameInput, 4, 1)

        self.playOutBtn = QPushButton("재생")
        self.playOutBtn.setToolTip("편집영상 재생하기")
        self.playOutBtn.setEnabled(False)
        self.playOutBtn.clicked.connect(self.play_output_video)
        layout.addWidget(self.playOutBtn, 4, 2)

        # 3-1. 옵션 영역 (행 5)
        layout.addWidget(QLabel("옵션"), 5, 0)
        options_layout = QHBoxLayout()
        self.muteCheck = QCheckBox("음소거 (영상만 가져오기)")
        self.copyMetaCheck = QCheckBox("속성 복사")
        self.copyMetaCheck.setChecked(True)
        self.autoNumberCheck = QCheckBox("자동 넘버링")
        self.autoNumberCheck.setChecked(True)
        options_layout.addWidget(self.muteCheck)
        options_layout.addWidget(self.copyMetaCheck)
        options_layout.addWidget(self.autoNumberCheck)
        layout.addLayout(options_layout, 5, 1, 1, 2)

        # 4. 저장 위치 라디오 그룹 (행 6)
        layout.addWidget(QLabel("저장 위치"), 6, 0)
        radio_layout = QHBoxLayout()
        self.radioSame = QRadioButton("동일 경로 (../)")
        self.radioOutput = QRadioButton("output 폴더 (../output/)")
        self.radioCustom = QRadioButton("사용자 지정 (custom)")

        self.radioGroup = QButtonGroup(self)
        self.radioGroup.addButton(self.radioSame)
        self.radioGroup.addButton(self.radioOutput)
        self.radioGroup.addButton(self.radioCustom)

        radio_layout.addWidget(self.radioSame)
        radio_layout.addWidget(self.radioOutput)
        radio_layout.addWidget(self.radioCustom)
        layout.addLayout(radio_layout, 6, 1, 1, 2)

        # 5. 저장 경로 설정 영역 (행 7)
        layout.addWidget(QLabel("저장 경로"), 7, 0)
        self.dirInput = QLineEdit()
        self.dirInput.textChanged.connect(self.update_output_play_btn_state)
        layout.addWidget(self.dirInput, 7, 1)
        self.dirBtn = QPushButton("위치 선택")
        self.dirBtn.clicked.connect(self.openDirDialog)
        layout.addWidget(self.dirBtn, 7, 2)

        # 6. 작업 히스토리 영역 (행 8)
        layout.addWidget(QLabel("작업 히스토리"), 8, 0)
        self.taskHistoryCombo = QComboBox()
        self.taskHistoryCombo.currentIndexChanged.connect(self.on_task_history_selected)
        layout.addWidget(self.taskHistoryCombo, 8, 1, 1, 2)

        # 6-1. 최근 작업 폴더 및 위치 열기 (행 9)
        layout.addWidget(QLabel("최근 작업 폴더"), 9, 0)
        self.historyCombo = QComboBox()
        self.historyCombo.currentIndexChanged.connect(self.on_history_combo_changed)
        layout.addWidget(self.historyCombo, 9, 1)

        self.openDirBtn = QPushButton("위치 열기")
        self.openDirBtn.clicked.connect(self.open_current_directory)
        layout.addWidget(self.openDirBtn, 9, 2)

        # 7. 실행 트리거 (행 10)
        self.runBtn = QPushButton("무손실 컷팅 실행")
        self.runBtn.setStyleSheet(
            "font-weight: bold; background-color: #2b579a; color: white; padding: 10px; margin-top: 10px;"
        )
        self.runBtn.clicked.connect(self.executeCutter)
        layout.addWidget(self.runBtn, 10, 0, 1, 3)

        self.setLayout(layout)

        # Radio buttons connections
        self.radioSame.toggled.connect(self.on_radio_changed)
        self.radioOutput.toggled.connect(self.on_radio_changed)
        self.radioCustom.toggled.connect(self.on_radio_changed)

        # Set default selection
        self.radioOutput.setChecked(True)

        # Connect widget modifications to history creation flag
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

    def get_active_working_dir(self):
        """현재 타겟 뼈대가 될 탐색기 기준 경로 연동 제어 함수"""
        if self.historyCombo.currentIndex() >= 0:
            current_path = self.historyCombo.currentText()
            if os.path.exists(current_path):
                return current_path
        return self.default_dir

    def openFileDialog(self):
        start_dir = self.get_active_working_dir()
        file, _ = QFileDialog.getOpenFileName(
            self, "비디오 파일 선택", start_dir, "Video Files (*.mp4 *.mkv *.mov)"
        )
        if file:
            self.fileInput.setText(file)

    def on_file_changed(self, text):
        self.update_output_dir()
        is_exist = os.path.isfile(text)
        self.playSrcBtn.setEnabled(is_exist)
        self.propertiesBtn.setEnabled(is_exist)
        self.openSrcDirBtn.setEnabled(is_exist)
        
        if is_exist:
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

    def play_source_video(self):
        video_path = self.fileInput.text()
        if video_path and os.path.isfile(video_path):
            try:
                os.startfile(video_path)
            except Exception as e:
                QMessageBox.critical(self, "에러", f"재생 실패:\n{str(e)}")
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
            try:
                os.startfile(output_file)
            except Exception as e:
                QMessageBox.critical(self, "에러", f"재생 실패:\n{str(e)}")
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

        ffmpeg_bin = "ffmpeg.exe"
        if not os.path.exists(ffmpeg_bin):
            base_path = getattr(
                sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))
            )
            ffmpeg_bin = os.path.join(base_path, "ffmpeg.exe")

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


if __name__ == "__main__":
    try:
        # 유저님의 고유 앱 ID 지정 (형식: 회사명.파일명.버전)
        myappid = "mycompany.mp4trimmer.cutter.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print("작업표시줄 아이콘 프로세스 등록 실패:", e)
    app = QApplication(sys.argv)
    ex = VideoCutterApp()
    ex.setWindowIcon(QIcon("dist/icon.ico"))
    ex.show()
    sys.exit(app.exec())
