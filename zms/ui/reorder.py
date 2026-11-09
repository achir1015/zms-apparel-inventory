"""補貨調度（舊系統 61～66）：補貨建議、轉貨建議、追加採購建議，並可一鍵產生單據。"""
import flet as ft

from .common import Grid, dd, export_button, section, tf


def _num(field, default):
    try:
        return int((field.value or "").strip() or default)
    except ValueError:
        raise ValueError("%s 要是整數" % field.label)


def _filters(ctx):
    q = tf("貨號／品名", width=150)
    brand = dd("品牌", [(r["code"], r["name"]) for r in ctx.svc.codes("brand")], "", width=130, blank="all")
    season = dd("季別", [(r["code"], r["name"]) for r in ctx.svc.codes("season")], "", width=130, blank="all")
    return q, brand, season


def _hint(text):
    return ft.Container(ft.Text(text, size=12, color=ft.Colors.BLUE_GREY_700), bgcolor=ft.Colors.BLUE_50,
                        padding=10, border_radius=6)


class ReplenishView(ft.Column):
    """補貨建議：總倉 → 店家。"""

    def __init__(self, ctx):
        self.ctx = ctx
        svc = ctx.svc
        self.method = dd("補貨方式", [("sales", "61 依銷售補貨"), ("level", "62 依庫存量補貨"), ("safe", "63 依安全存量補貨")],
                         "sales", width=190, blank=False, on_select=lambda e: self._method())
        whs = svc.options("warehouses")
        self.wh = dd("出貨倉庫", whs, whs[0][0] if whs else "", width=200, blank=False)
        self.shop = dd("店家", svc.options("shops"), "", width=200, blank="all")
        self.days = tf("參考近幾天銷量", "14", width=130)
        self.cover = tf("補到幾天份", "14", width=110)
        self.level = tf("每規格補到幾件", "2", width=130, visible=False)
        self.q, self.brand, self.season = _filters(ctx)
        self.hint = _hint("")
        self.grid = Grid([("sh_no", "店家", "s", 80), ("sh_name", "簡稱", "s", 90), ("prod_no", "貨號", "s", 110),
                          ("color", "顏色", "s", 45), ("size", "尺寸", "s", 45), ("name", "品名", "s", 140),
                          ("sold", "期間銷量", "n", 70), ("stock", "店庫存", "n", 60), ("target", "目標量", "n", 60),
                          ("suggest", "建議量", "n", 60), ("wh_avail", "倉可用", "n", 60), ("alloc", "配貨量", "n", 60)],
                         total_keys=("sold", "suggest", "alloc"))
        self.go_btn = ft.FilledButton("依配貨量產生出貨單", icon=ft.Icons.LOCAL_SHIPPING, on_click=self.make, disabled=True)
        super().__init__([section("補貨建議（總倉 → 店家）",
                                  ft.Row([self.method, self.wh, self.shop, self.days, self.cover, self.level], wrap=True),
                                  ft.Row([self.q, self.brand, self.season,
                                          ft.FilledButton("計算建議", icon=ft.Icons.CALCULATE, on_click=lambda e: self.calc()),
                                          self.go_btn, export_button(ctx, self.grid, "補貨建議")], wrap=True),
                                  self.hint, self.grid)], expand=True)
        self._method(False)

    def _method(self, update=True):
        m = self.method.value or "sales"
        self.days.visible = self.cover.visible = m == "sales"
        self.level.visible = m == "level"
        self.hint.content.value = {
            "sales": "依銷售補貨：目標量＝近 N 天日均銷量 × 補到天數（無條件進位）；建議量＝目標量－店庫存。"
                     "倉庫不夠時，同一規格由銷量高、缺口大的店先配。",
            "level": "依庫存量補貨：倉庫有貨的每個規格，各店都補到指定件數（例如每色每碼 2 件，適合新品鋪貨）。",
            "safe": "依安全存量補貨：店庫存低於產品資料設定的「安全存量」就補足（請先在產品資料填安全存量）。"}[m] + \
            "　產生的出貨單可再到「店家單據 → 出貨」修改。"
        if update:
            self.update()

    def calc(self):
        try:
            args = dict(days=_num(self.days, 14), cover=_num(self.cover, 14), level=_num(self.level, 2))
        except ValueError as e:
            self.ctx.toast(str(e), True)
            return
        rows = self.ctx.guard(self.ctx.svc.replenish_suggest, self.method.value or "sales", self.wh.value or "",
                              [self.shop.value] if self.shop.value else None, q=(self.q.value or "").strip(),
                              brand=self.brand.value or "", season=self.season.value or "", **args)
        if isinstance(rows, list):
            self.grid.set_rows(rows)
            self.go_btn.disabled = not any(r["alloc"] for r in rows)
            self.update()

    def make(self, e):
        rows = self.grid.rows_data
        n = sum(r["alloc"] for r in rows)
        shops = len({r["sh_no"] for r in rows if r["alloc"]})

        def yes():
            nos = self.ctx.guard(self.ctx.svc.make_ship_docs, self.wh.value, rows)
            if isinstance(nos, list):
                self.ctx.toast("已產生 %d 張出貨單：%s" % (len(nos), "、".join(nos)))
                self.calc()
        self.ctx.confirm("產生出貨單", "從倉庫 %s 出貨給 %d 家店，共 %d 件，確定產生？" % (self.wh.value, shops, n), yes, "產生")


class TransferView(ft.Column):
    """轉貨建議：店家 ↔ 店家。"""

    def __init__(self, ctx):
        self.ctx = ctx
        self.days = tf("參考近幾天銷量", "30", width=130)
        self.cover = tf("補到幾天份", "14", width=110)
        self.keep = tf("每規格至少留幾件", "1", width=140)
        self.q, self.brand, self.season = _filters(ctx)
        self.grid = Grid([("from_sh", "調出店", "s", 80), ("from_name", "簡稱", "s", 80), ("to_sh", "調入店", "s", 80),
                          ("to_name", "簡稱", "s", 80), ("prod_no", "貨號", "s", 110), ("color", "顏色", "s", 45),
                          ("size", "尺寸", "s", 45), ("name", "品名", "s", 130), ("qty", "建議調撥", "n", 70),
                          ("from_stock", "調出店庫存", "n", 80), ("from_sold", "調出店銷量", "n", 80),
                          ("to_stock", "調入店庫存", "n", 80), ("to_sold", "調入店銷量", "n", 80)], total_keys=("qty",))
        self.go_btn = ft.FilledButton("產生調撥單", icon=ft.Icons.SYNC_ALT, on_click=self.make, disabled=True)
        super().__init__([section("轉貨建議（店家 ↔ 店家）",
                                  ft.Row([self.days, self.cover, self.keep, self.q, self.brand, self.season], wrap=True),
                                  ft.Row([ft.FilledButton("計算建議", icon=ft.Icons.CALCULATE, on_click=lambda e: self.calc()),
                                          self.go_btn, export_button(ctx, self.grid, "轉貨建議")]),
                                  _hint("目標量＝近 N 天日均銷量 × 補到天數。庫存超過目標量（且超過保留件數）的店是「多」，"
                                        "庫存低於目標量的店是「缺」；同一規格把多的調給缺的，賣得快的店優先。"
                                        "　產生後每一組「調出店→調入店」一張店家調撥單。"),
                                  self.grid)], expand=True)

    def calc(self):
        try:
            args = dict(days=_num(self.days, 30), cover=_num(self.cover, 14), keep=_num(self.keep, 1))
        except ValueError as e:
            self.ctx.toast(str(e), True)
            return
        rows = self.ctx.guard(self.ctx.svc.transfer_suggest, None, q=(self.q.value or "").strip(),
                              brand=self.brand.value or "", season=self.season.value or "", **args)
        if isinstance(rows, list):
            self.grid.set_rows(rows)
            self.go_btn.disabled = not rows
            self.update()

    def make(self, e):
        rows = self.grid.rows_data
        pairs = len({(r["from_sh"], r["to_sh"]) for r in rows})

        def yes():
            nos = self.ctx.guard(self.ctx.svc.make_move_docs, rows)
            if isinstance(nos, list):
                self.ctx.toast("已產生 %d 張調撥單：%s" % (len(nos), "、".join(nos)))
                self.calc()
        self.ctx.confirm("產生調撥單", "共 %d 組店家、%d 件，確定產生？" % (pairs, sum(r["qty"] for r in rows)), yes, "產生")


class RecutView(ft.Column):
    """追加採購／追裁建議（舊系統 65）。"""

    def __init__(self, ctx):
        self.ctx = ctx
        svc = ctx.svc
        self.days = tf("參考近幾天銷量", "30", width=130)
        self.cover = tf("備貨幾天份", "30", width=110)
        self.q, self.brand, self.season = _filters(ctx)
        whs = svc.options("warehouses")
        self.wh = dd("進貨倉庫", whs, whs[0][0] if whs else "", width=200, blank=False)
        self.vendor = dd("廠商", svc.options("vendors"), "", width=200)
        self.grid = Grid([("prod_no", "貨號", "s", 110), ("color", "顏色", "s", 45), ("size", "尺寸", "s", 45),
                          ("name", "品名", "s", 150), ("sold", "期間銷量", "n", 70), ("stock", "全公司庫存", "n", 80),
                          ("pending", "已訂未進", "n", 70), ("days_left", "可賣天數", "n", 70), ("target", "目標量", "n", 60),
                          ("suggest", "建議追加", "n", 70)], total_keys=("sold", "stock", "suggest"))
        self.go_btn = ft.FilledButton("產生採購單", icon=ft.Icons.SHOPPING_CART, on_click=self.make, disabled=True)
        super().__init__([section("追加採購／追裁建議",
                                  ft.Row([self.days, self.cover, self.q, self.brand, self.season,
                                          ft.FilledButton("計算建議", icon=ft.Icons.CALCULATE,
                                                          on_click=lambda e: self.calc())], wrap=True),
                                  ft.Row([self.wh, self.vendor, self.go_btn, export_button(ctx, self.grid, "追加採購建議")],
                                         wrap=True),
                                  _hint("使用時機：季初裁剪、熱賣款需求增加時。目標量＝近 N 天全公司日均銷量 × 備貨天數；"
                                        "建議追加＝目標量－（倉庫＋所有店家庫存）－已採購未進貨。「可賣天數」＝現有庫存還能賣幾天。"),
                                  self.grid)], expand=True)

    def calc(self):
        try:
            args = dict(days=_num(self.days, 30), cover=_num(self.cover, 30))
        except ValueError as e:
            self.ctx.toast(str(e), True)
            return
        rows = self.ctx.guard(self.ctx.svc.recut_suggest, q=(self.q.value or "").strip(), brand=self.brand.value or "",
                              season=self.season.value or "", **args)
        if isinstance(rows, list):
            self.grid.set_rows(rows)
            self.go_btn.disabled = not rows
            self.update()

    def make(self, e):
        if not self.vendor.value:
            self.ctx.toast("請先選廠商", True)
            return
        rows = self.grid.rows_data

        def yes():
            no = self.ctx.guard(self.ctx.svc.make_purchase_doc, self.wh.value, self.vendor.value, rows)
            if isinstance(no, str):
                self.ctx.toast("已產生採購單 %s（可在「倉庫單據 → 採購」修改）" % no)
                self.calc()
        self.ctx.confirm("產生採購單", "向廠商 %s 採購 %d 件，確定產生？" % (self.vendor.value,
                                                                  sum(r["suggest"] for r in rows)), yes, "產生")
