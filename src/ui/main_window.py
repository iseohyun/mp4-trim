import sys
import os
import json
import subprocess
import copy
import logging
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QRadioButton, QButtonGroup, QComboBox, QFrame, QStackedWidget,
    QListWidget, QListWidgetItem, QMenu, QFileDialog, QMessageBox, QScrollArea,
    QApplication, QStyledItemDelegate, QStyle
)
from PyQt6.QtCore import Qt, QStandardPaths, QTimer, QPropertyAnimation, QEasingCurve, QObject, QEvent, QSize
from PyQt6.QtGui import QIcon, QKeySequence, QKeyEvent, QAction, QColor, QPen

from src.utils.logger import APP_DIR
from src.utils.time_utils import ms_to_time_str
from src.core.metadata import (
    get_ffmpeg_path, get_unique_filename, show_file_properties,
    open_source_file_dir, get_media_creation_time_and_duration
)
from src.core.hotkeys import DEFAULT_HOTKEYS, event_to_key_str
from src.ui.widgets.line_edit import ArrowKeyLineEdit
from src.ui.widgets.player import EmbeddedVideoPlayer
from src.ui.dialogs.key_capture import KeyCaptureDialog


def get_user_data_path(file_name: str) -> str:
    appdata = os.environ.get('APPDATA')
    if appdata:
        dir_path = os.path.join(appdata, "MP4-Trim")
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, file_name)
    return os.path.join(APP_DIR, file_name)

def save_app_data_json(file_name: str, data):
    paths = [get_user_data_path(file_name), os.path.join(APP_DIR, file_name)]
    for p in paths:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save JSON to {p}: {e}")

def load_app_data_json(file_name: str):
    paths = [get_user_data_path(file_name), os.path.join(APP_DIR, file_name)]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load JSON from {p}: {e}")
    return None


class FocusOutFilter(QObject):
    def __init__(self, target_widget, parent=None):
        super().__init__(parent)
        self.target_widget = target_widget

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(50, self.check_focus)
        return super().eventFilter(obj, event)

    def check_focus(self):
        from PyQt6.QtWidgets import QLineEdit, QComboBox, QListWidget, QTableWidget
        focus_w = QApplication.focusWidget()
        if focus_w is None or (not isinstance(focus_w, (QLineEdit, QComboBox, QListWidget, QTableWidget))
                               and not focus_w.inherits("QLineEdit")
                               and not focus_w.inherits("QComboBox")
                               and not focus_w.inherits("QListWidget")
                               and not focus_w.inherits("QTableWidget")):
            if self.target_widget:
                self.target_widget.setFocus()


class PlaylistDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect
        
        bg_brush = index.data(Qt.ItemDataRole.BackgroundRole)
        fg_brush = index.data(Qt.ItemDataRole.ForegroundRole)
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        
        if is_selected:
            # 현재 선택된 파일: 파란색 배경 + 흰색 글씨
            painter.fillRect(rect, QColor('#0078d7'))
            painter.setPen(QColor('#ffffff'))
        elif bg_brush:
            # 컷팅 히스토리가 있는 파일: 노란색 단계별 배경 + 지정된 글씨색(흰색)
            painter.fillRect(rect, bg_brush.color())
            painter.setPen(fg_brush.color() if fg_brush else QColor('#ffffff'))
        else:
            # 기본 파일: 어두운 배경 + 흰색 글씨
            painter.fillRect(rect, QColor('#1e1e1e'))
            painter.setPen(QColor('#ffffff'))
            
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        text_rect = rect.adjusted(8, 0, -8, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        
        # 하단 구분선
        painter.setPen(QPen(QColor('#282828'), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        
        painter.restore()


class CustomPlaylistListWidget(QListWidget):
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete:
            main_win = self.window()
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if hasattr(main_win, 'delete_selected_playlist_file_permanently'):
                    main_win.delete_selected_playlist_file_permanently()
                    return
            else:
                if hasattr(main_win, 'remove_selected_playlist_item'):
                    main_win.remove_selected_playlist_item()
                    return
        super().keyPressEvent(event)


class VideoCutterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.task_histories = []
        self.create_history_flag = True
        self.is_loading_history = False
        self.is_loading_file = False
        self.is_loading_file = False
        self.last_enter_name = ""
        self.original_duration_cs = 35999999
        self.original_creation_dt = None
        
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
        icon_path = os.path.join(APP_DIR, "dist", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(APP_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

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
        opt_title = QLabel("옵션 & 설정 (단축키: [ )")
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

        # 1-1. 저장 파일명 (.mp4 생략 표시)
        name_box = QHBoxLayout()
        self.nameInput = QLineEdit("output")
        self.nameInput.textChanged.connect(self.on_input_modified)
        self.nameInput.returnPressed.connect(self.on_name_input_enter)
        self.nameInput.textChanged.connect(self.update_name_input_style)
        self.playOutBtn = QPushButton("컷팅")
        self.playOutBtn.setToolTip("무손실 컷팅 실행 / 저장 영상 재생")
        self.playOutBtn.clicked.connect(self.on_cut_or_play_clicked)
        name_box.addWidget(self.nameInput, 1)
        name_box.addWidget(self.playOutBtn, 0)

        opt_layout.addWidget(QLabel("저장 파일명"))
        opt_layout.addLayout(name_box)

        # 1-2. 저장 옵션
        self.muteCheck = QCheckBox("음소거 (영상만 가져오기)")
        self.copyMetaCheck = QCheckBox("속성 복사")
        self.copyMetaCheck.setChecked(True)
        self.autoNumberCheck = QCheckBox("자동 넘버링")
        self.autoNumberCheck.setChecked(False)  # default: unchecked
        self.hudCheck = QCheckBox("동영상 정보 HUD 표시")
        self.hudCheck.toggled.connect(self.on_hud_check_toggled)
        opt_layout.addWidget(self.muteCheck)
        opt_layout.addWidget(self.copyMetaCheck)
        opt_layout.addWidget(self.autoNumberCheck)
        opt_layout.addWidget(self.hudCheck)

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
        self.dirInput.textChanged.connect(self.on_input_modified)
        self.dirBtn = QPushButton("선택")
        self.dirBtn.clicked.connect(self.openDirDialog)
        dir_box.addWidget(self.dirInput, 1)
        dir_box.addWidget(self.dirBtn, 0)
        opt_layout.addWidget(QLabel("저장 경로"))
        opt_layout.addLayout(dir_box)

        # 1-4. 작업 히스토리 및 최근 작업 폴더 (글씨 흰색 스타일 적용)
        combo_style = """
            QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e;
                color: #ffffff;
                selection-background-color: #0078d7;
                selection-color: white;
            }
        """

        opt_layout.addWidget(QLabel("작업 히스토리"))
        self.taskHistoryCombo = QComboBox()
        self.taskHistoryCombo.setStyleSheet(combo_style)
        self.taskHistoryCombo.currentIndexChanged.connect(self.on_task_history_selected)
        opt_layout.addWidget(self.taskHistoryCombo)

        opt_layout.addWidget(QLabel("최근 작업 폴더"))
        hist_box = QHBoxLayout()
        self.historyCombo = QComboBox()
        self.historyCombo.setStyleSheet(combo_style)
        self.historyCombo.currentIndexChanged.connect(self.on_history_combo_changed)
        self.openDirBtn = QPushButton("열기")
        self.openDirBtn.clicked.connect(self.open_current_directory)
        hist_box.addWidget(self.historyCombo, 1)
        hist_box.addWidget(self.openDirBtn, 0)
        opt_layout.addLayout(hist_box)

        opt_layout.addStretch()

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
        sb_title = QLabel("재생 목록 (단축키: ] )")
        self.add_file_btn = QPushButton("+ 추가")
        self.add_file_btn.setStyleSheet("background-color: #2d89ef; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px;")
        self.add_file_btn.clicked.connect(self.openFileDialog)
        sb_header.addWidget(sb_title)
        sb_header.addStretch()
        sb_header.addWidget(self.add_file_btn)
        sidebar_layout.addLayout(sb_header)

        self.playlist_widget = CustomPlaylistListWidget()
        self.playlist_widget.setItemDelegate(PlaylistDelegate(self.playlist_widget))
        self.playlist_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #333;
                border-radius: 4px;
                outline: none;
            }
        """)
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

        # 포커스 아웃 필터 등록 (입력 필드가 포커스 잃으면 타임라인으로 반환)
        self.focus_filter = FocusOutFilter(self.player_widget.trimming_slider, self)
        self.nameInput.installEventFilter(self.focus_filter)
        self.dirInput.installEventFilter(self.focus_filter)
        self.startInput.installEventFilter(self.focus_filter)
        self.endInput.installEventFilter(self.focus_filter)
        self.taskHistoryCombo.installEventFilter(self.focus_filter)
        self.historyCombo.installEventFilter(self.focus_filter)

    def build_hotkey_settings_page(self):
        opt_hotkey_page = QWidget()
        opt_hotkey_page.setStyleSheet("QWidget { background-color: #252526; color: white; }")
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
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #252526; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("QWidget { background-color: #252526; color: white; }")
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
            self.hotkeys = copy.deepcopy(DEFAULT_HOTKEYS)
            self.save_hotkeys()
            self.refresh_hotkey_table()

    def get_active_working_dir(self):
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
        saved_paths = load_app_data_json("playlist_history.json")
        if saved_paths and isinstance(saved_paths, list):
            self.playlist_files = []
            self.playlist_widget.clear()
            for path in saved_paths:
                if isinstance(path, str):
                    norm_p = path.replace('\\', '/')
                    if os.path.isfile(norm_p):
                        self.add_file_to_playlist(norm_p, load_immediately=False, save_history=False)
            self.save_playlist_history()

    def save_playlist_history(self):
        save_app_data_json("playlist_history.json", self.playlist_files)

    def add_file_to_playlist(self, file_path: str, load_immediately=True, save_history=True):
        file_path = file_path.replace('\\', '/')
        if file_path and os.path.isfile(file_path):
            if file_path not in self.playlist_files:
                self.playlist_files.append(file_path)
                item = QListWidgetItem(os.path.basename(file_path))
                item.setToolTip(file_path)
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                item.setSizeHint(QSize(0, 22))
                self.playlist_widget.addItem(item)
            
            for i in range(self.playlist_widget.count()):
                it = self.playlist_widget.item(i)
                if it.data(Qt.ItemDataRole.UserRole) == file_path:
                    self.playlist_widget.setCurrentItem(it)
                    break

            if save_history:
                self.save_playlist_history()

            self.refresh_playlist_colors()

            if load_immediately:
                self.fileInput.setText(file_path)

    def remove_selected_playlist_item(self):
        item = self.playlist_widget.currentItem()
        if item:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if self.player_widget.video_path_cached == file_path or self.fileInput.text() == file_path:
                self.player_widget.unload_video()
                self.fileInput.setText("")
            
            row = self.playlist_widget.row(item)
            self.playlist_widget.takeItem(row)
            if file_path in self.playlist_files:
                self.playlist_files.remove(file_path)
                self.save_playlist_history()
            self.refresh_playlist_colors()

    def delete_selected_playlist_file_permanently(self):
        item = self.playlist_widget.currentItem()
        if not item:
            return
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return
            
        file_name = os.path.basename(file_path)
        
        res = QMessageBox.question(
            self,
            "파일 물리 삭제 확인",
            f"'{file_name}' 파일을 디스크에서 완전히 삭제하시겠습니까?\n\n경로: {file_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return

        # 1. 미디어 플레이어가 해당 파일을 사용 중이면 소유권/핸들 해제
        if self.player_widget.video_path_cached == file_path or self.fileInput.text() == file_path:
            self.player_widget.unload_video()
            self.fileInput.setText("")

        # 2. 재생목록에서 제거
        row = self.playlist_widget.row(item)
        self.playlist_widget.takeItem(row)
        if file_path in self.playlist_files:
            self.playlist_files.remove(file_path)
            self.save_playlist_history()
        self.refresh_playlist_colors()

        # 3. 디스크에서 실제 파일 삭제
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self.show_toast(f"'{file_name}' 파일이 물리적으로 삭제되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "삭제 실패", f"파일을 삭제하지 못했습니다:\n{e}")
        else:
            self.show_toast(f"'{file_name}' 목록에서 제거되었습니다.")

    def clear_playlist(self):
        if self.player_widget.has_video_loaded:
            self.player_widget.unload_video()
            self.fileInput.setText("")
        self.playlist_widget.clear()
        self.playlist_files.clear()
        self.save_playlist_history()

    def on_playlist_item_double_clicked(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path and os.path.isfile(file_path):
            self.fileInput.setText(file_path)
            self.player_widget.load_video(file_path, auto_play=True)
            self.player_widget.setFocus()

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

            delete_file_act = QAction("파일 물리 삭제 (Ctrl+Del)", menu)
            delete_file_act.triggered.connect(self.delete_selected_playlist_file_permanently)

            menu.addAction(open_folder_act)
            menu.addAction(props_act)
            menu.addSeparator()
            menu.addAction(remove_act)
            menu.addAction(delete_file_act)

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
                    
                    self.startInput.max_val_cs = duration_cs
                    self.endInput.max_val_cs = duration_cs
                    
                    start_cs = 0
                    end_cs = duration_cs
                    
                    self.startInput.setText(self.startInput.centiseconds_to_time(start_cs))
                    base_name = os.path.basename(text)
                    if base_name.lower().endswith(".mp4"):
                        base_name = base_name[:-4]
                    if not self.nameInput.text() or self.nameInput.text() == "output":
                        self.nameInput.setText(base_name)

                    self.check_target_file_exists()
                    self.update_timeline_cut_highlights()
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
        self.playOutBtn.setStyleSheet("")
        out_dir = self.dirInput.text()
        out_name = self.nameInput.text()
        output_file = os.path.join(out_dir, out_name)
        if output_file and os.path.isfile(output_file):
            self.player_widget.load_video(output_file, auto_play=True)
        else:
            QMessageBox.warning(self, "경고", "편집 영상 파일이 존재하지 않습니다.")

    def update_output_play_btn_state(self):
        if self.playOutBtn.text() == "재생":
            out_dir = self.dirInput.text()
            out_name = self.nameInput.text()
            if out_dir and out_name:
                output_file = os.path.join(out_dir, out_name)
                is_exist = os.path.isfile(output_file)
            else:
                is_exist = False
            self.playOutBtn.setEnabled(is_exist)
        else:
            has_input = bool(self.fileInput.text().strip() and os.path.isfile(self.fileInput.text().strip()))
            self.playOutBtn.setEnabled(has_input)

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

    def get_clean_output_name(self) -> str:
        txt = self.nameInput.text().strip()
        if txt.lower().endswith(".mp4"):
            txt = txt[:-4].strip()
        return txt if txt else "output"

    def get_full_output_path(self) -> str:
        out_dir = self.dirInput.text().strip()
        clean_name = self.get_clean_output_name()
        return os.path.join(out_dir, clean_name + ".mp4").replace('\\', '/')

    def check_target_file_exists(self):
        if hasattr(self, 'is_loading_history') and self.is_loading_history:
            return
        full_path = self.get_full_output_path()
        if full_path and os.path.exists(full_path):
            self.autoNumberCheck.blockSignals(True)
            self.autoNumberCheck.setChecked(True)
            self.autoNumberCheck.blockSignals(False)

    def show_toast(self, message: str):
        if not hasattr(self, 'toast_label') or self.toast_label is None:
            self.toast_label = QLabel(self)
            self.toast_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(30, 100, 200, 0.95);
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 8px 16px;
                    border-radius: 6px;
                    border: 1px solid rgba(255, 255, 255, 0.4);
                }
            """)
            self.toast_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.toast_label.hide()
        
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self.toast_label.move(max(10, self.width() - self.toast_label.width() - 20), 20)
        self.toast_label.show()
        self.toast_label.raise_()
        
        QTimer.singleShot(1000, lambda: self.toast_label.hide() if hasattr(self, 'toast_label') and self.toast_label else None)

    def on_cut_or_play_clicked(self):
        if self.playOutBtn.text() == "재생":
            self.play_output_video()
        else:
            self.executeCutter()

    def executeCutter(self):
        video_in = self.fileInput.text()
        start_time = self.startInput.displayText()
        end_time = self.endInput.displayText()
        clean_name = self.get_clean_output_name()
        out_name = clean_name + ".mp4"
        out_dir = self.dirInput.text().strip()

        if not video_in or not out_dir:
            QMessageBox.warning(
                self, "경고", "파일 경로 및 저장 위치를 모두 지정하십시오."
            )
            return

        os.makedirs(out_dir, exist_ok=True)

        video_out = os.path.join(out_dir, out_name).replace('\\', '/')
        if self.autoNumberCheck.isChecked():
            video_out = get_unique_filename(video_out)
            final_name = os.path.basename(video_out)
            if final_name.lower().endswith(".mp4"):
                final_name = final_name[:-4]
            self.nameInput.blockSignals(True)
            self.nameInput.setText(final_name)
            self.nameInput.blockSignals(False)

        ffmpeg_bin = get_ffmpeg_path()

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
            out_filename = os.path.basename(video_out)
            self.show_toast(f"'{out_filename}' (으)로 저장되었습니다.")

            self.playOutBtn.setText("재생")
            self.playOutBtn.setStyleSheet("background-color: #ff3b30; color: white; font-weight: bold;")
            self.playOutBtn.setEnabled(True)
            
            # 무손실 컷팅 성공 시 항상 작업 히스토리 저장
            self.add_task_history()

            self.refresh_playlist_colors()
            self.update_timeline_cut_highlights()
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "에러", f"FFmpeg 분할 실패:\n{e.stderr}")

    def save_history(self, path):
        path = path.replace('\\', '/')
        saved = load_app_data_json("trim_history.json")
        history = [p.replace('\\', '/') for p in saved] if saved and isinstance(saved, list) else []
        if path in history:
            history.remove(path)
        history.insert(0, path)
        history = history[:5]
        save_app_data_json("trim_history.json", history)
        self.refresh_history_combo(history)

    def load_history(self):
        saved = load_app_data_json("trim_history.json")
        history = [p.replace('\\', '/') for p in saved] if saved and isinstance(saved, list) else []
        self.refresh_history_combo(history)

    def refresh_history_combo(self, history):
        self.historyCombo.clear()
        
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
        saved = load_app_data_json("task_history.json")
        self.task_histories = saved if saved and isinstance(saved, list) else []
        self.refresh_task_history_combo()
        self.refresh_playlist_colors()
        self.update_timeline_cut_highlights()

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
        
        # 1. 영상 파일 로드 및 재생바 연동
        v_in = task.get('video_in', '')
        if v_in and os.path.isfile(v_in):
            self.fileInput.setText(v_in)
            if self.player_widget.video_path_cached != v_in:
                self.player_widget.load_video(v_in, auto_play=False)

        # 2. 작업 히스토리의 시작/종료 범위로 start & end 설정
        start_str = task.get('start_time', '00:00:00.00')
        end_str = task.get('end_time', '00:00:00.00')
        self.startInput.setText(''.join(c for c in start_str if c.isdigit()))
        self.endInput.setText(''.join(c for c in end_str if c.isdigit()))
        
        # 3. 타임라인 슬라이더의 [Start, End] 마커 및 재생 헤드 위치 동기화
        start_cs = self.startInput.time_to_centiseconds(self.startInput.displayText())
        end_cs = self.endInput.time_to_centiseconds(self.endInput.displayText())
        start_ms = start_cs * 10
        end_ms = end_cs * 10
        
        def apply_trim_bounds():
            if hasattr(self.player_widget, 'trimming_slider'):
                self.player_widget.trimming_slider.set_end_ms(end_ms)
                self.player_widget.trimming_slider.set_start_ms(start_ms)
                self.player_widget.trimming_slider.set_position(start_ms)
            if hasattr(self.player_widget, 'media_player'):
                self.player_widget.media_player.setPosition(start_ms)

        apply_trim_bounds()
        QTimer.singleShot(100, apply_trim_bounds)
        QTimer.singleShot(350, apply_trim_bounds)

        raw_out_name = task.get('out_name', '')
        if raw_out_name.lower().endswith(".mp4"):
            raw_out_name = raw_out_name[:-4]
        self.nameInput.setText(raw_out_name)

        self.muteCheck.setChecked(task.get('mute', False))
        self.copyMetaCheck.setChecked(task.get('copy_meta', True))
        self.autoNumberCheck.setChecked(task.get('auto_number', False))
        
        radio_state = task.get('radio_state', 'custom')
        if radio_state == 'same':
            self.radioSame.setChecked(True)
        elif radio_state == 'output':
            self.radioOutput.setChecked(True)
        else:
            self.radioCustom.setChecked(True)
            
        self.dirInput.setText(task.get('out_dir', ''))
        
        self.create_history_flag = False
        self.is_loading_history = False
        self.update_timeline_cut_highlights()
        self.update_output_play_btn_state()
        if hasattr(self, 'player_widget') and self.player_widget:
            self.player_widget.setFocus()

    def add_task_history(self):
        video_in = self.fileInput.text().strip()
        if not video_in:
            return
        start_time = self.startInput.displayText()
        end_time = self.endInput.displayText()
        clean_name = self.get_clean_output_name()
        out_name = clean_name + ".mp4"
        out_dir = self.dirInput.text().strip()
        
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
        
        self.task_histories = [
            t for t in self.task_histories 
            if not (t['video_in'] == video_in and t['start_time'] == start_time and t['end_time'] == end_time and t['out_name'] == out_name and t['out_dir'] == out_dir)
        ]
        
        self.task_histories.insert(0, task)
        self.task_histories = self.task_histories[:50]
        
        save_app_data_json("task_history.json", self.task_histories)
        self.refresh_task_history_combo()
        self.refresh_playlist_colors()
        self.update_timeline_cut_highlights()

    def refresh_playlist_colors(self):
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            item.setSizeHint(QSize(0, 22))  # 고밀도 세로 간격 22px 지정
            v_path = item.data(Qt.ItemDataRole.UserRole)
            if not v_path:
                continue
            
            norm_v = os.path.abspath(os.path.normpath(v_path)).lower()
            cut_count = sum(
                1 for t in self.task_histories 
                if t.get('video_in') and os.path.abspath(os.path.normpath(t.get('video_in'))).lower() == norm_v
            )
            
            # 글씨색은 언제나 기존의 흰색(#ffffff)으로 유지
            item.setForeground(QColor("#ffffff"))
            
            if cut_count >= 3:
                # 3개 이상 컷팅 이력: 선명한 파스텔톤 노란색 배경 (#c4ab14)
                item.setBackground(QColor("#c4ab14"))
            elif cut_count == 2:
                # 2개 컷팅 이력: 중간 옅은 파스텔 노란색 배경 (#99861e)
                item.setBackground(QColor("#99861e"))
            elif cut_count == 1:
                # 1개 컷팅 이력: 아주 옅은 파스텔 노란색 배경 (#695c1b)
                item.setBackground(QColor("#695c1b"))
            else:
                # 0개 컷팅 이력: 기본 어두운 배경 (#1e1e1e)
                item.setBackground(QColor("#1e1e1e"))

    def update_timeline_cut_highlights(self):
        cur_file = self.fileInput.text().strip()
        if not cur_file or not hasattr(self.player_widget, 'trimming_slider'):
            return
        
        regions = []
        for t in self.task_histories:
            if t.get('video_in') == cur_file:
                try:
                    s_cs = self.startInput.time_to_centiseconds(t.get('start_time', '00:00:00.00'))
                    e_cs = self.endInput.time_to_centiseconds(t.get('end_time', '00:00:00.00'))
                    name = t.get('out_name', '')
                    regions.append({
                        'start_ms': s_cs * 10,
                        'end_ms': e_cs * 10,
                        'name': name
                    })
                except:
                    pass
        self.player_widget.trimming_slider.set_cut_history_regions(regions)

    def on_hud_check_toggled(self, checked):
        self.player_widget.force_hud_visible = checked
        self.player_widget.update_hud()

    def on_input_modified(self):
        if not self.is_loading_history:
            self.create_history_flag = True
        self.playOutBtn.setText("컷팅")
        self.playOutBtn.setStyleSheet("")
        self.check_target_file_exists()
        self.update_timeline_cut_highlights()

    def on_name_input_enter(self):
        self.executeCutter()

    def update_name_input_style(self):
        current_name = self.nameInput.text()
        if self.last_enter_name and current_name == self.last_enter_name:
            self.nameInput.setStyleSheet("border: 1px solid red;")
        else:
            self.nameInput.setStyleSheet("")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange:
            if hasattr(self, 'player_widget') and self.player_widget:
                self.player_widget.update_hud()

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
