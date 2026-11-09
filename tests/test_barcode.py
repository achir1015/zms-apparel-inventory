"""Code 128 正確性：畫成圖片後用 zbar 解碼，內容要一致。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zms import barcode  # noqa: E402

pyzbar = pytest.importorskip("pyzbar.pyzbar")
from PIL import Image, ImageDraw  # noqa: E402


def render(text, unit=3, height=80):
    ws = barcode.modules(text)
    img = Image.new("L", (sum(ws) * unit, height), 255)
    d = ImageDraw.Draw(img)
    x, bar = ws[0] * unit, True
    for w in ws[1:-1]:
        if bar:
            d.rectangle([x, 0, x + w * unit - 1, height], fill=0)
        x += w * unit
        bar = not bar
    return img


def test_pattern_table():
    assert len(barcode.PATTERNS) == 107
    assert all(sum(map(int, p)) == 11 for p in barcode.PATTERNS[:106])
    assert sum(map(int, barcode.PATTERNS[106])) == 13


@pytest.mark.parametrize("text", ["T200-01-M", "22222-00-11", "4710123456789A", "12345678", "A", "AB-cd_9/x"])
def test_decode(text):
    res = pyzbar.decode(render(text))
    assert res and res[0].data.decode() == text and res[0].type == "CODE128"


def test_svg():
    s = barcode.svg("T200-01-M", height_mm=10, width_mm=36)
    assert s.startswith("<svg") and 'width="36.00mm"' in s
    with pytest.raises(ValueError):
        barcode.svg("中文")
