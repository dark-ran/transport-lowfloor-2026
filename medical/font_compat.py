"""Select an installed Korean-capable plotting font across Windows and Linux."""
from matplotlib import font_manager


def korean_font():
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for candidate in ("Malgun Gothic", "NanumGothic", "Noto Sans CJK KR"):
        if candidate in installed:
            return candidate
    return "DejaVu Sans"
