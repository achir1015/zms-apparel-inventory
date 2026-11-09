"""日期：畫面用民國（115/11/09），資料庫存 DATE。"""
import datetime as _dt
import re


def today() -> _dt.date:
    return _dt.date.today()


def roc(d) -> str:
    if not d:
        return ""
    if isinstance(d, str):
        d = parse(d)
    return "%03d/%02d/%02d" % (d.year - 1911, d.month, d.day)


def roc_compact(d) -> str:
    return "%03d%02d%02d" % (d.year - 1911, d.month, d.day)


def parse(s) -> _dt.date:
    """接受 115/11/09、1151109、2026-11-09、20261109、11/09（今年）。"""
    if isinstance(s, _dt.datetime):
        return s.date()
    if isinstance(s, _dt.date):
        return s
    s = (s or "").strip()
    if not s:
        raise ValueError("日期空白")
    parts = [p for p in re.split(r"[/\-.\s]", s) if p]
    try:
        if len(parts) == 3:
            y, m, d = map(int, parts)
        elif len(parts) == 2:
            y = today().year
            m, d = map(int, parts)
        elif s.isdigit() and len(s) == 8:
            y, m, d = int(s[:4]), int(s[4:6]), int(s[6:])
        elif s.isdigit() and len(s) in (6, 7):
            y, m, d = int(s[:-4]), int(s[-4:-2]), int(s[-2:])
        else:
            raise ValueError
        if y < 1000:
            y += 1911
        return _dt.date(y, m, d)
    except ValueError:
        raise ValueError("日期格式不對：%s（例：115/11/09）" % s)


def month_range(period: str):
    """'202611' → (2026-11-01, 2026-11-30)"""
    y, m = int(period[:4]), int(period[4:6])
    start = _dt.date(y, m, 1)
    end = (_dt.date(y + (m == 12), m % 12 + 1, 1) - _dt.timedelta(days=1))
    return start, end
