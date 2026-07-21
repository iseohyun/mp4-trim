from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QKeyEvent

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
