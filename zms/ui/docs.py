"""單據畫面：清單＋編輯（倉庫／店家共用）。"""
from decimal import Decimal

import flet as ft

from .. import dates
from ..doctypes import BY_CODE, label
from ..services import D, money
from .common import Grid, date_field, dd, export_button, fmt, section, tf
from .printing import open_doc

PARTY_SOURCES = {"wh_no": "warehouses", "wh_no2": "warehouses", "sh_no": "shops", "sh_no2": "shops",
                 "ma_no": "vendors", "per_no": "employees", "reason": "reason"}


class DocView(ft.Column):
    def __init__(self, ctx, code):
        self.ctx, self.code, self.dt = ctx, code, BY_CODE[code]
        super().__init__(expand=True)
        self.show_list()

    # ---------------- 清單
    def show_list(self, update=False):
        t = dates.today()
        self.d1 = date_field("起日", t.replace(day=1))
        self.d2 = date_field("迄日", t)
        party_field = next((f for f in ("sh_no", "ma_no", "wh_no") if f in self.dt.fields), None)
        self.party = dd(label(self.dt, party_field), self.ctx.svc.options(PARTY_SOURCES[party_field]), "",
                        width=220, blank="all") if party_field else None
        self.q = tf("單號／備註", width=170, on_submit=lambda e: self.load())
        self.grid = Grid([("doc_no", "單號", "s", 120), ("doc_date", "日期", "s", 80),
                          ("party", "對象", "s", 180), ("total_qty", "數量", "n", 70),
                          ("total_amt", "金額", "n", 100), ("memo", "備註", "s", 200),
                          ("created_by", "輸入者", "s", 70)], on_pick=lambda r: self.open(r["id"]),
                         total_keys=("total_qty", "total_amt"))
        bar = [self.d1, self.d2] + ([self.party] if self.party else []) + [
            self.q, ft.FilledButton("查詢", icon=ft.Icons.SEARCH, on_click=lambda e: self.load()),
            ft.FilledButton("新增單據", icon=ft.Icons.ADD, on_click=lambda e: self.open(None)),
            export_button(self.ctx, self.grid, self.dt.name)]
        self.controls = [section(self.dt.name, ft.Row(bar, wrap=True), self.grid)]
        self.load(update)

    def load(self, update=True):
        try:
            rows = self.ctx.svc.list_docs(self.code, self.d1.value, self.d2.value,
                                          (self.party.value if self.party else "") or "", (self.q.value or "").strip())
        except ValueError as e:
            self.ctx.toast(str(e), True)
            return
        for r in rows:
            parts = []
            for f in self.dt.fields:
                if f in ("sh_no", "sh_no2"):
                    parts.append(r.get(f) + (" " + (r.get("sh_name") or "") if f == "sh_no" else ""))
                elif f in ("wh_no", "wh_no2") and f == "wh_no":
                    parts.append(r["wh_no"] + " " + (r.get("wh_name") or ""))
                elif f == "wh_no2":
                    parts.append("→" + r["wh_no2"])
                elif f == "ma_no":
                    parts.append(r["ma_no"] + " " + (r.get("ma_name") or ""))
            r["party"] = "　".join(p for p in parts if p.strip())
        self.grid.set_rows(rows)
        if update:
            self.update()

    # ---------------- 編輯
    def open(self, doc_id):
        svc = self.ctx.svc
        if doc_id:
            h, lines = svc.get_doc(doc_id)
        else:
            h, lines = {"doc_date": dates.today(), "discount": 100}, []
        self.doc_id = doc_id
        self.header = {}
        hdr = [tf("單號", h.get("doc_no") or "（存檔時自動編號）", width=170, disabled=True),
               date_field("日期", h.get("doc_date"))]
        self.header["doc_date"] = hdr[1]
        for f in self.dt.fields:
            if f in PARTY_SOURCES:
                c = dd(label(self.dt, f), svc.options(PARTY_SOURCES[f]), h.get(f) or "", width=220,
                       on_select=self._on_party if f == "sh_no" else None)
            elif f == "discount":
                c = tf(label(self.dt, f), fmt(D(h.get("discount") or 100)), width=90,
                       on_blur=lambda e: self.recalc())
            else:
                c = tf(label(self.dt, f), h.get(f) or "", width=160)
            self.header[f] = c
            hdr.append(c)
        self.header["memo"] = tf("備註", h.get("memo") or "", width=360)
        hdr.append(self.header["memo"])
        if self.code == "TA":
            for f, t in (("pay_cash", "現金"), ("pay_card", "刷卡"), ("pay_voucher", "禮券")):
                self.header[f] = tf(t, fmt(D(h.get(f) or 0)), width=100)
                hdr.append(self.header[f])

        self.lines = [dict(prod_no=l["prod_no"], color=l["color"], size=l["size"], name=l.get("name") or "",
                           qty=l["qty"], price=D(l["price"]), memo=l.get("memo") or "") for l in lines]
        self.scan = tf("貨號（開尺寸矩陣）或條碼，按 Enter", width=320, autofocus=True, on_submit=self._on_scan,
                       prefix_icon=ft.Icons.QR_CODE_SCANNER)
        self.lines_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(t)) for t in ("#", "貨號", "顏色", "尺寸", "品名", "數量", "單價", "金額", "")],
            rows=[], heading_row_height=34, data_row_min_height=40, data_row_max_height=48, column_spacing=14,
            heading_row_color=ft.Colors.BLUE_50, border=ft.Border.all(1, ft.Colors.GREY_300))
        self.total = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
        btns = [ft.FilledButton("存檔", icon=ft.Icons.SAVE, on_click=self._save),
                ft.OutlinedButton("返回清單", icon=ft.Icons.ARROW_BACK, on_click=lambda e: self.show_list(True))]
        if doc_id:
            btns += [ft.OutlinedButton("列印", icon=ft.Icons.PRINT, on_click=lambda e: open_doc(svc, doc_id)),
                     ft.OutlinedButton("列印吊牌", icon=ft.Icons.QR_CODE_2, on_click=lambda e: self._labels()),
                     ft.OutlinedButton("裝箱標籤", icon=ft.Icons.INVENTORY_2, on_click=lambda e: self._box_labels(),
                                       visible=self.code in ("GR", "DR", "MO", "CH", "PO")),
                     ft.OutlinedButton("刪除", icon=ft.Icons.DELETE, on_click=self._delete,
                                       style=ft.ButtonStyle(color=ft.Colors.RED))]
            if self.code in ("ST", "CK"):
                btns.append(ft.FilledButton("盤差計算", icon=ft.Icons.COMPARE_ARROWS, on_click=self._diff))
        title = "%s　%s" % (self.dt.name, "修改" if doc_id else "新增")
        self.controls = [section(title, ft.Row(hdr, wrap=True, spacing=10, run_spacing=10),
                                 ft.Row([self.scan,
                                         ft.FilledButton("尺寸矩陣", icon=ft.Icons.GRID_ON,
                                                         on_click=lambda e: self._ask_matrix()),
                                         ft.OutlinedButton("挑選產品", icon=ft.Icons.LIST,
                                                           on_click=lambda e: self._picker(""))], wrap=True),
                                 ft.Column([ft.Row([self.lines_table], scroll=ft.ScrollMode.AUTO)],
                                           scroll=ft.ScrollMode.AUTO, expand=True),
                                 ft.Row([self.total, ft.Row(btns, wrap=True)],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN))]
        self.render_lines()
        self.update()

    def _labels(self):
        """依本單數量印吊牌（例如進貨後每件掛一張）。"""
        from .. import labels
        items = self.ctx.svc.label_items_from_doc(self.doc_id)
        if not items:
            self.ctx.toast("本單沒有可印的產品", True)
            return
        lvl = "1"
        sh = self.header.get("sh_no").value if self.header.get("sh_no") else ""
        if sh:
            lvl = str(self.ctx.svc.db.scalar("SELECT price_level FROM shops WHERE sh_no=%s", (sh,)) or 1)
        labels.open_labels(items, layout="tag40x60", price_level=lvl,
                           company=(self.ctx.svc.company() or {}).get("name") or "")
        self.ctx.toast("已開啟 %d 張吊牌（要換版型請到「基本資料 → 吊牌標籤」）" % sum(i["copies"] for i in items))

    def _box_labels(self):
        """裝箱標籤（舊系統 C1_D）：輸入箱數，每箱一張「第 i / N 箱」。"""
        from .. import labels
        info = self.ctx.guard(self.ctx.svc.box_info, self.doc_id)
        if not isinstance(info, dict):
            return
        boxes = tf("箱數", "1", width=100, autofocus=True)
        lay = dd("版型", [(k, v[0]) for k, v in labels.BOX_LAYOUTS.items()], "box100x70", width=300, blank=False)

        def go(e):
            try:
                n = int(boxes.value or 1)
            except ValueError:
                self.ctx.toast("箱數要是整數", True)
                return
            self.ctx.page.pop_dialog()
            labels.open_box_labels(info, boxes=n, layout=lay.value or "box100x70")
            self.ctx.toast("已開啟 %d 張裝箱標籤" % n)
        boxes.on_submit = go
        to = info["to"]
        self.ctx.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("裝箱標籤　%s" % info["doc_no"]),
            content=ft.Column([ft.Text("收件：%s　%s" % (to.get("name") or "", to.get("tel") or "")),
                               ft.Text("地址：%s" % (to.get("address") or "（未填，請到基本資料補送貨地址）"), size=13),
                               ft.Row([boxes, lay])], tight=True),
            actions=[ft.TextButton("取消", on_click=lambda e: self.ctx.page.pop_dialog()),
                     ft.FilledButton("列印", icon=ft.Icons.PRINT, on_click=go)]))

    def _on_party(self, e):
        """換店家：帶入該店折數，並依店家售價等級重算單價。"""
        if not self.header.get("sh_no").value:
            return
        if "discount" in self.header:
            self.header["discount"].value = fmt(self.ctx.svc.shop_discount(self.header["sh_no"].value))
        if self.dt.price == "sale" and self.lines:
            h = self._hdr_values()
            for ln in self.lines:
                p = self.ctx.svc.db.one("SELECT * FROM products WHERE prod_no=%s AND color=%s AND size=%s",
                                        (ln["prod_no"], ln["color"], ln["size"]))
                if p:
                    ln["price"], ln["memo"] = self.ctx.svc.price_info(self.code, p, h)
            self.render_lines()
        self.recalc()

    def _hdr_values(self):
        return {k: (c.value or "").strip() if isinstance(c.value, str) else c.value for k, c in self.header.items()}

    def _add(self, p, qty=1):
        for ln in self.lines:
            if (ln["prod_no"], ln["color"], ln["size"]) == (p["prod_no"], p["color"], p["size"]):
                ln["qty"] = int(ln["qty"] or 0) + qty
                return
        price, tag = self.ctx.svc.price_info(self.code, p, self._hdr_values())
        self.lines.append(dict(prod_no=p["prod_no"], color=p["color"], size=p["size"], name=p.get("name") or "",
                               qty=qty, price=price, memo=tag))

    def _on_scan(self, e):
        code = (self.scan.value or "").strip()
        if not code:
            return
        p = self.ctx.svc.product_by_code(code)
        if p:
            self._add(p)
            self.scan.value = ""
            self.render_lines()
            self.update()
            self.scan.focus()
        elif self.ctx.svc.variants(code):
            self._matrix(code)   # 輸入的是貨號：直接開「顏色 × 尺寸」矩陣
        else:
            self._picker(code)

    def _stock_loc(self):
        """矩陣上顯示哪個位置的庫存：優先顯示會被扣庫存的位置。"""
        for f, sign in self.dt.effects:
            if sign == -1 and self.header.get(f) and self.header[f].value:
                return ("W" if f.startswith("wh") else "S"), self.header[f].value
        for f in ("wh_no", "sh_no"):
            if f in self.header and self.header[f].value:
                return ("W" if f == "wh_no" else "S"), self.header[f].value
        return None, None

    def _matrix(self, prod_no):
        """尺寸矩陣輸入（舊系統「多尺寸」）：列＝顏色、欄＝尺寸，一次填整款數量；淡字是目前庫存。"""
        svc = self.ctx.svc
        lt, ln = self._stock_loc()
        m = svc.matrix_for(prod_no, lt, ln)
        if not m:
            self.ctx.toast("找不到貨號 %s" % prod_no, True)
            return
        cur = {(l["color"], l["size"]): l["qty"] for l in self.lines if l["prod_no"] == prod_no}
        fields = {}
        total = ft.Text("", weight=ft.FontWeight.BOLD)

        def recount(e=None):
            n = 0
            for tf_ in fields.values():
                try:
                    n += int(tf_.value or 0)
                except ValueError:
                    pass
            total.value = "合計 %d 件" % n
            if e:
                total.update()

        head = [ft.Container(ft.Text("顏色＼尺寸", weight=ft.FontWeight.BOLD), width=130)] + [
            ft.Container(ft.Text(s, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER), width=70)
            for s in m["sizes"]]
        rows = [ft.Row(head, spacing=6)]
        for c in m["colors"]:
            cells = [ft.Container(ft.Text("%s %s" % (c, m["color_names"].get(c, "")), no_wrap=True), width=130)]
            for s in m["sizes"]:
                if (c, s) in m["variants"]:
                    st = m["stock"].get((c, s))
                    tfx = ft.TextField(str(cur[(c, s)]) if (c, s) in cur else "", width=70, dense=True,
                                       text_align=ft.TextAlign.RIGHT, keyboard_type=ft.KeyboardType.NUMBER,
                                       hint_text=("庫%d" % st) if st is not None and lt else "", on_change=recount,
                                       tooltip="目前庫存 %s" % (st if st is not None else 0) if lt else None)
                    fields[(c, s)] = tfx
                    cells.append(tfx)
                else:
                    cells.append(ft.Container(ft.Text("—", color=ft.Colors.GREY_400,
                                                      text_align=ft.TextAlign.CENTER), width=70))
            rows.append(ft.Row(cells, spacing=6))
        recount()

        def apply(e):
            new = []
            for (c, s), tfx in fields.items():
                try:
                    q = int(tfx.value or 0)
                except ValueError:
                    self.ctx.toast("%s-%s 數量不是整數" % (c, s), True)
                    return
                if q:
                    new.append((m["variants"][(c, s)], q))
            # 這個貨號以矩陣為準：先移除舊明細再加入
            self.lines = [l for l in self.lines if l["prod_no"] != prod_no]
            for v, q in new:
                self._add(v, q)
            self.ctx.page.pop_dialog()
            self.scan.value = ""
            self.render_lines()
            self.update()
            self.ctx.toast("%s 已填入 %d 個顏色尺寸" % (prod_no, len(new)))

        where = ("（淡字為%s %s 的目前庫存）" % ("倉庫" if lt == "W" else "店家", ln)) if lt else ""
        self.ctx.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("尺寸矩陣　%s %s" % (prod_no, m["name"] or "")),
            content=ft.Container(ft.Column([ft.Text(where, size=12, color=ft.Colors.GREY_700),
                                            ft.Row([ft.Column(rows, spacing=6)], scroll=ft.ScrollMode.AUTO), total],
                                           scroll=ft.ScrollMode.AUTO, tight=True),
                                 width=min(140 + 76 * len(m["sizes"]) + 40, 1000)),
            actions=[ft.TextButton("取消", on_click=lambda e: self.ctx.page.pop_dialog()),
                     ft.FilledButton("填入單據", icon=ft.Icons.DONE, on_click=apply)]))

    def _ask_matrix(self):
        code = (self.scan.value or "").strip()
        if code and self.ctx.svc.variants(code):
            self._matrix(code)
            return
        q = tf("貨號", code, width=220, autofocus=True)

        def go(e):
            pn = (q.value or "").strip()
            self.ctx.page.pop_dialog()
            if self.ctx.svc.variants(pn):
                self._matrix(pn)
            else:
                self._picker(pn)
        q.on_submit = go
        self.ctx.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("尺寸矩陣輸入"), content=q,
                                                 actions=[ft.TextButton("取消", on_click=lambda e: self.ctx.page.pop_dialog()),
                                                          ft.FilledButton("開啟", on_click=go)]))

    def _picker(self, q):
        """挑選產品：同貨號的各顏色尺寸一次輸入數量（取代舊系統「多尺寸」輸入）。"""
        svc = self.ctx.svc
        search = tf("貨號／品名", q, width=260)
        body = ft.Column(scroll=ft.ScrollMode.AUTO, height=380, width=640)
        qty_fields = []

        def load(e=None):
            rows = svc.find_products((search.value or "").strip(), limit=120)
            qty_fields.clear()
            items = []
            for p in rows:
                f = ft.TextField(width=80, dense=True, text_align=ft.TextAlign.RIGHT, hint_text="0",
                                 keyboard_type=ft.KeyboardType.NUMBER)
                qty_fields.append((p, f))
                items.append(ft.Row([ft.Text("%s-%s-%s" % (p["prod_no"], p["color"], p["size"]), width=200),
                                     ft.Text(p["name"] or "", width=220, no_wrap=True), f]))
            body.controls = items or [ft.Text("找不到產品", color=ft.Colors.GREY)]
            body.update() if e else None

        def add(e):
            n = 0
            for p, f in qty_fields:
                try:
                    q2 = int(f.value or 0)
                except ValueError:
                    continue
                if q2:
                    self._add(p, q2)
                    n += 1
            self.ctx.page.pop_dialog()
            self.scan.value = ""
            self.render_lines()
            self.update()
            if n:
                self.ctx.toast("已加入 %d 項" % n)

        search.on_submit = load
        load()
        self.ctx.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("挑選產品"),
            content=ft.Column([ft.Row([search, ft.FilledButton("搜尋", on_click=load)]), body], tight=True),
            actions=[ft.TextButton("取消", on_click=lambda e: self.ctx.page.pop_dialog()),
                     ft.FilledButton("加入", icon=ft.Icons.ADD, on_click=add)]))

    def render_lines(self):
        rows = []
        for i, ln in enumerate(self.lines):
            qf = ft.TextField(str(ln["qty"]), width=80, dense=True, text_align=ft.TextAlign.RIGHT,
                              on_change=lambda e, i=i: self._set(i, "qty", e.control.value))
            pf = ft.TextField(fmt(ln["price"]).replace(",", ""), width=100, dense=True, text_align=ft.TextAlign.RIGHT,
                              on_change=lambda e, i=i: self._set(i, "price", e.control.value))
            amt = ft.Text("", width=100, text_align=ft.TextAlign.RIGHT)
            ln["_amt"] = amt
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(i + 1))), ft.DataCell(ft.Text(ln["prod_no"])), ft.DataCell(ft.Text(ln["color"])),
                ft.DataCell(ft.Text(ln["size"])), ft.DataCell(ft.Row([ft.Text(ln["name"], width=160, no_wrap=True)] + (
                    [ft.Container(ft.Text(ln["memo"][:6], size=11, color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_400,
                                  padding=ft.Padding.symmetric(horizontal=4), border_radius=4,
                                  tooltip=ln["memo"])] if ln.get("memo") else []), spacing=4)),
                ft.DataCell(qf), ft.DataCell(pf), ft.DataCell(amt),
                ft.DataCell(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, tooltip="刪除此筆",
                                          on_click=lambda e, i=i: self._remove(i)))]))
        self.lines_table.rows = rows
        self.recalc(update=False)

    def _set(self, i, k, v):
        try:
            self.lines[i][k] = int(v or 0) if k == "qty" else D(v or 0)
        except Exception:
            return
        self.recalc()

    def _remove(self, i):
        self.lines.pop(i)
        self.render_lines()
        self.update()

    def recalc(self, update=True):
        try:
            disc = D(self.header["discount"].value or 100) if "discount" in self.header else Decimal(100)
        except Exception:
            disc = Decimal(100)
        tq, ta = 0, Decimal(0)
        for ln in self.lines:
            try:
                a = money(int(ln["qty"] or 0) * D(ln["price"]) * disc / 100)
            except Exception:
                a = Decimal(0)
            ln["_amt"].value = fmt(a)
            tq += int(ln["qty"] or 0)
            ta += a
        self.total.value = "共 %d 筆　數量 %s　金額 %s" % (len(self.lines), fmt(tq, "n"), fmt(ta))
        if update:
            self.update()

    def _save(self, e):
        h = self._hdr_values()
        lines = [dict(prod_no=l["prod_no"], color=l["color"], size=l["size"], qty=l["qty"], price=l["price"],
                      memo=l.get("memo") or "") for l in self.lines]
        new_id = self.ctx.guard(self.ctx.svc.save_doc, self.code, h, lines, self.doc_id)
        if new_id:
            no = self.ctx.svc.db.scalar("SELECT doc_no FROM docs WHERE id=%s", (new_id,))
            self.ctx.toast("已存檔：%s" % no)
            self.open(new_id)

    def _delete(self, e):
        def yes():
            if self.ctx.guard(self.ctx.svc.delete_doc, self.doc_id, ok="已刪除，庫存已回沖"):
                self.show_list(True)
        self.ctx.confirm("刪除單據", "刪除後庫存會自動回沖，確定刪除？", yes, "刪除")

    def _diff(self, e):
        r = self.ctx.guard(self.ctx.svc.stocktake_diff, self.doc_id)
        if r is None:
            return
        h, diff = r
        g = Grid([("prod_no", "貨號", "s", 120), ("color", "顏色", "s", 50), ("size", "尺寸", "s", 50),
                  ("book", "帳面量", "n", 70), ("counted", "盤點量", "n", 70), ("diff", "差異", "n", 70)], height=360)
        g.set_rows(diff)
        only = ft.Checkbox(label="只調整有盤到的產品（沒盤到的不歸零）", value=True)

        def post(ev):
            nid = self.ctx.guard(self.ctx.svc.post_stocktake, self.doc_id, only.value)
            if nid:
                self.ctx.page.pop_dialog()
                no = self.ctx.svc.db.scalar("SELECT doc_no FROM docs WHERE id=%s", (nid,))
                self.ctx.toast("已產生調整單 %s" % no)

        self.ctx.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("盤差（%s）" % h["doc_no"]),
            content=ft.Container(ft.Column([g, only], tight=True), width=560),
            actions=[ft.TextButton("關閉", on_click=lambda ev: self.ctx.page.pop_dialog()),
                     ft.FilledButton("產生調整單", on_click=post, disabled=not diff)]))
