"""吊牌／貼紙條碼標籤：產生可列印的 HTML（以 mm 為單位，標籤機或 A4 標籤紙都可印）。"""
import html
import os
import tempfile
import webbrowser

from . import barcode

LAYOUTS = {
    # 代號：(名稱, 標籤寬 mm, 高 mm, 版面)
    "tag40x60": ("吊牌 40×60 mm（標籤機，一張一個）", 40, 60, "roll"),
    "tag35x50": ("吊牌 35×50 mm（標籤機，一張一個）", 35, 50, "roll"),
    "sticker50x30": ("貼紙 50×30 mm（標籤機，一張一個）", 50, 30, "roll"),
    "a4_3x8": ("A4 標籤紙 3×8＝24 格（70×37 mm）", 70, 37.125, "a4"),
}
PRICE_FIELDS = {"1": "price1", "2": "price2", "3": "price3", "0": None}


def _money(v):
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return ""
    return "NT$ {:,.0f}".format(v) if v else ""


def _special(it, base):
    try:
        base = float(base or 0)
    except (TypeError, ValueError):
        return None
    if it.get("special_price") is not None:
        sp = float(it["special_price"])
    elif it.get("special_discount") is not None:
        sp = round(base * float(it["special_discount"]) / 100)
    else:
        return None
    return sp if sp < base else None


def label_html(items, layout="tag40x60", price_level="1", company="", show_company=True, show_special=True):
    name, w, h, mode = LAYOUTS[layout]
    pf = PRICE_FIELDS.get(str(price_level))
    small = h < 40
    cells = []
    for it in items:
        bc_w = min(w - 6, 45)
        try:
            code_svg = barcode.svg(it["code"], height_mm=8 if small else 11, width_mm=bc_w)
        except ValueError:
            code_svg = '<div class="err">條碼含中文，請在產品資料填英數條碼</div>'
        price = _money(it.get(pf)) if pf else ""
        sp = _special(it, it.get(pf)) if (pf and show_special) else None
        if sp is not None and price:
            price = '<div class="old">原價 <s>%s</s></div><span class="sp">特價 %s</span>' % (price, _money(sp))
        color = (it.get("color") or "") + (" " + it["color_name"] if it.get("color_name") else "")
        rows = []
        if show_company and company and not small:
            rows.append('<div class="co">%s</div>' % html.escape(company))
        rows.append('<div class="nm">%s</div>' % html.escape(it.get("name") or ""))
        rows.append('<div class="ln"><b>貨號</b> %s</div>' % html.escape(it["prod_no"]))
        rows.append('<div class="ln"><b>顏色</b> %s　<b>尺寸</b> %s</div>' % (html.escape(color),
                                                                      html.escape(it.get("size") or "")))
        if it.get("fabric_name") and not small:
            rows.append('<div class="ln"><b>材質</b> %s</div>' % html.escape(it["fabric_name"]))
        rows.append('<div class="bc">%s<div class="hr">%s</div></div>' % (code_svg, html.escape(it["code"])))
        if price:
            rows.append('<div class="pr">%s</div>' % price)
        cell = '<div class="lb">%s</div>' % "".join(rows)
        cells += [cell] * int(it.get("copies") or 1)

    if mode == "roll":
        page = "@page{size:%smm %smm;margin:0}" % (w, h)
        body = "".join('<div class="pg">%s</div>' % c for c in cells)
    else:
        page = "@page{size:A4;margin:0}"
        per = 24
        pages = [cells[i:i + per] for i in range(0, len(cells), per)]
        body = "".join('<div class="a4">%s</div>' % "".join(p) for p in pages)
    fs = 2.6 if small else 3.0
    top = 5 if layout.startswith("tag") else 2  # 吊牌上方留穿繩孔
    return """<!doctype html><html><head><meta charset="utf-8"><title>吊牌標籤</title><style>
%(page)s
*{box-sizing:border-box}body{margin:0;font-family:'Microsoft JhengHei','PingFang TC','Noto Sans TC',sans-serif;color:#000}
.pg{width:%(w)smm;height:%(h)smm;page-break-after:always;overflow:hidden}
.a4{width:210mm;height:297mm;display:grid;grid-template-columns:repeat(3,70mm);grid-auto-rows:37.125mm;
page-break-after:always}
.lb{width:%(w)smm;height:%(h)smm;padding:%(top)smm 3mm 2mm;display:flex;flex-direction:column;gap:.6mm;
font-size:%(fs)smm;line-height:1.15;overflow:hidden}
.co{font-size:%(fs2)smm;text-align:center;letter-spacing:.3mm;border-bottom:.2mm solid #000;padding-bottom:.6mm}
.nm{font-size:%(fs3)smm;font-weight:bold;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ln b{font-weight:normal;color:#444}.bc{text-align:center;margin-top:auto}.bc svg{display:block;margin:0 auto}
.hr{font-family:Consolas,monospace;font-size:%(fs2)smm;letter-spacing:.2mm}
.pr{font-size:%(fs4)smm;font-weight:bold;text-align:center}
.err{color:#c00;font-size:2.4mm}.old{font-weight:normal;font-size:%(fs2)smm;color:#555}.sp{font-size:%(fs3)smm;white-space:nowrap}
.bar{position:fixed;top:6px;right:6px}@media print{.bar{display:none}}
@media screen{body{background:#ddd}.pg,.a4{background:#fff;margin:6px auto;box-shadow:0 0 4px #888}}
</style></head><body><div class="bar"><button onclick="print()" style="padding:6px 16px">列印</button></div>
%(body)s</body></html>""" % dict(page=page, w=w, h=h, top=top, fs=fs, fs2=fs * 0.85, fs3=fs * 1.2, fs4=fs * 1.5, body=body)


def open_labels(items, **kw):
    path = os.path.join(tempfile.gettempdir(), "zms_labels.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(label_html(items, **kw))
    webbrowser.open("file:///" + path.replace("\\", "/"))
    return path


# ---------------------------------------------------------------- 裝箱標籤
BOX_LAYOUTS = {
    "box100x70": ("裝箱標籤 100×70 mm（標籤機）", 100, 70, "roll"),
    "box100x150": ("物流標籤 100×150 mm（標籤機）", 100, 150, "roll"),
    "a4_2x4": ("A4 一張 8 格（105×74 mm）", 105, 74.25, "a4"),
}


def box_html(info, boxes=1, layout="box100x70"):
    from . import dates
    name, w, h, mode = BOX_LAYOUTS[layout]
    boxes = max(int(boxes or 1), 1)
    to, snd = info["to"], info["sender"]
    try:
        code = barcode.svg(info["doc_no"], height_mm=9, width_mm=min(w - 40, 55))
    except ValueError:
        code = ""
    e = html.escape
    cells = []
    for i in range(1, boxes + 1):
        cells.append("""<div class="lb">
<div class="to"><div class="k">收件</div><div><div class="nm">%s　<span class="sx">先生／小姐 收</span></div>
<div>%s</div><div>電話：%s　%s</div></div></div>
<div class="mid"><div class="bx">第 <b>%d</b> / %d 箱</div><div class="bc">%s<div class="hr">%s</div></div></div>
<div class="ft"><span>%s　%s　共 %s 件</span><span>寄件：%s %s</span></div>
</div>""" % (e(to.get("name") or ""), e(to.get("address") or ""), e(to.get("tel") or ""),
             e(("聯絡人：" + to["contact"]) if to.get("contact") else ""), i, boxes, code, e(info["doc_no"]),
             e(info["doc_type"]), dates.roc(info["doc_date"]), info["total_qty"], e(snd.get("name") or ""),
             e(snd.get("tel") or "")))
    if mode == "roll":
        page, body = "@page{size:%smm %smm;margin:0}" % (w, h), "".join('<div class="pg">%s</div>' % c for c in cells)
    else:
        page = "@page{size:A4;margin:0}"
        body = "".join('<div class="a4">%s</div>' % "".join(cells[j:j + 8]) for j in range(0, len(cells), 8))
    big = h >= 100
    return """<!doctype html><html><head><meta charset="utf-8"><title>裝箱標籤 %(no)s</title><style>
%(page)s *{box-sizing:border-box}body{margin:0;font-family:'Microsoft JhengHei','PingFang TC','Noto Sans TC',sans-serif}
.pg{width:%(w)smm;height:%(h)smm;page-break-after:always;overflow:hidden}
.a4{width:210mm;height:297mm;display:grid;grid-template-columns:repeat(2,105mm);grid-auto-rows:74.25mm;page-break-after:always}
.lb{width:%(w)smm;height:%(h)smm;padding:4mm 5mm;display:flex;flex-direction:column;gap:2mm;font-size:3.4mm;
border:.3mm dashed #bbb}
.to{display:flex;gap:2mm;border-bottom:.4mm solid #000;padding-bottom:2mm;flex:%(toflex)s}
.k{writing-mode:vertical-rl;font-weight:bold;background:#000;color:#fff;padding:1mm .6mm;font-size:3.2mm}
.nm{font-size:%(nm)smm;font-weight:bold;line-height:1.2}.sx{font-size:3.2mm;font-weight:normal}
.mid{display:flex;justify-content:space-between;align-items:center}.bx{font-size:4.2mm}.bx b{font-size:%(bx)smm}
.bc{text-align:center}.bc svg{display:block}.hr{font-family:Consolas,monospace;font-size:3mm}
.ft{display:flex;flex-wrap:wrap;justify-content:space-between;gap:0 3mm;font-size:2.8mm;color:#333;margin-top:auto}.ft span{white-space:nowrap}
.bar{position:fixed;top:6px;right:6px}@media print{.bar{display:none}.lb{border:none}}
@media screen{body{background:#ddd}.pg,.a4{background:#fff;margin:6px auto;box-shadow:0 0 4px #888}}
</style></head><body><div class="bar"><button onclick="print()" style="padding:6px 16px">列印</button></div>%(body)s
</body></html>""" % dict(no=e(info["doc_no"]), page=page, w=w, h=h, body=body, nm=7 if big else 5.2,
                         bx=10 if big else 7, toflex="1" if big else "0 0 auto")


def open_box_labels(info, **kw):
    path = os.path.join(tempfile.gettempdir(), "zms_box_%s.html" % info["doc_no"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(box_html(info, **kw))
    webbrowser.open("file:///" + path.replace("\\", "/"))
    return path
