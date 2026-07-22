import sys
import os
import shutil
import re
import subprocess
import ctypes
import ctypes.wintypes
from datetime import datetime

def get_ffmpeg_path() -> str:
    """시스템 환경변수(PATH), 로컬/번들 디렉터리 순으로 ffmpeg 경로를 탐색합니다."""
    system_ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if system_ffmpeg:
        return system_ffmpeg

    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    local_ffmpeg = os.path.join(base_path, "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    return "ffmpeg.exe"

def get_ffplay_path() -> str:
    """시스템 환경변수(PATH), 로컬/번들 디렉터리 순으로 ffplay 경로를 탐색합니다."""
    system_ffplay = shutil.which("ffplay") or shutil.which("ffplay.exe")
    if system_ffplay:
        return system_ffplay

    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    local_ffplay = os.path.join(base_path, "ffplay.exe")
    if os.path.exists(local_ffplay):
        return local_ffplay

    return "ffplay.exe"

def get_unique_filename(file_path: str) -> str:
    if not os.path.exists(file_path):
        return file_path
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    name, ext = os.path.splitext(base_name)
    
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
            subprocess.run(['explorer', '/select,', os.path.normpath(file_path)], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print("Failed to open folder:", e)

def get_media_creation_time_and_duration(video_path: str):
    ffmpeg_bin = get_ffmpeg_path()
    
    cmd = [ffmpeg_bin, "-i", video_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    output = res.stderr
    
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
        
    creation_match = re.search(r"creation_time\s*:\s*(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?[Z]?)", output, re.IGNORECASE)
    creation_dt = None
    if creation_match:
        time_str = creation_match.group(1)
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

def is_caps_lock_on() -> bool:
    try:
        return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)
    except:
        return False

def get_detailed_video_info(video_path: str) -> dict:
    ffmpeg_bin = get_ffmpeg_path()
    cmd = [ffmpeg_bin, "-i", video_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    output = res.stderr

    info = {
        "width": 0,
        "height": 0,
        "nickname": "Unknown",
        "aspect_ratio": "Unknown",
        "fps": 0.0,
        "duration": "00:00:00.00",
        "bitrate": "Unknown",
        "pix_fmt": "Unknown",
        "bit_depth": "8-bit",
        "metadata": {}
    }

    # 1. Parse duration & overall bitrate
    duration_match = re.search(r"Duration:\s*(\d+:\d+:\d+(?:\.\d+)?)", output)
    if duration_match:
        info["duration"] = duration_match.group(1)
    
    bitrate_match = re.search(r"Duration:.*bitrate:\s*(\d+\s*kb/s)", output, re.IGNORECASE)
    if bitrate_match:
        info["bitrate"] = bitrate_match.group(1)

    # 2. Parse Video Stream details
    video_stream_match = re.search(r"Stream #\d+:\d+.*Video:.*", output)
    if video_stream_match:
        line = video_stream_match.group(0)
        
        # Resolution
        res_match = re.search(r"(\d{3,4})x(\d{3,4})", line)
        if res_match:
            w = int(res_match.group(1))
            h = int(res_match.group(2))
            info["width"] = w
            info["height"] = h
            
            # Nickname mapping
            if w >= 3840 or h >= 2160:
                info["nickname"] = "UHD (4K)"
            elif w >= 2560 or h >= 1440:
                info["nickname"] = "QHD (2K)"
            elif w >= 1920 or h >= 1080:
                info["nickname"] = "FHD (1080p)"
            elif w >= 1280 or h >= 720:
                info["nickname"] = "HD (720p)"
            else:
                info["nickname"] = "SD"

        dar_match = re.search(r"DAR\s+(\d+:\d+)", line)
        if dar_match:
            info["aspect_ratio"] = dar_match.group(1)
        else:
            if info["width"] and info["height"]:
                from math import gcd
                g = gcd(info["width"], info["height"])
                info["aspect_ratio"] = f"{info['width']//g}:{info['height']//g}"

        # Frame rate
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", line)
        if fps_match:
            info["fps"] = float(fps_match.group(1))

        # pix_fmt / bit_depth
        pix_fmt_match = re.search(r"Video:[^,]+,\s*([a-zA-Z0-9_()]+)", line)
        if pix_fmt_match:
            fmt = pix_fmt_match.group(1)
            info["pix_fmt"] = fmt
            if "10" in fmt:
                info["bit_depth"] = "10-bit"
            elif "12" in fmt:
                info["bit_depth"] = "12-bit"
            else:
                info["bit_depth"] = "8-bit"

    # 3. Parse Metadata tags (under the first Metadata:)
    metadata_block_match = re.search(r"Metadata:\s*\n((?:\s+\w+\s+:[^\n]+\n)+)", output, re.IGNORECASE)
    if metadata_block_match:
        lines = metadata_block_match.group(1).split('\n')
        for l in lines:
            if ':' in l:
                k, v = l.split(':', 1)
                k = k.strip()
                v = v.strip()
                if k and v and k not in ("major_brand", "minor_version", "compatible_brands"):
                    info["metadata"][k] = v

    return info
