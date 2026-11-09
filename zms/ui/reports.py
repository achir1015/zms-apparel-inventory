"""查詢報表：庫存、進銷存、銷售分析、訂單／採購追蹤、產品異動明細。"""
import flet as ft

from .. import dates
from ..doctypes import BY_CODE
from .common import Grid, date_field, dd, export_button, section, tf


class StockView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.kind = dd("位置", [("W", "倉庫"), ("S", "店家")], "W", width=120, blank=False,
                       on_select=lambda e: self._kind())
        self.loc = dd("倉庫", ctx.svc.options("warehouses"), "", width=220, blank="all")
        self.q = tf("貨號／品名", width=200, on_submit=lambda e: self.load())
        self.brand = dd("品牌", [(r["code"], r["name"]) for r in ctx.svc.codes("brand")], "", width=150, blank="all")
        self.nz = ft.Checkbox(label="不顯示零庫存", value=True)
        self.grid = Grid([("loc_no", "代號", "s", 70), ("loc_name", "名稱", "s", 120), ("prod_no", "貨號", "s", 120),
                          ("color", "顏色", "s", 50), ("size", "尺寸", "s", 50), ("name", "品名", "s", 180),
                          ("qty", "庫存", "n", 70), ("cost", "成本", "n", 70), ("cost_amt", "成本金額", "n", 100),
                          ("sale_amt", "售價金額", "n", 100)], total_keys=("qty", "cost_amt", "sale_amt"))
        super().__init__([section("庫存查詢", ft.Row([self.kind, self.loc, self.q, self.brand, self.nz,
                                                    ft.FilledButton("查詢", icon=ft.Icons.SEARCH,
                                                                    on_click=lambda e: self.load()),
                                                    export_button(ctx, self.grid, "庫存")], wrap=True), self.grid)],
                         expand=True)
        self.load(False)

    def _kind(self):
        w = self.kind.value == "W"
        self.loc.label = "倉庫" if w else "店家"
        from .common import dd as _dd
        new = _dd(self.loc.label, self.ctx.svc.options("warehouses" if w else "shops"), "", width=220, blank="all")
        self.loc.options, self.loc.value = new.options, ""
        self.load()

    def load(self, update=True):
        rows = self.ctx.guard(self.ctx.svc.stock_query, self.kind.value or "W", self.loc.value or "",
                              (self.q.value or "").strip(), self.brand.value or "", self.nz.value)
        if isinstance(rows, list):
            self.grid.set_rows(rows)
        if update:
            self.update()


class PeriodView(ft.Column):
    """進銷存查詢（舊 D2 / E3 / E6）。"""

    def __init__(self, ctx):
        self.ctx = ctx
        t = dates.today()
        self.kind = dd("位置", [("W", "倉庫"), ("S", "店家")], "W", width=120, blank=False,
                       on_select=lambda e: self._kind())
        self.loc = dd("倉庫", ctx.svc.options("warehouses"), "", width=220, blank="all")
        self.d1, self.d2 = date_field("起日", t.replace(day=1)), date_field("迄日", t)
        self.q = tf("貨號", width=160, on_submit=lambda e: self.load())
        self.holder = ft.Column(expand=True)
        self.grid = None
        self.exp = ft.Row()
        super().__init__([section("進銷存查詢", ft.Row([self.kind, self.loc, self.d1, self.d2, self.q,
                                                     ft.FilledButton("查詢", icon=ft.Icons.SEARCH,
                                                                     on_click=lambda e: self.load()), self.exp],
                                                    wrap=True), self.holder)], expand=True)

    def _kind(self):
        w = self.kind.value == "W"
        self.loc.label = "倉庫" if w else "店家"
        new = dd(self.loc.label, self.ctx.svc.options("warehouses" if w else "shops"), "", width=220, blank="all")
        self.loc.options, self.loc.value = new.options, ""
        self.update()

    def load(self):
        r = self.ctx.guard(self.ctx.svc.period_summary, self.kind.value or "W", self.loc.value or "",
                           self.d1.value, self.d2.value, (self.q.value or "").strip())
        if not isinstance(r, tuple):
            return
        rows, used = r
        cols = [("prod_no", "貨號", "s", 110), ("color", "顏色", "s", 45), ("size", "尺寸", "s", 45),
                ("name", "品名", "s", 150), ("opening", "期初", "n", 60)]
        cols += [(t, BY_CODE[t].name.replace("倉庫", "").replace("店家", "").replace("公司", ""), "n", 60) for t in used]
        cols += [("closing", "期末", "n", 60)]
        self.grid = Grid(cols, total_keys=tuple(["opening"] + used + ["closing"]))
        self.grid.set_rows(rows)
        self.holder.controls = [self.grid]
        self.exp.controls = [export_button(self.ctx, self.grid, "進銷存")]
        self.update()


class SalesView(ft.Column):
    """銷售分析（舊 E7/E8/EA/EF/C8 等）。"""

    def __init__(self, ctx):
        self.ctx = ctx
        t = dates.today()
        self.by = dd("分析方式", [("product", "依貨號（暢銷排行）"), ("shop", "依店家"), ("brand", "依品牌"),
                               ("season", "依年度季別"), ("style", "依款式"), ("size", "依尺寸"), ("month", "依月份"), ("person", "依人員")], "product", width=200, blank=False)
        self.shop = dd("店家", ctx.svc.options("shops"), "", width=200, blank="all")
        self.d1, self.d2 = date_field("起日", t.replace(day=1)), date_field("迄日", t)
        self.grid = Grid([("k", "代號", "s", 120), ("n", "名稱", "s", 180), ("qty", "數量", "n", 70),
                          ("amt", "銷售金額", "n", 110), ("cost", "成本", "n", 100), ("profit", "毛利", "n", 100),
                          ("rate", "毛利率%", "n", 70)], total_keys=("qty", "amt", "cost", "profit"))
        super().__init__([section("銷售分析", ft.Row([self.by, self.shop, self.d1, self.d2,
                                                    ft.FilledButton("查詢", icon=ft.Icons.SEARCH,
                                                                    on_click=lambda e: self.load()),
                                                    export_button(ctx, self.grid, "銷售分析")], wrap=True),
                                  ft.Text("資料來源：店家銷貨單", size=12, color=ft.Colors.GREY_600), self.grid)],
                         expand=True)

    def load(self):
        rows = self.ctx.guard(self.ctx.svc.sales_analysis, self.d1.value, self.d2.value, self.by.value or "product",
                              self.shop.value or "")
        if isinstance(rows, list):
            self.grid.set_rows(rows)
            self.update()


class TrackView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.kind = dd("追蹤", [("GE", "公司已訂未進（採購→進貨）"), ("OR", "店家訂單出貨狀況（訂單→出貨）")], "GE",
                       width=300, blank=False, on_select=lambda e: self.load())
        self.only = ft.Checkbox(label="只顯示未完成", value=True, on_change=lambda e: self.load())
        self.grid = Grid([("doc_no", "單號", "s", 120), ("doc_date", "日期", "s", 80), ("party", "對象", "s", 90),
                          ("prod_no", "貨號", "s", 110), ("color", "顏色", "s", 45), ("size", "尺寸", "s", 45),
                          ("ordered", "訂購量", "n", 70), ("done", "已交量", "n", 70), ("left", "未交量", "n", 70)],
                         total_keys=("ordered", "done", "left"))
        super().__init__([section("訂單／採購追蹤", ft.Row([self.kind, self.only, export_button(ctx, self.grid, "追蹤")]),
                                  ft.Text("進貨單的「採購單號」、出貨單的「訂單號碼」填入對應單號即可沖銷", size=12,
                                          color=ft.Colors.GREY_600), self.grid)], expand=True)
        self.load(False)

    def load(self, update=True):
        rows = self.ctx.svc.tracking(self.kind.value or "GE")
        for r in rows:
            r["left"] = int(r["ordered"]) - int(r["done"])
            r["party"] = r["ma_no"] or r["sh_no"]
        if self.only.value:
            rows = [r for r in rows if r["left"] > 0]
        self.grid.set_rows(rows)
        if update:
            self.update()


class HistoryView(ft.Column):
    """產品異動明細（舊 E5 產品進出明細）。"""

    def __init__(self, ctx):
        self.ctx = ctx
        self.p = tf("貨號", width=160, on_submit=lambda e: self.load())
        self.c = tf("顏色", width=80)
        self.s = tf("尺寸", width=80)
        self.d1, self.d2 = tf("起日", "", width=120), tf("迄日", "", width=120)
        self.grid = Grid([("doc_date", "日期", "s", 80), ("doc_name", "單據", "s", 80), ("doc_no", "單號", "s", 120),
                          ("loc", "位置", "s", 90), ("color", "顏色", "s", 45), ("size", "尺寸", "s", 45),
                          ("qty", "增減", "n", 70), ("memo", "備註", "s", 200)], total_keys=("qty",))
        super().__init__([section("產品異動明細", ft.Row([self.p, self.c, self.s, self.d1, self.d2,
                                                      ft.FilledButton("查詢", icon=ft.Icons.SEARCH,
                                                                      on_click=lambda e: self.load()),
                                                      export_button(ctx, self.grid, "產品異動")], wrap=True),
                                  self.grid)], expand=True)

    def load(self):
        if not (self.p.value or "").strip():
            self.ctx.toast("請輸入貨號", True)
            return
        rows = self.ctx.guard(self.ctx.svc.product_history, self.p.value.strip(), (self.c.value or "").strip(),
                              (self.s.value or "").strip(), self.d1.value or None, self.d2.value or None)
        if isinstance(rows, list):
            for r in rows:
                r["doc_name"] = BY_CODE[r["doc_type"]].name
                r["loc"] = ("倉" if r["loc_type"] == "W" else "店") + " " + r["loc_no"]
            self.grid.set_rows(rows)
            self.update()


class StockMatrixView(ft.Column):
    """庫存尺寸分布（服飾業）：每個貨號一張「位置／顏色 × 尺寸」表，一眼看出缺哪個尺寸。"""

    def __init__(self, ctx):
        self.ctx = ctx
        svc = ctx.svc
        self.kind = dd("位置", [("W", "倉庫"), ("S", "店家")], "W", width=120, blank=False,
                       on_select=lambda e: self._kind())
        self.loc = dd("倉庫", svc.options("warehouses"), "", width=200, blank="all")
        self.q = tf("貨號／品名", width=180, on_submit=lambda e: self.load())
        self.brand = dd("品牌", [(r["code"], r["name"]) for r in svc.codes("brand")], "", width=140, blank="all")
        self.year = tf("年度", "", width=90)
        self.season = dd("季別", [(r["code"], r["name"]) for r in svc.codes("season")], "", width=130, blank="all")
        self.nz = ft.Checkbox(label="不顯示零庫存", value=True)
        self.body = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self.info = ft.Text("", size=12, color=ft.Colors.GREY_700)
        super().__init__([section("庫存尺寸分布", ft.Row([self.kind, self.loc, self.q, self.brand, self.year, self.season,
                                                     self.nz, ft.FilledButton("查詢", icon=ft.Icons.SEARCH,
                                                                              on_click=lambda e: self.load())],
                                                    wrap=True),
                                  ft.Text("每個貨號一張表：列＝位置／顏色、欄＝尺寸；紅字＝負庫存、灰底＝缺貨（0）",
                                          size=12, color=ft.Colors.GREY_600), self.info, self.body)], expand=True)
        self.load(False)

    def _kind(self):
        w = self.kind.value == "W"
        self.loc.label = "倉庫" if w else "店家"
        new = dd(self.loc.label, self.ctx.svc.options("warehouses" if w else "shops"), "", width=200, blank="all")
        self.loc.options, self.loc.value = new.options, ""
        self.load()

    def load(self, update=True):
        data = self.ctx.guard(self.ctx.svc.stock_matrix, self.kind.value or "W", self.loc.value or "",
                              (self.q.value or "").strip(), self.brand.value or "", self.season.value or "",
                              (self.year.value or "").strip(), self.nz.value, 120)
        if not isinstance(data, list):
            return
        cards = []
        for p in data:
            cols = [ft.DataColumn(ft.Text("位置")), ft.DataColumn(ft.Text("顏色"))] + [
                ft.DataColumn(ft.Text(s, weight=ft.FontWeight.BOLD), numeric=True) for s in p["sizes"]] + [
                ft.DataColumn(ft.Text("合計", weight=ft.FontWeight.BOLD), numeric=True)]
            rows = []
            for l in p["lines"]:
                cells = [ft.DataCell(ft.Text("%s %s" % (l["loc"], l["loc_name"]), no_wrap=True)),
                         ft.DataCell(ft.Text("%s %s" % (l["color"], l["color_name"]), no_wrap=True))]
                for s in p["sizes"]:
                    q = l["cells"].get(s)
                    if q is None:
                        cells.append(ft.DataCell(ft.Text("—", color=ft.Colors.GREY_400)))
                    else:
                        cells.append(ft.DataCell(ft.Container(
                            ft.Text(str(q), color=ft.Colors.RED if q < 0 else None,
                                    weight=ft.FontWeight.BOLD if q > 0 else None),
                            bgcolor=ft.Colors.GREY_200 if q == 0 else None, padding=ft.Padding.symmetric(horizontal=6))))
                cells.append(ft.DataCell(ft.Text(str(l["total"]), weight=ft.FontWeight.BOLD)))
                rows.append(ft.DataRow(cells=cells))
            if len(p["lines"]) > 1:
                rows.append(ft.DataRow(color=ft.Colors.BLUE_50, cells=[
                    ft.DataCell(ft.Text("合計", weight=ft.FontWeight.BOLD)), ft.DataCell(ft.Text(""))] + [
                    ft.DataCell(ft.Text(str(p["col_tot"][s]), weight=ft.FontWeight.BOLD)) for s in p["sizes"]] + [
                    ft.DataCell(ft.Text(str(p["total"]), weight=ft.FontWeight.BOLD))]))
            table = ft.DataTable(columns=cols, rows=rows, heading_row_height=34, data_row_min_height=30,
                                 data_row_max_height=34, column_spacing=16, heading_row_color=ft.Colors.BLUE_50,
                                 border=ft.Border.all(1, ft.Colors.GREY_300))
            cards.append(ft.Container(ft.Column([
                ft.Text("%s　%s　（共 %d 件）" % (p["prod_no"], p["name"], p["total"]), size=15,
                        weight=ft.FontWeight.BOLD),
                ft.Row([table], scroll=ft.ScrollMode.AUTO)], spacing=6),
                padding=12, bgcolor=ft.Colors.WHITE, border_radius=8, border=ft.Border.all(1, ft.Colors.GREY_200)))
        self.body.controls = cards or [ft.Text("沒有符合的庫存", color=ft.Colors.GREY)]
        self.info.value = "共 %d 個貨號%s" % (len(data), "（只顯示前 120 個，請加條件縮小範圍）" if len(data) >= 120 else "")
        if update:
            self.update()
