"""手機版（iPhone／Android 直立）：營運總覽、庫存查詢、門市銷貨、盤點。

資料透過 Wi-Fi 連到電腦上的進銷存資料庫；功能依使用者權限顯示。
"""
from decimal import Decimal

import flet as ft

from .. import dates
from ..services import BizError, D, money
from .common import PRIMARY, Ctx, fmt


def _card(*controls, padding=12):
    return ft.Container(ft.Column(list(controls), spacing=6), padding=padding, bgcolor=ft.Colors.WHITE,
                        border_radius=12, border=ft.Border.all(1, ft.Colors.GREY_200))


def _safe_update(ctrl):
    """元件還沒放上畫面時呼叫 update 會出錯 → 略過。"""
    try:
        ctrl.update()
    except RuntimeError:
        pass


def _title(text):
    return ft.Text(text, size=16, weight=ft.FontWeight.BOLD, color=PRIMARY)


def _code_field(on_submit, label="貨號或條碼"):
    return ft.TextField(label=label, dense=True, expand=True, on_submit=on_submit, prefix_icon=ft.Icons.QR_CODE_SCANNER,
                        autocorrect=False, enable_suggestions=False, capitalization=ft.TextCapitalization.CHARACTERS)


class MobileShell:
    def __init__(self, app):
        self.app, self.page, self.svc = app, app.page, app.svc
        self.ctx = Ctx(self.page, self.svc)
        tabs = []
        if self.svc.can("Q3") or self.svc.can("Q1"):
            tabs.append(("總覽", ft.Icons.DASHBOARD_OUTLINED, OverviewTab))
        if self.svc.can("Q1"):
            tabs.append(("庫存", ft.Icons.INVENTORY_2_OUTLINED, StockTab))
        if self.svc.can("D_TA"):
            tabs.append(("銷貨", ft.Icons.POINT_OF_SALE, SalesTab))
        if self.svc.can("D_CK") or self.svc.can("D_ST"):
            tabs.append(("盤點", ft.Icons.FACT_CHECK_OUTLINED, StocktakeTab))
        self.tabs = tabs
        self.views = {}

    def show(self):
        p = self.page
        p.controls.clear()
        if not self.tabs:
            p.add(ft.Text("您的帳號沒有手機版可用的功能，請管理員在電腦版開啟權限。"))
            p.update()
            return
        self.body = ft.Container(expand=True, padding=ft.Padding.only(left=10, right=10, top=6))
        self.nav = ft.NavigationBar(destinations=[ft.NavigationBarDestination(icon=ic, label=t) for t, ic, _ in self.tabs],
                                    selected_index=0, on_change=lambda e: self.select(e.control.selected_index),
                                    bgcolor=ft.Colors.WHITE, height=64)
        bar = ft.Container(ft.Row([ft.Text("資料助秘 服飾業進銷存", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE,
                                           expand=True),
                                   ft.Text(self.svc.user["name"], color=ft.Colors.WHITE, size=13),
                                   ft.IconButton(ft.Icons.LOGOUT, icon_color=ft.Colors.WHITE, tooltip="登出",
                                                 on_click=lambda e: self.app.logout())]),
                           bgcolor=PRIMARY, padding=ft.Padding.only(left=14, right=4, top=8, bottom=8))
        p.add(ft.SafeArea(ft.Column([bar, self.body, self.nav], spacing=0, expand=True), expand=True))
        self.select(0)

    def select(self, i):
        name, _, cls = self.tabs[i]
        if name not in self.views:     # 保留各分頁狀態（例如銷貨開到一半）
            self.views[name] = cls(self)
        self.body.content = self.views[name]
        self.page.update()


# ------------------------------------------------------------ 共用：選規格
def pick_variant(shell, prod_no, on_pick, loc_type=None, loc_no=None, title="選擇顏色尺寸"):
    svc, p = shell.svc, shell.page
    m = svc.matrix_for(prod_no, loc_type, loc_no)
    if not m:
        shell.ctx.toast("找不到貨號 %s" % prod_no, True)
        return
    rows = []
    for c in m["colors"]:
        btns = []
        for s in m["sizes"]:
            v = m["variants"].get((c, s))
            if not v:
                continue
            st = m["stock"].get((c, s))
            label = s + ("\n庫%d" % st if st is not None and loc_type else "")
            btns.append(ft.OutlinedButton(label, width=64, height=52 if loc_type else 40,
                                          on_click=lambda e, v=v: (p.pop_dialog(), on_pick(v))))
        rows.append(ft.Column([ft.Text("%s %s" % (c, m["color_names"].get(c, "")), weight=ft.FontWeight.BOLD),
                               ft.Row(btns, wrap=True, spacing=6, run_spacing=6)], spacing=4))
    p.show_dialog(ft.AlertDialog(title=ft.Text("%s　%s" % (prod_no, m["name"] or ""), size=16),
                                 content=ft.Column(rows, scroll=ft.ScrollMode.AUTO, tight=True, spacing=10),
                                 actions=[ft.TextButton("取消", on_click=lambda e: p.pop_dialog())]))


def resolve(shell, code, on_product, loc_type=None, loc_no=None):
    """掃條碼／輸入貨號：唯一商品直接回傳；只有貨號就跳出規格選單。"""
    code = (code or "").strip()
    if not code:
        return
    svc = shell.svc
    p = svc.product_by_code(code)
    if p:
        on_product(p)
    elif svc.variants(code.upper()) or svc.variants(code):
        pick_variant(shell, code if svc.variants(code) else code.upper(), on_product, loc_type, loc_no)
    else:
        rows = svc.find_products(code, limit=30)
        if not rows:
            shell.ctx.toast("找不到：%s" % code, True)
            return
        pns = sorted({r["prod_no"] for r in rows})
        if len(pns) == 1:
            pick_variant(shell, pns[0], on_product, loc_type, loc_no)
            return
        pg = shell.page
        pg.show_dialog(ft.AlertDialog(
            title=ft.Text("找到多個貨號"),
            content=ft.Column([ft.ListTile(title=ft.Text(pn), subtitle=ft.Text(next(r["name"] for r in rows if r["prod_no"] == pn) or ""),
                                           on_click=lambda e, pn=pn: (pg.pop_dialog(),
                                                                      pick_variant(shell, pn, on_product, loc_type, loc_no)))
                               for pn in pns[:20]], scroll=ft.ScrollMode.AUTO, tight=True),
            actions=[ft.TextButton("取消", on_click=lambda e: pg.pop_dialog())]))


# ------------------------------------------------------------ 營運總覽
class OverviewTab(ft.Column):
    def __init__(self, shell):
        self.shell = shell
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)
        self.refresh()

    def refresh(self, e=None):
        svc = self.shell.svc
        t = dates.today()
        d = svc.dashboard()
        today = svc.sales_analysis(t, t, by="shop")
        month = svc.sales_analysis(t.replace(day=1), t, by="shop")
        top = svc.sales_analysis(t.replace(day=1), t, by="product", top=10)

        def kpi(label, value, icon, color):
            return ft.Container(ft.Column([ft.Row([ft.Icon(icon, size=18, color=color), ft.Text(label, size=12)]),
                                           ft.Text(value, size=20, weight=ft.FontWeight.BOLD)], spacing=2),
                                padding=10, bgcolor=ft.Colors.WHITE, border_radius=10, col=6,
                                border=ft.Border.all(1, ft.Colors.GREY_200))
        t_amt = sum(D(r["amt"]) for r in today)
        t_qty = sum(int(r["qty"]) for r in today)
        self.controls = [
            ft.Row([_title("營運總覽　%s" % dates.roc(t)),
                    ft.IconButton(ft.Icons.REFRESH, on_click=self.refresh, tooltip="重新整理")],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ResponsiveRow([kpi("今日銷售", fmt(t_amt), ft.Icons.TODAY, ft.Colors.GREEN),
                              kpi("今日件數", fmt(t_qty, "n"), ft.Icons.SHOPPING_BAG, ft.Colors.TEAL),
                              kpi("本月銷售", fmt(d["month_sales"]), ft.Icons.CALENDAR_MONTH, ft.Colors.BLUE),
                              kpi("本月出貨", fmt(d["month_ship"]), ft.Icons.LOCAL_SHIPPING, ft.Colors.INDIGO),
                              kpi("倉庫庫存", fmt(d["wh_qty"]), ft.Icons.WAREHOUSE, ft.Colors.BROWN),
                              kpi("店家庫存", fmt(d["sh_qty"]), ft.Icons.STOREFRONT, ft.Colors.DEEP_ORANGE)],
                             spacing=8, run_spacing=8),
            _card(_title("本月各店業績"), *([ft.Row([ft.Text("%s %s" % (r["k"], r["n"] or ""), expand=True, no_wrap=True),
                                                  ft.Text(fmt(r["qty"], "n") + " 件", width=60, text_align=ft.TextAlign.RIGHT),
                                                  ft.Text(fmt(r["amt"]), width=90, text_align=ft.TextAlign.RIGHT,
                                                          weight=ft.FontWeight.BOLD)]) for r in month]
                                           or [ft.Text("本月尚無銷售", color=ft.Colors.GREY)])),
            _card(_title("本月暢銷前 10"), *([ft.Row([ft.Text("%d." % i, width=24), ft.Text(r["k"], width=90),
                                                    ft.Text(r["n"] or "", expand=True, no_wrap=True, size=13),
                                                    ft.Text(fmt(r["qty"], "n"), width=44, text_align=ft.TextAlign.RIGHT)])
                                            for i, r in enumerate(top, 1)] or [ft.Text("本月尚無銷售", color=ft.Colors.GREY)])),
        ]
        if e:
            self.update()


# ------------------------------------------------------------ 庫存查詢
class StockTab(ft.Column):
    def __init__(self, shell):
        self.shell = shell
        self.code = _code_field(lambda e: self.search())
        self.kind = ft.SegmentedButton(segments=[ft.Segment(value="S", label=ft.Text("店家")),
                                                 ft.Segment(value="W", label=ft.Text("倉庫"))],
                                       selected=["S"], on_change=lambda e: self.search())
        self.result = ft.Column(spacing=10)
        super().__init__([ft.Row([self.code, ft.IconButton(ft.Icons.SEARCH, on_click=lambda e: self.search())]),
                          self.kind, self.result], scroll=ft.ScrollMode.AUTO, expand=True, spacing=10)

    def search(self):
        code = (self.code.value or "").strip()
        if not code:
            return
        svc = self.shell.svc
        p = svc.product_by_code(code)
        pn = p["prod_no"] if p else (code if svc.variants(code) else (code.upper() if svc.variants(code.upper()) else None))
        if not pn:
            rows = svc.find_products(code, limit=1)
            pn = rows[0]["prod_no"] if rows else None
        if not pn:
            self.result.controls = [ft.Text("找不到：%s" % code, color=ft.Colors.RED)]
            self.update()
            return
        vs = svc.variants(pn)
        v0 = vs[0]
        sp = svc.special_for(v0, "")
        price = "售價 %s" % fmt(v0["price1"])
        if sp:
            spv = sp["special_price"] if sp["special_price"] is not None else money(D(v0["price1"]) * D(sp["discount"]) / 100)
            price += "　特價 %s（至 %s）" % (fmt(spv), dates.roc(sp["end_date"]))
        kind = (self.kind.selected or ["S"])[0]
        data = [x for x in svc.stock_matrix(kind, "", q=pn, nonzero=False) if x["prod_no"] == pn]
        cards = [_card(ft.Text("%s　%s" % (pn, v0["name"] or ""), size=17, weight=ft.FontWeight.BOLD),
                       ft.Text(price, color=ft.Colors.RED_700 if sp else None),
                       ft.Text("%d 個規格" % len(vs), size=12, color=ft.Colors.GREY_700))]
        if not data:
            cards.append(ft.Text("%s都沒有這個貨號的庫存" % ("店家" if kind == "S" else "倉庫"), color=ft.Colors.GREY))
        for x in data:
            by_loc = {}
            for l in x["lines"]:
                by_loc.setdefault((l["loc"], l["loc_name"]), []).append(l)
            for (loc, lname), lines in by_loc.items():
                head = [ft.DataColumn(ft.Text("顏色"))] + [ft.DataColumn(ft.Text(s), numeric=True) for s in x["sizes"]]
                rows = [ft.DataRow(cells=[ft.DataCell(ft.Text(l["color"] + (" " + l["color_name"] if l["color_name"] else ""),
                                                              no_wrap=True))] +
                                   [ft.DataCell(ft.Text("" if l["cells"].get(s) is None else str(l["cells"][s]),
                                                        color=ft.Colors.RED if (l["cells"].get(s) or 0) < 0 else None,
                                                        weight=ft.FontWeight.BOLD if (l["cells"].get(s) or 0) > 0 else None))
                                    for s in x["sizes"]]) for l in lines]
                tot = sum(l["total"] for l in lines)
                cards.append(_card(ft.Text("%s %s　（%d 件）" % (loc, lname, tot), weight=ft.FontWeight.BOLD),
                                   ft.Row([ft.DataTable(columns=head, rows=rows, column_spacing=14, heading_row_height=30,
                                                        data_row_min_height=28, data_row_max_height=32,
                                                        horizontal_margin=6)], scroll=ft.ScrollMode.AUTO), padding=8))
        self.result.controls = cards
        self.update()


# ------------------------------------------------------------ 明細清單（銷貨、盤點共用）
class LineList(ft.Column):
    def __init__(self, on_change, show_price=True):
        self.on_change, self.show_price = on_change, show_price
        self.lines = []   # dict(p, qty, price, memo)
        super().__init__(spacing=6)

    def add(self, p, qty=1, price=None, memo=""):
        for l in self.lines:
            if (l["p"]["prod_no"], l["p"]["color"], l["p"]["size"]) == (p["prod_no"], p["color"], p["size"]):
                l["qty"] += qty
                self.render()
                return
        self.lines.insert(0, dict(p=p, qty=qty, price=price, memo=memo))
        self.render()

    def _qty(self, l, d):
        l["qty"] += d
        if l["qty"] <= 0:
            self.lines.remove(l)
        self.render()

    def render(self):
        rows = []
        for l in self.lines:
            p = l["p"]
            sub = "%s %s / %s" % (p["color"], p.get("color_name") or "", p["size"])
            if self.show_price:
                sub += "　@%s" % fmt(l["price"])
            tag = [ft.Container(ft.Text(l["memo"][:4], size=10, color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_400,
                                padding=ft.Padding.symmetric(horizontal=4), border_radius=4)] if l.get("memo") else []
            rows.append(ft.Container(ft.Row([
                ft.Column([ft.Row([ft.Text(p["prod_no"], weight=ft.FontWeight.BOLD)] + tag, spacing=6),
                           ft.Text(p.get("name") or "", size=12, no_wrap=True), ft.Text(sub, size=12, color=ft.Colors.GREY_700)],
                          spacing=0, expand=True),
                ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, on_click=lambda e, l=l: self._qty(l, -1)),
                ft.Text(str(l["qty"]), size=18, weight=ft.FontWeight.BOLD, width=34, text_align=ft.TextAlign.CENTER),
                ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, on_click=lambda e, l=l: self._qty(l, 1))], spacing=0),
                padding=ft.Padding.only(left=10, top=4, bottom=4), bgcolor=ft.Colors.WHITE, border_radius=10,
                border=ft.Border.all(1, ft.Colors.GREY_200)))
        self.controls = rows
        self.on_change()

    def clear(self):
        self.lines = []
        self.render()


def _shop_dd(shell, value, on_select, kind="S"):
    svc = shell.svc
    opts = svc.options("shops" if kind == "S" else "warehouses")
    return ft.Dropdown(label="店家" if kind == "S" else "倉庫", value=value or (opts[0][0] if opts else None), dense=True,
                       options=[ft.DropdownOption(key=k, text=t) for k, t in opts], expand=True, on_select=on_select)


# ------------------------------------------------------------ 門市銷貨
class SalesTab(ft.Column):
    def __init__(self, shell):
        self.shell = shell
        cfg = shell.app.cfg
        self.shop = _shop_dd(shell, cfg.extra.get("m_shop"), lambda e: self._shop_changed())
        self.code = _code_field(lambda e: self.scan())
        self.lines = LineList(self.recalc)
        self.total = ft.Text("", size=20, weight=ft.FontWeight.BOLD)
        self.cash = ft.TextField(label="現金", dense=True, width=110, keyboard_type=ft.KeyboardType.NUMBER)
        self.card = ft.TextField(label="刷卡", dense=True, width=110, keyboard_type=ft.KeyboardType.NUMBER)
        self.voucher = ft.TextField(label="禮券", dense=True, width=110, keyboard_type=ft.KeyboardType.NUMBER)
        self.pay = ft.Container(ft.Column([ft.Row([self.total]),
                                           ft.Row([self.cash, self.card, self.voucher], wrap=True, spacing=6),
                                           ft.FilledButton("結帳", icon=ft.Icons.CHECK_CIRCLE, height=48, expand=True,
                                                           on_click=lambda e: self.checkout())], spacing=6),
                                padding=10, bgcolor=ft.Colors.BLUE_50, border_radius=12)
        super().__init__([_title("門市銷貨"), ft.Row([self.shop]),
                          ft.Row([self.code, ft.IconButton(ft.Icons.ADD_BOX, on_click=lambda e: self.scan())]),
                          ft.Column([self.lines], scroll=ft.ScrollMode.AUTO, expand=True), self.pay],
                         expand=True, spacing=8)
        self.recalc()

    def _shop_changed(self):
        self.shell.app.cfg.extra["m_shop"] = self.shop.value
        from .. import config
        config.save(self.shell.app.cfg)
        for l in self.lines.lines:   # 換店：依該店售價等級與特價重算
            l["price"], l["memo"] = self.shell.svc.price_info("TA", l["p"], dict(sh_no=self.shop.value))
        self.lines.render()
        self.update()

    def scan(self):
        if not self.shop.value:
            self.shell.ctx.toast("請先選店家", True)
            return

        def add(p):
            price, tag = self.shell.svc.price_info("TA", p, dict(sh_no=self.shop.value, doc_date=dates.today()))
            p = dict(p, color_name=self.shell.svc.code_map("color").get(p["color"], ""))
            self.lines.add(p, 1, price, tag)
            self.code.value = ""
            self.update()
            self.code.focus()
        resolve(self.shell, self.code.value, add, "S", self.shop.value)

    def recalc(self):
        amt = sum(money(D(l["price"]) * l["qty"]) for l in self.lines.lines)
        qty = sum(l["qty"] for l in self.lines.lines)
        self.total.value = "共 %d 件　應收 %s" % (qty, fmt(amt))
        self.cash.hint_text = fmt(amt)
        self._amt = amt
        _safe_update(self)

    def checkout(self):
        if not self.lines.lines:
            self.shell.ctx.toast("還沒有商品", True)
            return
        try:
            cash, card, vou = (D(f.value or 0) for f in (self.cash, self.card, self.voucher))
        except Exception:
            self.shell.ctx.toast("付款金額要是數字", True)
            return
        if cash == card == vou == 0:
            cash = self._amt   # 沒填付款方式＝全額現金
        header = dict(doc_date=dates.today(), sh_no=self.shop.value, pay_cash=cash, pay_card=card, pay_voucher=vou,
                      memo="手機銷貨")
        lines = [dict(prod_no=l["p"]["prod_no"], color=l["p"]["color"], size=l["p"]["size"], qty=l["qty"],
                      price=l["price"], memo=l.get("memo") or "") for l in self.lines.lines]
        did = self.shell.ctx.guard(self.shell.svc.save_doc, "TA", header, lines)
        if did:
            no = self.shell.svc.db.scalar("SELECT doc_no FROM docs WHERE id=%s", (did,))
            self.shell.ctx.toast("已結帳：%s　%s" % (no, fmt(self._amt)))
            self.lines.clear()
            for f in (self.cash, self.card, self.voucher):
                f.value = ""
            self.update()


# ------------------------------------------------------------ 盤點
class StocktakeTab(ft.Column):
    def __init__(self, shell):
        self.shell = shell
        svc = shell.svc
        segs = []
        if svc.can("D_CK"):
            segs.append(ft.Segment(value="S", label=ft.Text("店家盤點")))
        if svc.can("D_ST"):
            segs.append(ft.Segment(value="W", label=ft.Text("倉庫盤點")))
        self.kind = ft.SegmentedButton(segments=segs, selected=[segs[0].value], on_change=lambda e: self._kind())
        self.loc_box = ft.Row()
        self.code = _code_field(lambda e: self.scan(), "掃描或輸入（每次 +1）")
        self.lines = LineList(self.recalc, show_price=False)
        self.info = ft.Text("", size=13, color=ft.Colors.GREY_700)
        self.doc_id = None
        self.save_btn = ft.FilledButton("儲存盤點單", icon=ft.Icons.SAVE, height=46, expand=True, on_click=lambda e: self.save())
        self.diff_btn = ft.OutlinedButton("看盤差", icon=ft.Icons.COMPARE_ARROWS, height=46, on_click=lambda e: self.diff(),
                                          disabled=True)
        super().__init__([_title("盤點"), self.kind, self.loc_box,
                          ft.Row([self.code, ft.IconButton(ft.Icons.ADD_BOX, on_click=lambda e: self.scan())]),
                          self.info, ft.Column([self.lines], scroll=ft.ScrollMode.AUTO, expand=True),
                          ft.Row([self.save_btn, self.diff_btn])], expand=True, spacing=8)
        self._kind(False)

    def _kind(self, update=True):
        k = (self.kind.selected or ["S"])[0]
        self.loc = _shop_dd(self.shell, None, lambda e: self._reset(), k)
        self.loc_box.controls = [self.loc]
        self._reset(update)

    def _reset(self, update=True):
        self.doc_id = None
        self.lines.clear()
        self.diff_btn.disabled = True
        if update:
            self.update()

    def scan(self):
        k = (self.kind.selected or ["S"])[0]

        def add(p):
            p = dict(p, color_name=self.shell.svc.code_map("color").get(p["color"], ""))
            self.lines.add(p, 1)
            self.code.value = ""
            self.update()
            self.code.focus()
        resolve(self.shell, self.code.value, add, k, self.loc.value)

    def recalc(self):
        n = sum(l["qty"] for l in self.lines.lines)
        self.info.value = "已盤 %d 個規格、%d 件%s" % (len(self.lines.lines), n,
                                                 "　（盤點單已儲存，可繼續盤並再次儲存）" if self.doc_id else "")
        _safe_update(self)

    def save(self):
        if not self.lines.lines:
            self.shell.ctx.toast("還沒有盤點資料", True)
            return
        k = (self.kind.selected or ["S"])[0]
        code = "CK" if k == "S" else "ST"
        header = dict(doc_date=dates.today(), memo="手機盤點", **({"sh_no": self.loc.value} if k == "S" else {"wh_no": self.loc.value}))
        lines = [dict(prod_no=l["p"]["prod_no"], color=l["p"]["color"], size=l["p"]["size"], qty=l["qty"], price=0)
                 for l in self.lines.lines]
        did = self.shell.ctx.guard(self.shell.svc.save_doc, code, header, lines, self.doc_id)
        if did:
            self.doc_id = did
            no = self.shell.svc.db.scalar("SELECT doc_no FROM docs WHERE id=%s", (did,))
            self.shell.ctx.toast("盤點單 %s 已儲存（調整庫存請在電腦版按「盤差計算」）" % no)
            self.diff_btn.disabled = False
            self.recalc()

    def diff(self):
        r = self.shell.ctx.guard(self.shell.svc.stocktake_diff, self.doc_id)
        if not isinstance(r, tuple):
            return
        h, diff = r
        counted = {(l["p"]["prod_no"], l["p"]["color"], l["p"]["size"]) for l in self.lines.lines}
        diff = [x for x in diff if (x["prod_no"], x["color"], x["size"]) in counted]   # 只看這次有盤到的
        p = self.shell.page
        p.show_dialog(ft.AlertDialog(
            title=ft.Text("盤差　%s" % h["doc_no"]),
            content=ft.Column([ft.Row([ft.Text("%s %s/%s" % (x["prod_no"], x["color"], x["size"]), expand=True),
                                       ft.Text("帳 %d" % x["book"], width=56), ft.Text("盤 %d" % x["counted"], width=56),
                                       ft.Text("%+d" % x["diff"], width=44, weight=ft.FontWeight.BOLD,
                                               color=ft.Colors.RED if x["diff"] < 0 else ft.Colors.GREEN)])
                               for x in diff] or [ft.Text("這次盤到的商品都和帳面相符 👍")],
                              scroll=ft.ScrollMode.AUTO, tight=True),
            actions=[ft.TextButton("關閉", on_click=lambda e: p.pop_dialog())]))
