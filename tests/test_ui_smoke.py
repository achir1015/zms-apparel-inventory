"""介面煙霧測試：把每個選單畫面都建立一次（不開視窗），確認沒有例外。"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zms import config  # noqa: E402
from zms.db import Database  # noqa: E402
from zms.server import EmbeddedServer, port_open  # noqa: E402
from zms.services import Service  # noqa: E402
from zms.ui.app import build_menu  # noqa: E402
from zms.ui.common import Ctx  # noqa: E402


class FakePage:
    def show_dialog(self, d):
        self.last = d

    def pop_dialog(self):
        pass

    def update(self):
        pass


@pytest.fixture(scope="module")
def ctx():
    cfg = config.load()
    srv = None
    if cfg.mode == "embedded":
        srv = EmbeddedServer(cfg)
        srv.start()  # 已在執行就沿用；port 被別的程式佔用會自動換埠
    db = Database(cfg)
    db.ensure_database()  # 跟程式啟動時一樣，先自動升級資料表
    svc = Service(db)
    svc.user = {"user_no": "test", "name": "測試", "is_admin": 1, "perms": set()}
    yield Ctx(FakePage(), svc)
    db.close()
    if srv:
        srv.stop()


def test_all_views_build(ctx):
    menu = build_menu(ctx, None)
    n = 0
    for group, icon, items in menu:
        for fid, name, factory in items:
            view = factory()
            assert view is not None, name
            n += 1
    assert n >= 30


def test_doc_editor_opens(ctx):
    from zms.ui.docs import DocView
    for code in ("GR", "TA", "CH", "ST"):
        v = DocView(ctx, code)
        v.update = lambda: None
        v.open(None)
        rows = ctx.svc.list_docs(code, limit=1)
        if rows:
            v.open(rows[0]["id"])


def test_print_html(ctx):
    from zms.ui.printing import doc_html
    rows = ctx.svc.list_docs("GR", limit=1)
    if rows:
        html = doc_html(ctx.svc, rows[0]["id"])
        assert rows[0]["doc_no"] in html and "店家出貨單" in html


def test_apparel_dialogs(ctx):
    from zms.ui.masters import MasterView
    from zms.ui.docs import DocView
    mv = MasterView(ctx, "products", "A1")
    mv.style_dialog()
    assert ctx.page.last is not None
    dv = DocView(ctx, "GR")
    dv.update = lambda: None
    dv.open(None)
    rows = ctx.svc.db.all("SELECT prod_no FROM products GROUP BY prod_no HAVING COUNT(*)>1 LIMIT 1")
    if rows:
        dv._matrix(rows[0]["prod_no"])
        assert "尺寸矩陣" in ctx.page.last.title.value


def test_reorder_views(ctx):
    from zms.ui import reorder
    for cls in (reorder.ReplenishView, reorder.TransferView, reorder.RecutView):
        v = cls(ctx)
        v.update = lambda: None
        v.calc()
    v = reorder.ReplenishView(ctx)
    v.update = lambda: None
    v.method.value = "level"
    v._method()
    v.calc()


def test_label_view(ctx):
    from zms.ui.labels_view import LabelView
    v = LabelView(ctx)
    v.update = lambda: None
    rows = ctx.svc.db.all("SELECT prod_no FROM products GROUP BY prod_no HAVING COUNT(*)>1 LIMIT 1")
    if rows:
        v.pn.value = rows[0]["prod_no"]
        v.load_variants()
        v.add_fields()
        assert v.grid.rows_data


def test_specials_and_box_ui(ctx):
    from zms.ui.specials import SpecialsView
    v = SpecialsView(ctx)
    v.edit(None)
    from zms.ui.docs import DocView
    rows = ctx.svc.list_docs("GR", limit=1)
    if rows:
        dv = DocView(ctx, "GR")
        dv.update = lambda: None
        dv.open(rows[0]["id"])
        dv._box_labels()
        assert "裝箱標籤" in ctx.page.last.title.value


def test_mobile_shell(ctx):
    """手機版四個分頁：建立、掃描加入、結帳、盤點儲存。"""
    from types import SimpleNamespace
    from zms.ui import mobile
    from zms import config as cfgmod
    page = ctx.page
    page.controls = []
    page.add = lambda *c: page.controls.extend(c)
    page.platform = None
    app = SimpleNamespace(page=page, svc=ctx.svc, cfg=cfgmod.load(), logout=lambda: None)
    sh = mobile.MobileShell(app)
    sh.show()
    assert [t[0] for t in sh.tabs] == ["總覽", "庫存", "銷貨", "盤點"]
    for i in range(4):
        sh.select(i)
    p = ctx.svc.db.one("SELECT * FROM products WHERE barcode='' AND name<>'' LIMIT 1")
    code = ctx.svc.barcode_text(p)
    st = sh.views["庫存"]
    st.update = lambda: None
    st.code.value = p["prod_no"]
    st.search()
    assert st.result.controls
    sales = sh.views["銷貨"]
    sales.update = lambda: None
    sales.code.update = sales.code.focus = lambda: None
    sales.code.value = code
    sales.scan()
    assert sales.lines.lines and sales.lines.lines[0]["qty"] == 1
    tk = sh.views["盤點"]
    tk.update = lambda: None
    tk.code.update = tk.code.focus = lambda: None
    tk.code.value = code
    tk.scan()
    tk.code.value = code
    tk.scan()
    assert tk.lines.lines[0]["qty"] == 2
