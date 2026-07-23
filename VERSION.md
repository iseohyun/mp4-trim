# Movie Player Lite Version History

## [v1.5.0] - 2026-07-23 (Full Visual Transform & DWM Screen Integration)
### Added / Enhanced
- **Win32 DWM Screen Integration**:
  - Disabled Windows 11 DWM rounded corners (`DWMWCP_DONOTROUND`) in frameless fullscreen mode.
  - Expanded frameless window to physical screen geometry (`screen.geometry()`) with `WindowStaysOnTopHint`, completely covering the Windows Taskbar and removing 1px edge gaps.
- **4-Stage Fullscreen Cycle (`F` / `F11` / Double-Click)**:
  - **Stage 0**: Standard Windowed Mode.
  - **Stage 1**: Standard Fullscreen (with UI controls & sidebars).
  - **Stage 2**: Frameless Video-Only Fullscreen (Aspect Fit, solid black background).
  - **Stage 3**: Frameless Video-Only Fullscreen (100% Stretched edge-to-edge fill).
  - Synchronized video screen double-click event to cycle through all 4 fullscreen stages.
- **Real-Time Visual Transform Renderer (`QGraphicsVideoItem`)**:
  - Replaced `QVideoWidget` with high-performance `QGraphicsScene` / `QGraphicsVideoItem`.
  - Applied unified `QTransform` matrix for simultaneous real-time visual rotation (90°/180°/270°) and horizontal/vertical flips (`H`, `V`).
  - Implemented aspect ratio auto-fit scaling on rotation (`R`, `L`).
- **Timestamp Overlay (`T` Key Toggle)**:
  - Floating translucent dark badge overlay over the bottom-left corner of the video screen.
  - Added `T` key shortcut toggle (ON/OFF).
- **Auto-Numbering & Filename Presets**:
  - Loaded videos automatically default output filename field to source file base name (without `.mp4`).
  - Automatic collision numbering (`(2)`, `(3)`...) when saving files with existing names.

### Fixed
- Resolved `AttributeError` tracebacks on overlay and play button handlers.
- Restored `T` key shortcut handler in keypress routing.

---

## [v1.4.0] - 2026-07-22 (Transform Hotkeys & Frame Screenshot)
### Added
- Shortcut transforms: `H` (Horizontal Flip), `V` (Vertical Flip), `R` (Rotate Right 90°), `L` (Rotate Left 90°).
- Live 4px red container border indicator on transform state modification.
- `Ctrl+S` smart behavior: Saves transformed video losslessly when modified; captures current frame PNG screenshot when unmodified.
- Playlist item `F2` inline rename with collision auto-numbering.

---

## [v1.3.0] - 2026-07-21 (Trimming Engine & Playlist History UI)
### Added
- FFmpeg timestamp normalization (`-ss` before `-i`, `-t` duration parameter) for zero-loss fast cutting.
- Pastel yellow background highlight gradient (1 cut, 2 cuts, 3+ cuts) for playlist items.
- Compact 22px item height and custom `PlaylistDelegate` painter.
- AppData path persistence (`playlist_history.json`, `task_history.json`).

---

## [v1.2.0] - 2026-07-20 (Focus Control Flow & Filmstrip Ruler Ticks)
### Added
- 8-Event focus routing to prevent accidental hotkey triggers during text editing.
- Filmstrip timeline ruler tick marks (1s/5s/10s intervals).
- `test_requirements_trace.py` automated traceability test suite.

---

## [v1.0.0] - 2026-07-19 (Initial Release)
- Core PySide6/PyQt6 video player, FFmpeg lossless trimming, custom hotkey manager, and playlist sidebar.
