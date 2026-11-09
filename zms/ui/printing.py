"""單據列印：產生 HTML 用瀏覽器開啟（可直接列印或另存 PDF）。"""
import html
import os
import tempfile
import webbrowser

from .. import dates
from ..doctypes import BY_CODE, label
from .common import fmt


def doc_html(svc, doc_id):
    h, lines = svc.get_doc(doc_id)
    dt = BY_CODE[h["doc_type"]]
    comp = svc.company() or {}
    names = {}
    for f, tbl in (("wh_no", "warehouses"), ("wh_no2", "warehouses"), ("sh_no", "shops"), ("sh_no2", "shops"),
                   ("ma_no", "vendors"), ("per_no", "employees")):
        if h.get(f):
            r = svc.master_get(tbl, [h[f]])
            names[f] = "%s %s" % (h[f], (r or {}).get("short_name") or (r or {}).get("name") or "")
    info = "".join("<td><b>%s</b>：%s</td>" % (html.escape(label(dt, f)), html.escape(names.get(f, str(h.get(f) or ""))))
                   for f in dt.fields if f != "discount")
    rows = "".join(
        "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td class=n>%s</td><td class=n>%s</td>"
        "<td class=n>%s</td></tr>" % (i, html.escape(l["prod_no"]), html.escape(l["color"]), html.escape(l["size"]),
                                      html.escape(l.get("name") or ""), fmt(l["qty"], "n"), fmt(l["price"]),
                                      fmt(l["amount"])) for i, l in enumerate(lines, 1))
    disc = ("　折數 %s%%" % fmt(h["discount"])) if "discount" in dt.fields else ""
    return """<!doctype html><html><head><meta charset="utf-8"><title>%(title)s %(no)s</title>
<style>body{font-family:'Microsoft JhengHei','PingFang TC',sans-serif;margin:24px;color:#111}h1{text-align:center;margin:0}
h2{text-align:center;margin:4px 0 14px;font-weight:normal}table{border-collapse:collapse;width:100%%;font-size:13px}
.info td{padding:3px 8px}.lines th,.lines td{border:1px solid #888;padding:4px 6px}.lines th{background:#eef}
.n{text-align:right}.foot{margin-top:10px;display:flex;justify-content:space-between}
@media print{button{display:none}}</style></head><body>
<button onclick="print()" style="float:right;padding:6px 16px">列印</button>
<h1>%(comp)s</h1><h2>%(title)s</h2>
<table class=info><tr><td><b>單號</b>：%(no)s</td><td><b>日期</b>：%(date)s</td>%(info)s</tr></table>
<table class=lines><tr><th>#</th><th>貨號</th><th>顏色</th><th>尺寸</th><th>品名</th><th>數量</th><th>單價</th>
<th>金額</th></tr>%(rows)s<tr><td colspan=5 class=n><b>合計</b></td><td class=n><b>%(qty)s</b></td><td></td>
<td class=n><b>%(amt)s</b></td></tr></table>
<div class=foot><span>備註：%(memo)s%(disc)s</span><span>經辦：%(by)s　　簽收：＿＿＿＿＿＿</span></div>
</body></html>""" % dict(title=dt.name + "單", no=html.escape(h["doc_no"]), date=dates.roc(h["doc_date"]),
                         comp=html.escape(comp.get("name") or ""), info=info, rows=rows, qty=fmt(h["total_qty"], "n"),
                         amt=fmt(h["total_amt"]), memo=html.escape(h["memo"] or ""), disc=disc,
                         by=html.escape(h["created_by"] or ""))


def open_doc(svc, doc_id):
    path = os.path.join(tempfile.gettempdir(), "zms_doc_%s.html" % doc_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc_html(svc, doc_id))
    webbrowser.open("file:///" + path.replace("\\", "/"))
    return path
