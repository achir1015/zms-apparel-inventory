"""特價品（舊系統 15 依貨號、16 依客戶）：設定期間內的特價或折數，開單時自動套用。"""
import datetime as _dt

import flet as ft

from .. import dates
from .common import Grid, date_field, dd, export_button, section, tf


class SpecialsView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.kind = dd("類別", [("", "全部"), ("prod", "15 依貨號（全部店家）"), ("shop", "16 依客戶（指定店家）")], "",
                       width=230, blank=False, on_select=lambda e: self.load())
        self.q = tf("貨號／店家／備註", width=200, on_submit=lambda e: self.load())
        self.cur = ft.Checkbox(label="只顯示今天有效", value=False, on_change=lambda e: self.load())
        self.grid = Grid([("sh_name", "店家", "s", 110), ("prod_no", "貨號", "s", 100), ("prod_name", "品名", "s", 140),
                          ("color", "顏色", "s", 45), ("size", "尺寸", "s", 45), ("start_date", "開始", "s", 80),
                          ("end_date", "結束", "s", 80), ("special_price", "特價", "n", 70), ("discount", "折數%", "n", 60),
                          ("memo", "備註", "s", 140), ("active", "啟用", "b", 40)], on_pick=self.edit)
        super().__init__([section("特價品", ft.Row([self.kind, self.q, self.cur,
                                                  ft.FilledButton("查詢", icon=ft.Icons.SEARCH, on_click=lambda e: self.load()),
                                                  ft.FilledButton("新增特價", icon=ft.Icons.ADD, on_click=lambda e: self.edit(None)),
                                                  export_button(ctx, self.grid, "特價品")], wrap=True),
                                  ft.Text("開售價類單據（出貨、銷貨、退貨、訂單、調撥）時，期間內自動帶入特價，明細會標示「特價」。"
                                          "同一商品有多筆時：指定店家優先於全部店家，指定顏色尺寸優先於整個貨號。"
                                          "顏色、尺寸留空＝該貨號全部規格。", size=12, color=ft.Colors.GREY_700),
                                  self.grid)], expand=True)
        self.load(False)

    def load(self, update=True):
        self.grid.set_rows(self.ctx.svc.list_specials(self.kind.value or "", (self.q.value or "").strip(), self.cur.value))
        if update:
            self.update()

    def edit(self, row):
        svc, p = self.ctx.svc, self.ctx.page
        r = row or {}
        today = dates.today()
        shop = dd("店家（空白＝全部店家）", svc.options("shops"), r.get("sh_no") or "", width=260)
        pn = tf("貨號", r.get("prod_no") or "", width=170)
        color = tf("顏色（空白＝全部）", r.get("color") or "", width=150)
        size = tf("尺寸（空白＝全部）", r.get("size") or "", width=150)
        d1 = date_field("開始日", r.get("start_date") or today)
        d2 = date_field("結束日", r.get("end_date") or (today + _dt.timedelta(days=30)))
        sp = tf("特價（元）", "" if r.get("special_price") is None else str(r["special_price"]), width=120)
        dc = tf("或 折數%（80＝八折）", "" if r.get("discount") is None else str(r["discount"]), width=170)
        memo = tf("備註（例：週年慶）", r.get("memo") or "", width=300)
        act = ft.Checkbox(label="啟用", value=bool(r.get("active", 1)))

        def save(e):
            data = dict(sh_no=shop.value or "", prod_no=pn.value, color=color.value, size=size.value,
                        start_date=d1.value, end_date=d2.value, special_price=sp.value, discount=dc.value,
                        memo=memo.value, active=1 if act.value else 0)
            if self.ctx.guard(svc.save_special, data, r.get("id"), ok="已儲存"):
                p.pop_dialog()
                self.load()

        def delete(e):
            svc.delete_special(r["id"])
            p.pop_dialog()
            self.ctx.toast("已刪除")
            self.load()

        actions = [ft.TextButton("取消", on_click=lambda e: p.pop_dialog()), ft.FilledButton("儲存", on_click=save)]
        if row:
            actions.insert(0, ft.TextButton("刪除", on_click=delete, style=ft.ButtonStyle(color=ft.Colors.RED)))
        p.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("特價品"),
            content=ft.Container(ft.Column([ft.Row([shop, pn, color, size], wrap=True), ft.Row([d1, d2, sp, dc], wrap=True),
                                            ft.Row([memo, act], wrap=True),
                                            ft.Text("特價與折數擇一填；兩者都填時以特價為準。", size=12,
                                                    color=ft.Colors.GREY_700)], tight=True), width=760),
            actions=actions))
