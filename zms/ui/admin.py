"""系統維護：使用者與權限、公司設定、庫存校帳、備份回存、舊系統匯入、連線資訊。"""
import os
import threading

import flet as ft

from .. import backup, dates
from ..importer import LegacyImporter
from ..services import FUNCS
from .common import Grid, section, tf


class UsersView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        self.grid = Grid([("user_no", "代號", "s", 90), ("name", "姓名", "s", 120), ("dept", "部門", "s", 100),
                          ("is_admin", "管理員", "b", 60), ("active", "啟用", "b", 50)], on_pick=self.edit)
        super().__init__([section("使用者與權限", ft.Row([ft.FilledButton("新增使用者", icon=ft.Icons.PERSON_ADD,
                                                                      on_click=lambda e: self.edit(None))]),
                                  ft.Text("管理員擁有全部功能；一般使用者依勾選的功能使用", size=12,
                                          color=ft.Colors.GREY_600), self.grid)], expand=True)
        self.load(False)

    def load(self, update=True):
        self.grid.set_rows(self.ctx.svc.list_users())
        if update:
            self.update()

    def edit(self, row):
        svc = self.ctx.svc
        is_new = row is None
        row = row or {"active": 1, "is_admin": 0}
        no = tf("代號", row.get("user_no", ""), width=140, disabled=not is_new)
        name = tf("姓名", row.get("name", ""), width=160)
        dept = tf("部門", row.get("dept", ""), width=140)
        pw = tf("密碼" if is_new else "新密碼（不改請留空）", "", width=200, password=True, can_reveal_password=True)
        adm = ft.Checkbox(label="系統管理員", value=bool(row.get("is_admin")))
        act = ft.Checkbox(label="啟用", value=bool(row.get("active")))
        perms = svc.get_perms(row["user_no"]) if not is_new else set()
        boxes = {}
        groups = {}
        for fid, fname, grp in FUNCS:
            boxes[fid] = ft.Checkbox(label=fname, value=fid in perms)
            groups.setdefault(grp, []).append(boxes[fid])
        perm_ui = ft.Column([ft.Column([ft.Text(g, weight=ft.FontWeight.BOLD), ft.Row(cs, wrap=True)], spacing=2)
                             for g, cs in groups.items()], scroll=ft.ScrollMode.AUTO, height=300)

        def save(e):
            def go():
                if is_new:
                    svc.create_user(no.value, name.value, pw.value, adm.value, dept.value)
                    if not act.value:
                        svc.update_user(no.value, name.value, dept.value, adm.value, False)
                else:
                    svc.update_user(row["user_no"], name.value, dept.value, adm.value, act.value, pw.value or None)
                svc.set_perms(no.value.strip(), [k for k, b in boxes.items() if b.value])
            if self.ctx.guard(go, ok="已儲存"):
                self.ctx.page.pop_dialog()
                self.load()

        def delete(e):
            self.ctx.page.pop_dialog()

            def yes():
                self.ctx.guard(svc.delete_user, row["user_no"], ok="已刪除")
                self.load()
            self.ctx.confirm("刪除使用者", "刪除 %s？" % row["user_no"], yes, "刪除")

        actions = [ft.TextButton("取消", on_click=lambda e: self.ctx.page.pop_dialog()),
                   ft.FilledButton("儲存", on_click=save)]
        if not is_new:
            actions.insert(0, ft.TextButton("刪除", on_click=delete, style=ft.ButtonStyle(color=ft.Colors.RED)))
        self.ctx.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("使用者"), content=ft.Container(ft.Column(
                [ft.Row([no, name, dept], wrap=True), ft.Row([pw, adm, act], wrap=True), ft.Divider(),
                 ft.Text("功能權限", weight=ft.FontWeight.BOLD), perm_ui], tight=True), width=760),
            actions=actions))


class CompanyView(ft.Column):
    def __init__(self, ctx):
        self.ctx = ctx
        c = ctx.svc.company() or {}
        self.f = {
            "name": tf("公司名稱", c.get("name"), width=320), "tax_id": tf("統一編號", c.get("tax_id"), width=140),
            "tel": tf("電話", c.get("tel"), width=160), "address": tf("地址", c.get("address"), width=480),
            "prod_len": tf("貨號長度", c.get("prod_len"), width=100), "color_len": tf("顏色長度", c.get("color_len"), width=100),
            "size_len": tf("尺寸長度", c.get("size_len"), width=100)}
        for g in "abcd":
            self.f["size_group_" + g] = tf("尺寸組 %s（以 * 分隔，例 S*M*L*XL）" % g.upper(),
                                           c.get("size_group_" + g), width=640)
        super().__init__([section("公司設定", ft.Row(list(self.f.values()), wrap=True, spacing=10, run_spacing=10),
                                  ft.FilledButton("儲存", icon=ft.Icons.SAVE, on_click=self.save))], expand=True,
                         scroll=ft.ScrollMode.AUTO)

    def save(self, e):
        self.ctx.guard(self.ctx.svc.save_company, {k: (v.value or "").strip() for k, v in self.f.items()}, ok="已儲存")


class ToolsView(ft.Column):
    """庫存校帳、備份回存、舊資料匯入、連線資訊。"""

    def __init__(self, ctx, app):
        self.ctx, self.app = ctx, app
        cfg = ctx.svc.db.cfg
        self.log = ft.ListView(height=220, spacing=2, auto_scroll=True)
        self.busy = ft.ProgressRing(visible=False, width=22, height=22)
        cards = []
        if ctx.svc.can("M3"):
            cards.append(self._card("庫存校帳", "依所有單據重新計算倉庫與店家庫存（舊系統 A2/A3）。",
                                    ft.FilledButton("開始校帳", icon=ft.Icons.BUILD, on_click=self.rebuild)))
        if ctx.svc.can("M4"):
            cards.append(self._card("備份與回存", "備份成 .sql.gz 檔；回存會覆蓋目前所有資料。", ft.Row([
                ft.FilledButton("備份", icon=ft.Icons.BACKUP, on_click=self.do_backup),
                ft.OutlinedButton("回存", icon=ft.Icons.RESTORE, on_click=self.do_restore)])))
        if ctx.svc.can("M5"):
            cards.append(self._card("舊系統資料匯入", "選擇舊進銷存的資料夾（例如 E:\\進銷存系統\\KS），匯入產品、店家、"
                                    "廠商、倉庫、人員、代碼與所有單據。會先清空目前的基本資料與單據！",
                                    ft.FilledButton("選擇資料夾並匯入", icon=ft.Icons.DRIVE_FOLDER_UPLOAD,
                                                    on_click=self.do_import)))
        cards.append(self._card("資料庫連線", "模式：%s　伺服器：%s:%s　資料庫：%s\n設定檔：%s" % (
            "內建（程式自動啟停）" if cfg.mode == "embedded" else "外部伺服器", cfg.host, cfg.port, cfg.database, cfg.path),
            ft.FilledButton("資料庫連線設定", icon=ft.Icons.STORAGE,
                            on_click=lambda e: app.db_settings() if app else None)))
        super().__init__([section("系統工具", *cards, ft.Row([ft.Text("執行紀錄", weight=ft.FontWeight.BOLD), self.busy]),
                                  ft.Container(self.log, border=ft.Border.all(1, ft.Colors.GREY_300), padding=8,
                                               border_radius=6))], expand=True, scroll=ft.ScrollMode.AUTO)

    def _card(self, title, desc, action):
        return ft.Card(ft.Container(ft.Column([ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
                                               ft.Text(desc, size=13), action], spacing=8), padding=14))

    def write(self, msg):
        import datetime as _dt
        self.log.controls.append(ft.Text("%s  %s" % (_dt.datetime.now().strftime("%H:%M:%S"), msg), size=13))
        self.log.update()

    def _bg(self, fn):
        self.busy.visible = True
        self.update()

        def run():
            try:
                fn()
            except Exception as e:
                self.write("✖ " + str(e))
                self.ctx.toast(str(e), True)
            finally:
                self.busy.visible = False
                self.update()
        self.ctx.page.run_thread(run)

    def rebuild(self, e):
        def go():
            n, diff = self.ctx.svc.rebuild_stock()
            self.write("校帳完成：%d 張單據，修正 %d 筆庫存" % (n, diff))
            self.ctx.toast("校帳完成")
        self._bg(go)

    async def do_backup(self, e):
        path = await ft.FilePicker().save_file(dialog_title="備份檔存放位置",
                                               file_name="zms_backup_%s.sql.gz" % dates.today().strftime("%Y%m%d"),
                                               allowed_extensions=["gz"])
        if not path:
            return
        self._bg(lambda: (backup.backup(self.ctx.svc.db.cfg, path), self.write("備份完成：" + path),
                          self.ctx.toast("備份完成")))

    async def do_restore(self, e):
        files = await ft.FilePicker().pick_files(dialog_title="選擇備份檔", allowed_extensions=["gz", "sql"])
        if not files:
            return
        path = files[0].path

        def yes():
            def go():
                self.ctx.svc.db.close()
                backup.restore(self.ctx.svc.db.cfg, path)
                self.write("回存完成：" + path)
                self.ctx.toast("回存完成")
            self._bg(go)
        self.ctx.confirm("回存", "回存會覆蓋目前所有資料，確定？\n%s" % path, yes, "回存")

    async def do_import(self, e):
        folder = await ft.FilePicker().get_directory_path(dialog_title="選擇舊系統資料夾",
                                                          initial_directory=r"E:\進銷存系統")
        if not folder:
            return

        def yes():
            def go():
                stats = LegacyImporter(self.ctx.svc, folder, log=self.write).run(import_users=True)
                self.write("匯入完成")
                self.ctx.toast("匯入完成：產品 %s 筆、單據 %s 張" % (
                    stats.get("產品", 0), sum(v for k, v in stats.items() if k.startswith("單據"))))
            self._bg(go)
        self.ctx.confirm("匯入舊資料", "會先清空目前的基本資料與單據，再從\n%s\n匯入。確定？" % folder, yes, "匯入")
