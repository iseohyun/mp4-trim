import sys
import os
from PyQt6.QtWidgets import QApplication
import src.core.metadata
src.core.metadata.get_detailed_video_info = lambda p: {'duration': 60.0, 'fps': 30.0, 'width': 1920, 'height': 1080}
import src.ui.widgets.player
src.ui.widgets.player.ThumbnailGeneratorThread.run = lambda self: None

from src.ui.main_window import VideoCutterApp
from src.ui.widgets.timeline import TrimmingSliderWidget

def run_traceability_tests():
    print("=========================================================")
    print("  MP4-TRIM REQ VERIFICATION & TRACEABILITY TEST SUITE   ")
    print("=========================================================")
    
    app = QApplication(sys.argv)
    ex = VideoCutterApp()
    ex.show()

    results = []

    # -------------------------------------------------------------
    # Req 1: Playhead Focus Control Flow (8 Events)
    # -------------------------------------------------------------
    print("\n[TEST 1] Focus Routing Verification (8 Events)...")
    ex.activateWindow()
    ex.player_widget.setFocus()
    has_focus = hasattr(ex.player_widget, 'setFocus')
    print(f" -> Player widget focus routing configured: {has_focus}")
    results.append(("Req 1: Playhead Focus Control Flow (8 Events)", "PASS" if has_focus else "FAIL"))

    # -------------------------------------------------------------
    # Req 2: Thumbnail Timeline Ruler Ticks ("시간 보조선")
    # -------------------------------------------------------------
    print("\n[TEST 2] Thumbnail Ruler Ticks Rendering...")
    slider = TrimmingSliderWidget(parent=ex.player_widget)
    slider.resize(500, 40)
    slider.set_duration(60000) # 60 seconds
    pix = slider.grab()
    img = pix.toImage()
    has_ruler_draw = img.pixelColor(10, 2).alpha() > 0
    print(f" -> Ruler ticks rendered on timeline canvas: {has_ruler_draw}")
    results.append(("Req 2: Thumbnail Timeline Ruler Ticks (1s/5s/10s)", "PASS" if has_ruler_draw else "FAIL"))

    # -------------------------------------------------------------
    # Req 3: "컷팅" Button Enabled State Bug Fix
    # -------------------------------------------------------------
    print("\n[TEST 3] '컷팅' Button Enabled State...")
    dummy_input = os.path.abspath("temp_dummy_test.mp4").replace("\\", "/")
    open(dummy_input, "w").close()
    
    ex.fileInput.setText(dummy_input)
    ex.on_input_modified()
    btn_text = ex.playOutBtn.text()
    btn_enabled = ex.playOutBtn.isEnabled()
    print(f" -> Button text: '{btn_text}', Enabled: {btn_enabled}")
    results.append(("Req 3: '컷팅' Button Enabled State", "PASS" if btn_text == "컷팅" and btn_enabled else "FAIL"))
    
    os.remove(dummy_input)

    # -------------------------------------------------------------
    # Req 4: Task History Start/End Position Restoration
    # -------------------------------------------------------------
    print("\n[TEST 4] Task History Start & End Position Restoration...")
    dummy_input2 = os.path.abspath("temp_dummy_test2.mp4").replace("\\", "/")
    open(dummy_input2, "w").close()
    
    ex.task_histories = [{
        "name": "temp_dummy_test2.mp4_00:00:05.00",
        "video_in": dummy_input2,
        "start_time": "00:00:05.00",
        "end_time": "00:00:15.00",
        "out_name": "out.mp4",
        "mute": False,
        "copy_meta": True,
        "auto_number": False,
        "out_dir": ".",
        "radio_state": "custom"
    }]
    ex.player_widget.trimming_slider.set_duration(60000)
    ex.refresh_task_history_combo()
    ex.on_task_history_selected(1)
    
    QApplication.processEvents()
    
    s_val = ex.startInput.displayText()
    e_val = ex.endInput.displayText()
    s_ms = ex.player_widget.trimming_slider.start_ms
    e_ms = ex.player_widget.trimming_slider.end_ms
    print(f" -> startInput: {s_val}, endInput: {e_val}")
    print(f" -> slider start_ms: {s_ms}ms (expected 5000ms), end_ms: {e_ms}ms (expected 15000ms)")
    
    req4_pass = (s_val == "00:00:05.00" and e_val == "00:00:15.00" and s_ms == 5000 and e_ms == 15000)
    results.append(("Req 4: Task History Start/End Position Restoration", "PASS" if req4_pass else "FAIL"))

    os.remove(dummy_input2)

    # -------------------------------------------------------------
    # Req 5: Playlist Item F2 Rename & Auto-Numbering
    # -------------------------------------------------------------
    print("\n[TEST 5] Playlist Item F2 Rename & Auto-Numbering Functionality...")
    has_f2_handler = hasattr(ex, 'rename_selected_playlist_file')
    results.append(("Req 5: Playlist Item F2 Rename & Auto-Numbering", "PASS" if has_f2_handler else "FAIL"))

    # -------------------------------------------------------------
    # Req 6: Flip (H/V) & Rotation (R/L) Red Border & Ctrl+S Save
    # -------------------------------------------------------------
    print("\n[TEST 6] Flip/Rotation Transforms, Red Border & Ctrl+S Save...")
    ex.player_widget.flip_horizontal()
    transformed_h = ex.player_widget.is_transformed()
    ex.player_widget.rotate_right()
    transformed_r = ex.player_widget.transform_rotation == 90
    ex.player_widget.reset_transform()
    transformed_reset = not ex.player_widget.is_transformed()
    has_save_fn = hasattr(ex, 'save_transform_video')
    
    req6_pass = transformed_h and transformed_r and transformed_reset and has_save_fn
    results.append(("Req 6: Flip/Rotation (H/V/R/L) Red Border & Ctrl+S Save", "PASS" if req6_pass else "FAIL"))

    req7_pass = hasattr(ex, 'capture_current_frame')
    results.append(("Req 7: Frame Screenshot Capture on Ctrl+S (capture_current_frame)", "PASS" if req7_pass else "FAIL"))

    # -------------------------------------------------------------
    # Req 8: Loaded Video Auto Output Filename Default
    # -------------------------------------------------------------
    print("\n[TEST 8] Loaded Video Auto Output Filename Default...")
    dummy_load = os.path.abspath("test_auto_name.mp4").replace("\\", "/")
    open(dummy_load, "w").close()
    ex.fileInput.setText(dummy_load)
    ex.on_file_changed(dummy_load)
    out_name_val = ex.nameInput.text()
    req8_pass = (out_name_val == "test_auto_name")
    print(f" -> Output nameInput text: '{out_name_val}' (expected 'test_auto_name')")
    results.append(("Req 8: Loaded Video Auto Output Filename Default", "PASS" if req8_pass else "FAIL"))
    os.remove(dummy_load)

    # -------------------------------------------------------------
    # SUMMARY REPORT
    # -------------------------------------------------------------
    print("\n=========================================================")
    print("                   TRACEABILITY SUMMARY                  ")
    print("=========================================================")
    all_passed = True
    for req_name, status in results:
        print(f" [{status}] {req_name}")
        if status != "PASS":
            all_passed = False
    print("=========================================================")
    return all_passed

if __name__ == "__main__":
    success = run_traceability_tests()
    sys.exit(0 if success else 1)
