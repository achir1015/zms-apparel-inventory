"""Code 128 條碼（純 Python，輸出 SVG）。

全數字且偶數長度用 Code C（較短），其他用 Code B（英數與符號，例如 T200-01-M）。
"""

# 0～106 的條／空寬度（條空條空條空），106 為終止碼（7 段）
PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
]
START_B, START_C, STOP = 104, 105, 106


def encode(text: str):
    """回傳碼值序列（含起始、檢查碼、終止碼）。"""
    if not text:
        raise ValueError("條碼內容空白")
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in text):
        raise ValueError("條碼只能用英數字與符號：%s" % text)
    if text.isdigit() and len(text) % 2 == 0 and len(text) >= 4:
        codes = [START_C] + [int(text[i:i + 2]) for i in range(0, len(text), 2)]
    else:
        codes = [START_B] + [ord(ch) - 32 for ch in text]
    check = (codes[0] + sum(i * c for i, c in enumerate(codes[1:], 1))) % 103
    return codes + [check, STOP]


def modules(text: str):
    """條空寬度序列（單位：模組），前後含 10 模組靜區。"""
    widths = [10]  # 靜區（空白）
    for c in encode(text):
        widths += [int(ch) for ch in PATTERNS[c]]
    widths.append(10)
    return widths


def svg(text: str, height_mm=12.0, width_mm=None, module_mm=0.25) -> str:
    """SVG 條碼；width_mm 指定時會等比縮放到該寬度。"""
    ws = modules(text)
    total = sum(ws)
    unit = (width_mm / total) if width_mm else module_mm
    rects, x, bar = [], ws[0] * unit, True  # 靜區之後，從「條」開始條、空交替
    for w in ws[1:-1]:
        if bar:
            rects.append('<rect x="%.3f" y="0" width="%.3f" height="%.2f"/>' % (x, w * unit, height_mm))
        x += w * unit
        bar = not bar
    x += ws[-1] * unit
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%.2fmm" height="%.2fmm" viewBox="0 0 %.3f %.2f" '
            'shape-rendering="crispEdges">%s</svg>' % (x, height_mm, x, height_mm, "".join(rects)))
