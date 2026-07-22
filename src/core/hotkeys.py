from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QKeySequence

DEFAULT_HOTKEYS = {
    "toggle_option": {"name": "옵션 패널 토글", "primary": "[", "secondary": ""},
    "toggle_playlist": {"name": "재생목록 토글", "primary": "]", "secondary": ""},
    "play_pause": {"name": "재생 / 일시정지", "primary": "Space", "secondary": "K"},
    "step_1s_prev": {"name": "1초 뒤로 이동", "primary": "Left", "secondary": ""},
    "step_1s_next": {"name": "1초 앞으로 이동", "primary": "Right", "secondary": ""},
    "step_frame_prev": {"name": "1프레임 뒤로 이동", "primary": "Ctrl+Left", "secondary": ""},
    "step_frame_next": {"name": "1프레임 앞으로 이동", "primary": "Ctrl+Right", "secondary": ""},
    "toggle_fullscreen": {"name": "전체화면 토글", "primary": "F", "secondary": "F11"},
    "exit_fullscreen": {"name": "전체화면 해제", "primary": "Esc", "secondary": ""},
    "show_properties": {"name": "동영상 정보 보기", "primary": "?", "secondary": ""},
    "delete_playlist_item": {"name": "재생목록 항목 삭제", "primary": "Delete", "secondary": ""},
    "rename_playlist_item": {"name": "재생목록 파일 이름 변경", "primary": "F2", "secondary": ""},
    "flip_h": {"name": "수평 뒤집기", "primary": "H", "secondary": ""},
    "flip_v": {"name": "수직 뒤집기", "primary": "V", "secondary": ""},
    "rotate_right": {"name": "오른쪽 90도 회전", "primary": "R", "secondary": ""},
    "rotate_left": {"name": "왼쪽 90도 회전", "primary": "L", "secondary": ""},
    "save_transform": {"name": "변형 상태 저장", "primary": "Ctrl+S", "secondary": ""},
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
    elif key == Qt.Key.Key_F2:
        k = "F2"
    else:
        k = QKeySequence(key).toString().upper()

    if not parts or (parts == ["Shift"] and k == "?"):
        if k == "?":
            parts = []

    parts.append(k)
    return "+".join(parts)
