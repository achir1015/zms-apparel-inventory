"""應收帳款：結帳、收款沖帳、店家費用、應收查詢。"""
import flet as ft

from .. import dates
from ..services import D
from .common import Grid, date_field, dd, export_button, fmt, section, tf


def _prev_period():
    t = dates.today().replace(day=1)
    p = t.replace(day=1) - __import__("datetime").timedelta(days=1)
    return p.strftime("%Y%m")


class CloseView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.period = tf("結帳年月（西元 YYYYMM）", _prev_period(), width=200)
        self.grid = Grid([("sh_no", "店家", "s", 80), ("short_name", "簡稱", "s", 120), ("mode", "方式", "s", 60),
                          ("ship_amt", "出貨", "n", 90), ("return_amt", "退貨", "n", 90), ("sales_amt", "銷貨", "n", 90),
                          ("commission_amt", "抽成", "n", 80), ("fee_amt", "費用", "n", 80), ("amount", "本期應收", "n", 100)],
                         total_keys=("ship_amt", "return_amt", "sales_amt", "commission_amt", "fee_amt", "amount"))
        super().__init__([section("應收結帳", ft.Row([
            self.period, ft.OutlinedButton("試算", icon=ft.Icons.CALCULATE, on_click=lambda e: self.preview()),
            ft.FilledButton("確認結帳", icon=ft.Icons.LOCK, on_click=lambda e: self.close()),
            export_button(ctx, self.grid, "應收結帳")], wrap=True),
            ft.Text("批發店家：出貨−退貨−費用；專櫃店家：銷貨−抽成−費用。同月份可重新結帳（覆蓋）。", size=12,
                    color=ft.Colors.GREY_600), self.grid)], expand=True)

    def _period(self):
        p = (self.period.value or "").strip()
        if len(p) == 5 and p.isdigit():   # 民國 11510
            p = "%04d%02d" % (int(p[:3]) + 1911, int(p[3:]))
        if not (len(p) == 6 and p.isdigit() and 1 <= int(p[4:]) <= 12):
            raise ValueError("年月格式：202611")
        return p

    def preview(self):
        try:
            p = self._period()
        except ValueError as e:
            self.ctx.toast(str(e), True)
            return
        rows = []
        for s in self.ctx.svc.db.all("SELECT sh_no FROM shops WHERE active=1 ORDER BY sh_no"):
            r = self.ctx.svc.ar_compute(s["sh_no"], p)
            if any([r["ship_amt"], r["return_amt"], r["sales_amt"], r["fee_amt"]]):
                r["mode"] = "專櫃" if r["settle_mode"] == "C" else "批發"
                rows.append(r)
        self.grid.set_rows(rows)
        self.update()

    def close(self):
        try:
            p = self._period()
        except ValueError as e:
            self.ctx.toast(str(e), True)
            return

        def yes():
            r = self.ctx.guard(self.ctx.svc.ar_close, p)
            if isinstance(r, list):
                self.ctx.toast("%s 結帳完成，共 %d 家" % (p, len(r)))
                self.preview()
        self.ctx.confirm("結帳", "確定結 %s 的帳？" % p, yes)


class PaymentView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.shop = dd("店家", ctx.svc.options("shops"), "", width=260, on_select=lambda e: self.load())
        self.date = date_field("收款日")
        self.amount = tf("收款金額", "", width=120)
        self.allow = tf("折讓", "", width=100)
        self.method = dd("方式", [("現金", "現金"), ("支票", "支票"), ("匯款", "匯款"), ("刷卡", "刷卡")], "現金",
                         width=110, blank=False)
        self.bill = tf("票號／帳號", "", width=150)
        self.memo = tf("備註", "", width=200)
        self.bal = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
        self.grid = Grid([("date", "日期", "s", 80), ("kind", "類別", "s", 50), ("ref", "參考", "s", 100),
                          ("debit", "應收", "n", 100), ("credit", "已收", "n", 100), ("balance", "餘額", "n", 100),
                          ("memo", "說明", "s", 260)], on_pick=self.pick)
        super().__init__([section("收款沖帳", ft.Row([self.shop, self.bal], spacing=30),
                                  ft.Row([self.date, self.amount, self.allow, self.method, self.bill, self.memo,
                                          ft.FilledButton("新增收款", icon=ft.Icons.ADD, on_click=lambda e: self.add())],
                                         wrap=True),
                                  ft.Text("點一下「收款」列可刪除該筆收款", size=12, color=ft.Colors.GREY_600),
                                  self.grid)], expand=True)

    def load(self):
        if not self.shop.value:
            return
        rows = self.ctx.svc.ar_history(self.shop.value)
        self.grid.set_rows(rows)
        self.bal.value = "目前應收餘額：%s" % fmt(rows[-1]["balance"] if rows else 0)
        self.update()

    def add(self):
        if not self.shop.value:
            self.ctx.toast("請先選店家", True)
            return
        if self.ctx.guard(self.ctx.svc.add_payment, self.shop.value, self.date.value, self.amount.value or 0,
                          self.allow.value or 0, self.method.value or "現金", self.bill.value or "",
                          self.memo.value or "", ok="已新增收款"):
            self.amount.value = self.allow.value = self.bill.value = self.memo.value = ""
            self.load()

    def pick(self, r):
        if r.get("kind") != "收款":
            return

        def yes():
            self.ctx.svc.delete_payment(r["id"])
            self.ctx.toast("已刪除")
            self.load()
        self.ctx.confirm("刪除收款", "刪除 %s 收款 %s？" % (dates.roc(r["date"]), fmt(r["credit"])), yes, "刪除")


class FeeView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.shop = dd("店家", ctx.svc.options("shops"), "", width=240)
        self.date = date_field("日期")
        self.subject = dd("科目", [(r["code"], "%s %s" % (r["code"], r["name"])) for r in ctx.svc.codes("subject")],
                          "", width=180)
        self.amount = tf("金額", "", width=110)
        self.memo = tf("備註", "", width=220)
        self.grid = Grid([("fee_date", "日期", "s", 80), ("sh_no", "店家", "s", 80), ("short_name", "簡稱", "s", 110),
                          ("subject_name", "科目", "s", 100), ("amount", "金額", "n", 90), ("memo", "備註", "s", 220)],
                         on_pick=self.pick, total_keys=("amount",))
        super().__init__([section("店家費用", ft.Row([self.shop, self.date, self.subject, self.amount, self.memo,
                                                    ft.FilledButton("新增", icon=ft.Icons.ADD,
                                                                    on_click=lambda e: self.add())], wrap=True),
                                  ft.Text("費用會在結帳時從應收中扣除（如百貨管理費、運費）；點一下列可刪除", size=12,
                                          color=ft.Colors.GREY_600), self.grid)], expand=True)
        self.load(False)

    def load(self, update=True):
        self.grid.set_rows(self.ctx.svc.list_fees())
        if update:
            self.update()

    def add(self):
        if self.ctx.guard(self.ctx.svc.add_fee, self.shop.value or "", self.date.value, self.subject.value or "",
                          self.amount.value or 0, self.memo.value or "", ok="已新增"):
            self.amount.value = self.memo.value = ""
            self.load()

    def pick(self, r):
        def yes():
            self.ctx.svc.delete_fee(r["id"])
            self.load()
        self.ctx.confirm("刪除費用", "刪除這筆費用？", yes, "刪除")


class BalanceView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.grid = Grid([("sh_no", "店家", "s", 80), ("short_name", "簡稱", "s", 140), ("last_period", "最近結帳", "s", 80),
                          ("billed", "累計應收", "n", 110), ("paid", "累計已收", "n", 110), ("balance", "未收餘額", "n", 110)],
                         total_keys=("billed", "paid", "balance"))
        super().__init__([section("應收帳款查詢", ft.Row([export_button(ctx, self.grid, "應收帳款")]), self.grid)],
                         expand=True)
        rows = ctx.svc.ar_balances()
        for r in rows:
            r["balance"] = D(r["billed"]) - D(r["paid"])
        self.grid.set_rows([r for r in rows if r["billed"] or r["paid"]])
