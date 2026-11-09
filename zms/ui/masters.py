"""基本資料維護：產品／店家／廠商／人員／倉庫（共用一個畫面類別）＋代碼表。"""
import flet as ft

from .. import dates
from ..services import CODE_KINDS, MASTERS
from .common import Grid, dd, export_button, section, tf


class MasterView(ft.Column):
    def __init__(self, ctx, table, func_id):
        self.ctx, self.table, self.func_id = ctx, table, func_id
        self.m = MASTERS[table]
        if table == "products":
            want = ["prod_no", "color", "size", "name", "brand", "year", "season", "style", "price1", "cost"]
            list_cols = [next(c for c in self.m["cols"] if c[0] == k) for k in want]
        else:
            list_cols = [c for c in self.m["cols"] if c[2] not in ("b",)][:9]
        self.q = tf("搜尋（代號、名稱）", width=260, on_submit=lambda e: self.load())
        self.grid = Grid([(c[0], c[1], "n" if c[2] == "n" else "s", c[3]) for c in list_cols], on_pick=self.edit)
        btns = [self.q, ft.FilledButton("查詢", icon=ft.Icons.SEARCH, on_click=lambda e: self.load()),
                ft.FilledButton("新增", icon=ft.Icons.ADD, on_click=lambda e: self.edit(None))]
        if table == "products":
            btns.append(ft.FilledButton("整款建檔（顏色×尺寸）", icon=ft.Icons.GRID_ON,
                                        on_click=lambda e: self.style_dialog()))
        bar = ft.Row(btns + [export_button(ctx, self.grid, self.m["title"])], wrap=True)
        super().__init__([section(self.m["title"], bar, ft.Text("點一下資料列可修改／刪除", size=12,
                                                                  color=ft.Colors.GREY_600), self.grid)], expand=True)
        self.load(update=False)

    def load(self, update=True):
        rows = self.ctx.guard(self.ctx.svc.master_list, self.table, (self.q.value or "").strip())
        if rows is not None:
            self.grid.set_rows(rows)
        if update:
            self.update()

    def _code_opts(self, kind):
        return [(r["code"], "%s %s" % (r["code"], r["name"])) for r in self.ctx.svc.codes(kind)]

    def edit(self, row):
        is_new = row is None
        row = row or {"active": 1, "price_level": 1, "settle_mode": "W", "discount": 100, "commission": 0}
        fields = {}
        controls = []
        for name, title, typ, width in self.m["cols"]:
            v = row.get(name)
            w = max(140, min(int(width * 1.3), 420))
            if typ == "b":
                c = ft.Checkbox(label=title, value=bool(v))
            elif typ.startswith("c:"):
                c = dd(title, self._code_opts(typ[2:]), v or "", width=w)
            elif typ.startswith("sel:"):
                opts = [tuple(x.split("=", 1)) for x in typ[4:].split(",")]
                c = dd(title, opts, str(v if v is not None else opts[0][0]), width=w, blank=False)
            elif typ == "d":
                c = tf(title, dates.roc(v) if v else "", width=w, hint_text="115/01/31")
            else:
                c = tf(title, v if v is not None else "", width=w,
                       keyboard_type=ft.KeyboardType.NUMBER if typ == "n" else None)
            if not is_new and name in self.m["pk"]:
                c.disabled = True
            fields[name] = c
            controls.append(c)

        def save(e):
            data = {k: c.value for k, c in fields.items()}
            if self.ctx.guard(self.ctx.svc.master_save, self.table, data, is_new, ok="已儲存") is not None:
                self.ctx.page.pop_dialog()
                self.load()

        def delete(e):
            key = [row[k] for k in self.m["pk"]]

            def yes():
                self.ctx.guard(self.ctx.svc.master_delete, self.table, key, ok="已刪除")
                self.load()
            self.ctx.page.pop_dialog()
            self.ctx.confirm("刪除確認", "確定刪除「%s」？" % " / ".join(str(k) for k in key), yes, "刪除")

        actions = [ft.TextButton("取消", on_click=lambda e: self.ctx.page.pop_dialog())]
        if not is_new:
            actions.insert(0, ft.TextButton("刪除", on_click=delete, style=ft.ButtonStyle(color=ft.Colors.RED)))
        actions.append(ft.FilledButton("儲存", icon=ft.Icons.SAVE, on_click=save))
        self.ctx.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text(("新增" if is_new else "修改") + self.m["title"]),
            content=ft.Container(ft.Column([ft.Row(controls, wrap=True, spacing=10, run_spacing=10)],
                                           scroll=ft.ScrollMode.AUTO), width=860, height=480),
            actions=actions))


    def style_dialog(self):
        """整款建檔：輸入一次貨號與共同資料，勾選顏色、選尺寸組，一次產生所有顏色尺寸。"""
        svc, p = self.ctx.svc, self.ctx.page
        f = {}
        for name in ("prod_no", "name", "spec", "class", "brand", "series", "year", "season", "style", "fabric",
                     "gender", "unit", "price1", "price2", "price3", "cost"):
            title, typ, width = next((c[1], c[2], c[3]) for c in self.m["cols"] if c[0] == name)
            w = max(130, min(int(width * 1.3), 300))
            if typ.startswith("c:"):
                f[name] = dd(title, self._code_opts(typ[2:]), "", width=w)
            elif typ.startswith("sel:"):
                f[name] = dd(title, [tuple(x.split("=", 1)) for x in typ[4:].split(",")], "", width=w, blank=False)
            else:
                f[name] = tf(title, "", width=w, keyboard_type=ft.KeyboardType.NUMBER if typ == "n" else None)
        colors = [ft.Checkbox(label="%s %s" % (r["code"], r["name"]), data=r["code"]) for r in svc.codes("color")]
        extra_colors = tf("其他顏色代碼（以空白分隔）", "", width=300)
        sizes = tf("尺寸（以空白或 * 分隔）", "", width=460)
        groups = svc.size_groups()

        def use_group(g):
            sizes.value = " ".join(groups[g])
            sizes.update()
        group_btns = [ft.OutlinedButton("尺寸組 %s：%s" % (g, " ".join(v[:6]) + ("…" if len(v) > 6 else "")),
                                        on_click=lambda e, g=g: use_group(g)) for g, v in groups.items()]
        size_codes = [r["code"] for r in svc.codes("size")]
        if size_codes:
            group_btns.append(ft.OutlinedButton("尺寸代碼表", on_click=lambda e: (setattr(sizes, "value", " ".join(
                size_codes)), sizes.update())))
        info = ft.Text("", size=13, color=ft.Colors.GREY_700)

        def preview(e=None):
            cs = [c.data for c in colors if c.value] + (extra_colors.value or "").split()
            ss = (sizes.value or "").replace("*", " ").split()
            info.value = "將產生 %d 色 × %d 碼 ＝ %d 筆" % (len(cs) or 1, len(ss) or 1, (len(cs) or 1) * (len(ss) or 1))
            info.update()
            return cs, ss
        for c in colors:
            c.on_change = preview
        extra_colors.on_change = preview
        sizes.on_change = preview

        def save(e):
            cs, ss = preview()
            base = {k: c.value for k, c in f.items()}
            base["safe_qty"] = 0
            r = self.ctx.guard(svc.create_style, base, cs, ss)
            if isinstance(r, tuple):
                p.pop_dialog()
                self.ctx.toast("已建立 %d 筆，略過已存在 %d 筆" % r)
                self.q.value = base["prod_no"]
                self.load()

        p.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("整款建檔（同一貨號，一次產生所有顏色尺寸）"),
            content=ft.Container(ft.Column([
                ft.Row(list(f.values()), wrap=True, spacing=10, run_spacing=10),
                ft.Divider(), ft.Text("顏色", weight=ft.FontWeight.BOLD),
                ft.Row(colors or [ft.Text("（代碼資料尚無顏色，可在下方直接輸入）", color=ft.Colors.GREY)], wrap=True),
                extra_colors,
                ft.Divider(), ft.Text("尺寸", weight=ft.FontWeight.BOLD),
                ft.Row(group_btns, wrap=True), sizes, info], scroll=ft.ScrollMode.AUTO), width=900, height=560),
            actions=[ft.TextButton("取消", on_click=lambda e: p.pop_dialog()),
                     ft.FilledButton("建立", icon=ft.Icons.DONE_ALL, on_click=save)]))


class CodesView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.kind = dd("代碼種類", list(CODE_KINDS.items()), "color", width=200, blank=False,
                       on_select=lambda e: self.load())
        self.grid = Grid([("code", "代碼", "s", 90), ("name", "名稱", "s", 200), ("memo", "備註", "s", 260)],
                         on_pick=self.edit)
        super().__init__([section("代碼資料", ft.Row([self.kind, ft.FilledButton("新增", icon=ft.Icons.ADD,
                                                                              on_click=lambda e: self.edit(None))]),
                                  ft.Text("顏色、尺寸、類別、品牌、系列、單位、異動原因、費用科目", size=12,
                                          color=ft.Colors.GREY_600), self.grid)], expand=True)
        self.load(update=False)

    def load(self, update=True):
        self.grid.set_rows(self.ctx.svc.codes(self.kind.value or "color"))
        if update:
            self.update()

    def edit(self, row):
        kind = self.kind.value or "color"
        code = tf("代碼", (row or {}).get("code", ""), width=140, disabled=row is not None)
        name = tf("名稱", (row or {}).get("name", ""), width=240)
        memo = tf("備註", (row or {}).get("memo", ""), width=380)

        def save(e):
            if self.ctx.guard(self.ctx.svc.save_code, kind, code.value, name.value, memo.value, ok="已儲存") is not None:
                self.ctx.page.pop_dialog()
                self.load()

        def delete(e):
            self.ctx.svc.delete_code(kind, row["code"])
            self.ctx.page.pop_dialog()
            self.ctx.toast("已刪除")
            self.load()

        actions = [ft.TextButton("取消", on_click=lambda e: self.ctx.page.pop_dialog()),
                   ft.FilledButton("儲存", on_click=save)]
        if row:
            actions.insert(0, ft.TextButton("刪除", on_click=delete, style=ft.ButtonStyle(color=ft.Colors.RED)))
        self.ctx.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text(CODE_KINDS[kind]),
                                                 content=ft.Column([code, name, memo], tight=True), actions=actions))
