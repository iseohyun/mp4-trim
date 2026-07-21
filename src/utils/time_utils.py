def ms_to_time_str(ms: int) -> str:
    total_sec = ms // 1000
    cs = (ms % 1000) // 10
    hh = total_sec // 3600
    mm = (total_sec % 3600) // 60
    ss = total_sec % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{cs:02d}"
