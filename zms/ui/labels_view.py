"""吊牌條碼標籤：選產品（同貨號各顏色尺寸）或從單據帶入數量，預覽後列印。"""
import flet as ft

from .. import labels
from ..doctypes import DOC_TYPES
from .common import Grid, dd, section, tf


class LabelView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        svc = ctx.svc
        self.picks = {}  # (prod_no, color, size) -> 張數
        # 來源一：貨號
        self.pn = tf("貨號", "", width=170, on_submit=lambda e: self.load_variants())
        self.each = tf("每個規格幾張", "1", width=120)
        self.var_box = ft.Column(spacing=4)
        # 來源二：單據
        self.dtype = dd("單據種類", [(d.code, d.name) for d in DOC_TYPES], "PI", width=150, blank=False)
        self.dno = tf("單號", "", width=170, on_submit=lambda e: self.from_doc())
        # 版型
        self.layout = dd("版型", [(k, v[0]) for k, v in labels.LAYOUTS.items()], "tag40x60", width=300, blank=False)
        self.price = dd("印售價", [("1", "售價一"), ("2", "售價二"), ("3", "售價三"), ("0", "不印價格")], "1",
                        width=130, blank=False)
        self.show_co = ft.Checkbox(label="印公司名稱", value=True)
        self.show_sp = ft.Checkbox(label="有特價時印特價（原價劃線）", value=True)
        self.grid = Grid([("prod_no", "貨號", "s", 110), ("color", "顏色", "s", 50), ("size", "尺寸", "s", 50),
                          ("name", "品名", "s", 160), ("code", "條碼內容", "s", 150), ("copies", "張數", "n", 50)],
                         on_pick=self.remove, total_keys=("copies",), height=260)
        super().__init__([section(
            "吊牌條碼標籤",
            ft.Text("條碼為 Code 128：產品資料有填「條碼」就用它，否則印「貨號-顏色-尺寸」，開單時掃描即可帶出商品。",
                    size=12, color=ft.Colors.GREY_700),
            ft.Row([ft.Text("① 依貨號", weight=ft.FontWeight.BOLD), self.pn, self.each,
                    ft.FilledButton("帶出規格", icon=ft.Icons.GRID_ON, on_click=lambda e: self.load_variants())],
                   wrap=True),
            self.var_box,
            ft.Row([ft.Text("② 依單據數量", weight=ft.FontWeight.BOLD), self.dtype, self.dno,
                    ft.FilledButton("帶入", icon=ft.Icons.RECEIPT_LONG, on_click=lambda e: self.from_doc())], wrap=True),
            ft.Divider(),
            ft.Row([ft.Text("要印的標籤（點一下列可移除）", weight=ft.FontWeight.BOLD),
                    ft.TextButton("全部清除", icon=ft.Icons.CLEAR_ALL, on_click=lambda e: self.clear())]),
            self.grid,
            ft.Row([self.layout, self.price, self.show_co, self.show_sp,
                    ft.FilledButton("預覽／列印", icon=ft.Icons.PRINT, on_click=lambda e: self.print_())], wrap=True),
        )], expand=True, scroll=ft.ScrollMode.AUTO)
        self.refresh(False)

    def load_variants(self):
        pn = (self.pn.value or "").strip()
        vs = self.ctx.svc.variants(pn) if pn else []
        if not vs:
            self.ctx.toast("找不到貨號 %s" % pn, True)
            return
        try:
            n = int(self.each.value or 1)
        except ValueError:
            n = 1
        svc = self.ctx.svc
        sizes = svc.sort_sizes([v["size"] for v in vs])
        colors = svc.sort_colors([v["color"] for v in vs])
        have = {(v["color"], v["size"]) for v in vs}
        cn = svc.code_map("color")
        self.fields = {}
        rows = [ft.Row([ft.Container(ft.Text("%s %s" % (pn, vs[0]["name"] or ""), weight=ft.FontWeight.BOLD),
                                     width=180)] + [ft.Container(ft.Text(s, text_align=ft.TextAlign.CENTER,
                                                                         weight=ft.FontWeight.BOLD), width=64)
                                                    for s in sizes])]
        for c in colors:
            cells = [ft.Container(ft.Text("%s %s" % (c, cn.get(c, ""))), width=180)]
            for s in sizes:
                if (c, s) in have:
                    f = ft.TextField(str(n), width=64, dense=True, text_align=ft.TextAlign.RIGHT)
                    self.fields[(pn, c, s)] = f
                    cells.append(f)
                else:
                    cells.append(ft.Container(ft.Text("—", color=ft.Colors.GREY_400), width=64))
            rows.append(ft.Row(cells, spacing=6))
        rows.append(ft.FilledButton("加入標籤清單", icon=ft.Icons.ADD, on_click=lambda e: self.add_fields()))
        self.var_box.controls = [ft.Container(ft.Column([ft.Row([ft.Column(rows, spacing=6)], scroll=ft.ScrollMode.AUTO)]),
                                              padding=10, border=ft.Border.all(1, ft.Colors.GREY_300), border_radius=8)]
        self.update()

    def add_fields(self):
        for k, f in self.fields.items():
            try:
                n = int(f.value or 0)
            except ValueError:
                continue
            if n > 0:
                self.picks[k] = self.picks.get(k, 0) + n
        self.var_box.controls = []
        self.refresh()

    def from_doc(self):
        no = (self.dno.value or "").strip()
        d = self.ctx.svc.db.one("SELECT id FROM docs WHERE doc_type=%s AND doc_no=%s", (self.dtype.value, no))
        if not d:
            self.ctx.toast("找不到單據 %s" % no, True)
            return
        self.add_doc(d["id"])

    def add_doc(self, doc_id):
        _, lines = self.ctx.svc.get_doc(doc_id)
        for l in lines:
            k = (l["prod_no"], l["color"], l["size"])
            self.picks[k] = self.picks.get(k, 0) + abs(int(l["qty"]))
        self.refresh()
        self.ctx.toast("已帶入 %d 筆" % len(lines))

    def remove(self, r):
        self.picks.pop((r["prod_no"], r["color"], r["size"]), None)
        self.refresh()

    def clear(self):
        self.picks = {}
        self.refresh()

    def items(self):
        return self.ctx.svc.label_items([k + (n,) for k, n in self.picks.items()])

    def refresh(self, update=True):
        self.grid.set_rows(self.items())
        if update:
            self.update()

    def print_(self):
        items = self.items()
        if not items:
            self.ctx.toast("請先加入要印的產品", True)
            return
        comp = (self.ctx.svc.company() or {}).get("name") or ""
        labels.open_labels(items, layout=self.layout.value or "tag40x60", price_level=self.price.value or "1",
                           company=comp, show_company=self.show_co.value,
                           show_special=self.show_sp.value)
        self.ctx.toast("已在瀏覽器開啟標籤頁，請選擇標籤印表機列印（邊界設為「無」、縮放 100%）")
