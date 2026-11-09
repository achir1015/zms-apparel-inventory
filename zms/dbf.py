"""讀取舊系統 dBASE（.DBF，Big5）資料表。"""
import datetime as _dt
import os
import struct
from decimal import Decimal, InvalidOperation


def read_dbf(path, encoding="cp950", include_deleted=False):
    with open(path, "rb") as f:
        data = f.read()
    nrec, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields, o = [], 32
    while o < hlen and data[o] != 0x0D:
        name = data[o:o + 11].split(b"\x00")[0].decode("latin1").strip().upper()
        fields.append((name, chr(data[o + 11]), data[o + 16], data[o + 17]))
        o += 32
    rows = []
    for i in range(nrec):
        r = data[hlen + i * rlen: hlen + (i + 1) * rlen]
        if len(r) < rlen:
            break
        if r[:1] == b"*" and not include_deleted:
            continue
        p, row = 1, {}
        for name, t, w, dec in fields:
            raw = r[p:p + w]
            p += w
            row[name] = _conv(raw, t, dec, encoding)
        rows.append(row)
    return rows


def _conv(raw, t, dec, enc):
    if t in "CM" or t == "V":
        return raw.decode(enc, "replace").rstrip("\x00 ").strip()
    if t in "NF":
        s = raw.decode("latin1").strip().replace(",", "")
        if not s or s in ("-", "."):
            return Decimal(0)
        try:
            return Decimal(s)
        except InvalidOperation:
            return Decimal(0)
    if t == "D":
        s = raw.decode("latin1").strip()
        try:
            return _dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except Exception:
            return None
    if t == "L":
        return raw[:1] in (b"T", b"t", b"Y", b"y")
    return raw.decode(enc, "replace").strip()


def find_table(folder, name):
    for ext in (".DBF", ".dbf", ".Dbf"):
        p = os.path.join(folder, name + ext)
        if os.path.isfile(p):
            return p
    low = name.lower() + ".dbf"
    for f in os.listdir(folder):
        if f.lower() == low:
            return os.path.join(folder, f)
    return None
