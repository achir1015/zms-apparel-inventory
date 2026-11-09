"""主程式框架：啟動資料庫 → 登入 → 主畫面（左側功能群組、上方功能按鈕）。"""
import logging
import os
import threading

import flet as ft

from .. import APP_NAME, APP_VERSION, config
from ..db import Database
from ..doctypes import DOC_TYPES
from ..server import EmbeddedServer
from ..services import BizError, Service
from . import admin, ar, docs, labels_view, masters, reorder, reports, specials
from .common import PRIMARY, Ctx, fmt, tf

log = logging.getLogger("zms")
if not log.handlers:
    _h = logging.FileHandler(os.path.join(config.data_dir(), "zms.log"), encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

# 群組：(名稱, 圖示, [(功能代號, 名稱, 建立畫面函式)])
def build_menu(ctx, app):
    s = ctx.svc
    return [
        ("首頁", ft.Icons.HOME_OUTLINED, [("", "首頁", lambda: Dashboard(ctx, app))]),
        ("基本資料", ft.Icons.INVENTORY_2_OUTLINED, [
            ("A1", "產品", lambda: masters.MasterView(ctx, "products", "A1")),
            ("A2", "店家", lambda: masters.MasterView(ctx, "shops", "A2")),
            ("A3", "廠商", lambda: masters.MasterView(ctx, "vendors", "A3")),
            ("A4", "人員", lambda: masters.MasterView(ctx, "employees", "A4")),
            ("A5", "倉庫", lambda: masters.MasterView(ctx, "warehouses", "A5")),
            ("A6", "代碼", lambda: masters.CodesView(ctx)),
            ("A7", "吊牌標籤", lambda: labels_view.LabelView(ctx)),
            ("A8", "特價品", lambda: specials.SpecialsView(ctx))]),
        ("倉庫單據", ft.Icons.WAREHOUSE_OUTLINED,
         [("D_" + d.code, d.name.replace("倉庫", "").replace("公司", ""), (lambda c=d.code: docs.DocView(ctx, c)))
          for d in DOC_TYPES if d.group == "倉庫"]),
        ("店家單據", ft.Icons.STOREFRONT_OUTLINED,
         [("D_" + d.code, d.name.replace("店家", ""), (lambda c=d.code: docs.DocView(ctx, c)))
          for d in DOC_TYPES if d.group == "店家"]),
        ("查詢報表", ft.Icons.QUERY_STATS, [
            ("Q1", "庫存查詢", lambda: reports.StockView(ctx)),
            ("Q1", "庫存尺寸分布", lambda: reports.StockMatrixView(ctx)),
            ("Q2", "進銷存", lambda: reports.PeriodView(ctx)),
            ("Q3", "銷售分析", lambda: reports.SalesView(ctx)),
            ("Q4", "訂單／採購追蹤", lambda: reports.TrackView(ctx)),
            ("Q5", "產品異動明細", lambda: reports.HistoryView(ctx))]),
        ("補貨調度", ft.Icons.SYNC_ALT, [
            ("R1", "補貨建議", lambda: reorder.ReplenishView(ctx)),
            ("R2", "轉貨建議", lambda: reorder.TransferView(ctx)),
            ("R3", "追加採購建議", lambda: reorder.RecutView(ctx))]),
        ("應收帳款", ft.Icons.PAYMENTS_OUTLINED, [
            ("G1", "結帳", lambda: ar.CloseView(ctx)),
            ("G2", "收款沖帳", lambda: ar.PaymentView(ctx)),
            ("G3", "店家費用", lambda: ar.FeeView(ctx)),
            ("G4", "應收查詢", lambda: ar.BalanceView(ctx))]),
        ("系統維護", ft.Icons.SETTINGS_OUTLINED, [
            ("M1", "使用者與權限", lambda: admin.UsersView(ctx)),
            ("M2", "公司設定", lambda: admin.CompanyView(ctx)),
            ("M3|M4|M5", "工具（校帳／備份／匯入）", lambda: admin.ToolsView(ctx, app))]),
    ]


class Dashboard(ft.Column):
    def __init__(self, ctx, app):
        d = ctx.svc.dashboard()
        comp = ctx.svc.company() or {}

        def card(title, value, icon, color):
            return ft.Container(ft.Row([ft.Icon(icon, size=36, color=color),
                                        ft.Column([ft.Text(title, size=13, color=ft.Colors.GREY_700),
                                                   ft.Text(value, size=24, weight=ft.FontWeight.BOLD)], spacing=0)]),
                                padding=16, border_radius=10, bgcolor=ft.Colors.WHITE, width=230,
                                border=ft.Border.all(1, ft.Colors.GREY_200))
        from ..doctypes import BY_CODE
        recent = ft.Column([ft.Row([ft.Text(BY_CODE[r["doc_type"]].name, width=80), ft.Text(r["doc_no"], width=130),
                                    ft.Text(fmt(r["doc_date"]), width=90), ft.Text(r["sh_no"] or r["wh_no"], width=100),
                                    ft.Text(fmt(r["total_qty"], "n"), width=60, text_align=ft.TextAlign.RIGHT),
                                    ft.Text(fmt(r["total_amt"]), width=100, text_align=ft.TextAlign.RIGHT)])
                            for r in d["recent"]] or [ft.Text("尚無單據", color=ft.Colors.GREY)], spacing=4)
        super().__init__([
            ft.Text(comp.get("name") or "", size=26, weight=ft.FontWeight.BOLD, color=PRIMARY),
            ft.Text("歡迎，%s" % ctx.svc.user["name"], size=14, color=ft.Colors.GREY_700),
            ft.Row([card("產品品項", fmt(d["products"], "n"), ft.Icons.CHECKROOM, ft.Colors.INDIGO),
                    card("往來店家", fmt(d["shops"], "n"), ft.Icons.STOREFRONT, ft.Colors.TEAL),
                    card("倉庫庫存（件）", fmt(d["wh_qty"]), ft.Icons.WAREHOUSE, ft.Colors.BROWN),
                    card("店家庫存（件）", fmt(d["sh_qty"]), ft.Icons.SHELVES, ft.Colors.DEEP_ORANGE),
                    card("本月出貨金額", fmt(d["month_ship"]), ft.Icons.LOCAL_SHIPPING, ft.Colors.BLUE),
                    card("本月銷貨金額", fmt(d["month_sales"]), ft.Icons.POINT_OF_SALE, ft.Colors.GREEN),
                    card("今日單據", fmt(d["today_docs"], "n"), ft.Icons.RECEIPT_LONG, ft.Colors.PURPLE)],
                   wrap=True, spacing=14, run_spacing=14),
            ft.Text("最近單據", size=18, weight=ft.FontWeight.BOLD),
            ft.Container(recent, padding=12, bgcolor=ft.Colors.WHITE, border_radius=10,
                         border=ft.Border.all(1, ft.Colors.GREY_200)),
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.cfg = config.load()
        self.server = None
        self.db = None
        self.svc = None
        self.mobile = config.is_mobile_env() or page.platform in (ft.PagePlatform.IOS, ft.PagePlatform.ANDROID)
        if self.mobile and self.cfg.mode == "embedded":
            self.cfg.mode = "external"   # 手機不能跑資料庫，一律連電腦／伺服器

    # ------------------------------------------------ 啟動
    def start(self):
        p = self.page
        p.title = APP_NAME
        p.fonts = {"NotoSansTC": "fonts/NotoSansTC-VF.ttf"}  # 內附字型：網頁／手機也有完整中文字
        p.theme = ft.Theme(color_scheme_seed=PRIMARY, font_family="NotoSansTC")
        p.theme_mode = ft.ThemeMode.LIGHT
        p.bgcolor = "#F4F6FA"
        p.padding = 0
        if self.mobile:
            p.padding = 0
        try:
            p.window.width, p.window.height = 1360, 860
            p.window.min_width, p.window.min_height = 1000, 640
            p.window.prevent_close = True
            p.window.on_event = self._on_window
        except Exception:
            pass
        if self.mobile and not self.cfg.host:
            self.first_mobile_setup()
            return
        self.boot_screen()

    def first_mobile_setup(self):
        p = self.page
        p.controls.clear()
        p.add(ft.Container(ft.Column([
            ft.Icon(ft.Icons.PHONE_IPHONE, size=56, color=PRIMARY),
            ft.Text(APP_NAME, size=22, weight=ft.FontWeight.BOLD, color=PRIMARY, text_align=ft.TextAlign.CENTER),
            ft.Text("第一次使用：請連到電腦上的進銷存資料庫。\n在電腦版「系統維護 → 工具 → 手機連線」開啟「允許手機連線」，"
                    "畫面會顯示要輸入的伺服器、帳號與密碼。", size=14, text_align=ft.TextAlign.CENTER),
            ft.FilledButton("設定連線", icon=ft.Icons.STORAGE, on_click=lambda e: self.db_settings(), height=46)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, spacing=18),
            alignment=ft.Alignment.CENTER, expand=True, padding=24))
        p.update()

    def boot_screen(self):
        p = self.page
        self.status = ft.Text("正在啟動資料庫…" if self.cfg.mode == "embedded" else
                              "正在連線 %s:%s…" % (self.cfg.host, self.cfg.port), size=16)
        self.ring = ft.ProgressRing()
        self.boot_btn = ft.OutlinedButton("資料庫連線設定", icon=ft.Icons.STORAGE, visible=False,
                                          on_click=lambda e: self.db_settings())
        p.controls.clear()
        p.add(ft.Container(ft.Column([ft.Text(APP_NAME, size=30, weight=ft.FontWeight.BOLD, color=PRIMARY),
                                      self.ring, self.status, self.boot_btn],
                                     horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                     alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                           alignment=ft.Alignment.CENTER, expand=True))
        p.update()
        p.run_thread(self._boot)

    def _boot(self):
        try:
            log.info("boot: mode=%s bin=%s data=%s port=%s", self.cfg.mode, self.cfg.mariadb_bin, self.cfg.datadir,
                     self.cfg.port)
            if self.cfg.mode == "embedded":
                self.server = EmbeddedServer(self.cfg)
                self.server.start()
            log.info("boot: server ready")
            self.db = Database(self.cfg)
            if self.mobile:
                # 手機帳號只有讀寫資料權限；資料表由電腦版建立與升級
                if not self.db.scalar("SELECT v FROM meta WHERE k='schema_version'"):
                    raise RuntimeError("這個資料庫還沒有進銷存資料，請先在電腦上開啟一次進銷存系統。")
            else:
                self.db.ensure_database()
            config.save(self.cfg)
            self.svc = Service(self.db)
            self.ctx = Ctx(self.page, self.svc)
            log.info("boot: show login")
            self.show_login()
            log.info("boot: done")
        except Exception as e:
            log.exception("boot failed")
            from ..db import friendly_error
            self.status.value = "資料庫連線失敗：\n%s" % (friendly_error(e) if self.cfg.mode == "external" else e)
            self.status.color = ft.Colors.RED
            self.ring.visible = False
            self.boot_btn.visible = True
            self.page.update()

    # ------------------------------------------------ 資料庫連線設定
    def db_settings(self):
        """選擇內建 MariaDB 或連既有的 MariaDB 伺服器（例如筆電上已安裝的那套）。"""
        p, c = self.page, self.cfg
        mode = ft.RadioGroup(value="external" if self.mobile else c.mode, content=ft.Column([
            ft.Radio(value="embedded", label="內建 MariaDB（程式自動啟動、關閉即停止，資料放在本機）",
                     visible=not self.mobile),
            ft.Radio(value="external", label="連到既有的 MariaDB 伺服器（本機已安裝的、或公司伺服器）")], spacing=0))
        host = tf("伺服器", c.host if c.mode == "external" else "127.0.0.1", width=200)
        port = tf("連接埠", str(c.port if c.mode == "external" else 3306), width=100)
        user = tf("帳號", c.user if c.mode == "external" else "root", width=160)
        pw = tf("密碼", c.password if c.mode == "external" else "", width=200, password=True, can_reveal_password=True)
        dbn = tf("資料庫名稱", c.database, width=200)
        ext = ft.Column([ft.Row([host, port], wrap=True), ft.Row([user, pw], wrap=True), dbn],
                        visible=c.mode == "external")
        msg = ft.Text("", size=13, selectable=True)

        def on_mode(e):
            ext.visible = mode.value == "external"
            p.update()
        mode.on_change = on_mode

        def test(e):
            from ..db import test_connection
            if mode.value != "external":
                msg.value, msg.color = "內建模式不需要測試。", ft.Colors.GREY_700
            else:
                ok, text = test_connection(host.value.strip(), port.value.strip() or 3306, user.value.strip(),
                                           pw.value, dbn.value.strip() or "zms_inventory")
                msg.value, msg.color = text, ft.Colors.GREEN_700 if ok else ft.Colors.RED
            p.update()

        def save(e):
            try:
                if mode.value == "external":
                    c.mode, c.host, c.port = "external", host.value.strip(), int(port.value.strip() or 3306)
                    c.user, c.password = user.value.strip(), pw.value
                    c.database = dbn.value.strip() or "zms_inventory"
                else:
                    if c.mode != "embedded":
                        fresh = config.Config()
                        c.mode, c.host, c.user = "embedded", "127.0.0.1", "root"
                        c.port, c.database = fresh.port, "zms_inventory"
                        c.password = c.extra.get("embedded_password") or ""
                    c.database = dbn.value.strip() or c.database
            except ValueError:
                msg.value, msg.color = "連接埠要是數字", ft.Colors.RED
                p.update()
                return
            p.pop_dialog()
            self.restart()

        # 切到外部前記住內建實例的密碼，切回來時還能用
        if c.mode == "embedded" and c.password:
            c.extra["embedded_password"] = c.password
        p.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("資料庫連線設定"),
            content=ft.Container(ft.Column([mode, ext, msg], tight=True, scroll=ft.ScrollMode.AUTO),
                                 width=None if self.mobile else 560),
            actions=[ft.TextButton("取消", on_click=lambda e: p.pop_dialog()),
                     ft.OutlinedButton("測試連線", icon=ft.Icons.WIFI_TETHERING, on_click=test),
                     ft.FilledButton("儲存並重新連線", icon=ft.Icons.SAVE, on_click=save)]))

    def restart(self):
        """套用新設定：關掉目前連線與內建伺服器，重新啟動。"""
        self.shutdown()
        self.server = self.db = self.svc = None
        if self.cfg.mode == "embedded" and not self.cfg.password:
            self.cfg.password = config.load().password
        config.save(self.cfg)
        self.boot_screen()

    async def _on_window(self, e):
        if getattr(e, "type", None) == ft.WindowEventType.CLOSE or str(getattr(e, "type", "")) .endswith("close"):
            self.shutdown()
            await self.page.window.destroy()

    def shutdown(self):
        try:
            if self.svc and self.svc.user:
                self.svc.log("logout", self.svc.uid)
            if self.db:
                self.db.close()
        except Exception:
            pass
        if self.server:
            self.server.stop()

    # ------------------------------------------------ 登入
    def show_login(self):
        p = self.page
        first = not self.svc.has_users()
        uid = tf("使用者代號", self.cfg.last_user or ("admin" if first else ""), width=300, autofocus=not first)
        name = tf("姓名", "系統管理員", width=300, visible=first)
        pw = tf("密碼", "", width=300, password=True, can_reveal_password=True, autofocus=not first and bool(uid.value))
        pw2 = tf("再輸入一次密碼", "", width=300, password=True, visible=first)
        msg = ft.Text("", color=ft.Colors.RED)

        def go(e=None):
            try:
                if first:
                    if (pw.value or "") != (pw2.value or ""):
                        raise BizError("兩次密碼不一樣")
                    if len(pw.value or "") < 4:
                        raise BizError("密碼至少 4 個字")
                    self.svc.create_user(uid.value, name.value, pw.value, is_admin=True)
                self.svc.login(uid.value, pw.value)
            except BizError as ex:
                msg.value = str(ex)
                p.update()
                return
            self.cfg.last_user = self.svc.uid
            config.save(self.cfg)
            self.show_main()

        pw.on_submit = go
        pw2.on_submit = go
        box = ft.Container(ft.Column([
            ft.Icon(ft.Icons.INVENTORY, size=56, color=PRIMARY),
            ft.Text(APP_NAME, size=24, weight=ft.FontWeight.BOLD, color=PRIMARY),
            ft.Text("第一次使用：請建立系統管理員帳號" if first else "請登入", size=14, color=ft.Colors.GREY_700),
            uid, name, pw, pw2, msg,
            ft.FilledButton("建立並登入" if first else "登入", width=300, height=44, on_click=go),
            ft.TextButton("資料庫連線設定", icon=ft.Icons.STORAGE, on_click=lambda e: self.db_settings()),
            ft.Text("v%s　資料庫：%s" % (APP_VERSION, "內建" if self.cfg.mode == "embedded" else
                                        "%s:%s" % (self.cfg.host, self.cfg.port)), size=11, color=ft.Colors.GREY_500)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12, tight=True),
            padding=20 if self.mobile else 36, bgcolor=ft.Colors.WHITE, border_radius=16,
            width=340 if self.mobile else 400,
            shadow=ft.BoxShadow(blur_radius=24, color="#22000000"))
        p.controls.clear()
        p.add(ft.Column([ft.Container(box, alignment=ft.Alignment.CENTER, padding=20)],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.AUTO, expand=True))
        p.update()

    # ------------------------------------------------ 主畫面
    def allowed(self, fid):
        if not fid:
            return True
        return any(self.svc.can(f) for f in fid.split("|"))

    def show_main(self):
        p = self.page
        if self.mobile:
            from .mobile import MobileShell
            MobileShell(self).show()
            return
        self.menu = [(g, ic, [it for it in items if self.allowed(it[0])]) for g, ic, items in build_menu(self.ctx, self)]
        self.menu = [m for m in self.menu if m[2]]
        self.rail = ft.NavigationRail(
            selected_index=0, extended=True, min_extended_width=170, bgcolor=ft.Colors.WHITE,
            destinations=[ft.NavigationRailDestination(icon=ic, label=g) for g, ic, _ in self.menu],
            on_change=lambda e: self.select_group(e.control.selected_index),
            leading=ft.Container(ft.Text("資料助秘\n服飾業進銷存", size=16, weight=ft.FontWeight.BOLD, color=PRIMARY,
                                         text_align=ft.TextAlign.CENTER), padding=ft.Padding.only(top=12, bottom=12)),
            trailing=ft.Column([ft.Divider(), ft.Text(self.svc.user["name"], size=13),
                                ft.TextButton("變更密碼", icon=ft.Icons.KEY, on_click=self.change_pw),
                                ft.TextButton("登出", icon=ft.Icons.LOGOUT, on_click=lambda e: self.logout())],
                               horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        self.subbar = ft.Row(wrap=True, spacing=8)
        self.body = ft.Container(expand=True, padding=16)
        p.controls.clear()
        p.add(ft.Row([self.rail, ft.VerticalDivider(width=1),
                      ft.Column([ft.Container(self.subbar, padding=ft.Padding.only(left=16, right=16, top=10)),
                                 self.body], expand=True, spacing=0)], expand=True, spacing=0))
        self.select_group(0)

    def select_group(self, gi):
        self.gi = gi
        self.rail.selected_index = gi
        self.select_item(0)

    def select_item(self, ii):
        g, ic, items = self.menu[self.gi]
        self.subbar.controls = [] if len(items) == 1 else [
            (ft.FilledButton if i == ii else ft.OutlinedButton)(it[1], on_click=lambda e, i=i: self.select_item(i))
            for i, it in enumerate(items)]
        try:
            self.body.content = items[ii][2]()
        except Exception as ex:
            self.body.content = ft.Text("畫面載入失敗：%s" % ex, color=ft.Colors.RED)
        self.page.update()

    def change_pw(self, e):
        old = tf("舊密碼", "", password=True, width=260)
        new = tf("新密碼", "", password=True, width=260)
        new2 = tf("再輸入一次", "", password=True, width=260)

        def save(ev):
            if new.value != new2.value:
                self.ctx.toast("兩次新密碼不一樣", True)
                return
            if self.ctx.guard(self.svc.change_password, old.value, new.value, ok="密碼已變更"):
                self.page.pop_dialog()
        self.page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("變更密碼"),
                                             content=ft.Column([old, new, new2], tight=True),
                                             actions=[ft.TextButton("取消", on_click=lambda ev: self.page.pop_dialog()),
                                                      ft.FilledButton("儲存", on_click=save)]))

    def logout(self):
        self.svc.log("logout", self.svc.uid)
        self.svc.user = None
        self.show_login()


def main(page: ft.Page):
    App(page).start()
