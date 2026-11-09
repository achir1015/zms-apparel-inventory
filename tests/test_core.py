"""核心邏輯測試：用獨立資料庫 zms_test（同一個內建 MariaDB 實例）。

執行：.venv\\Scripts\\python -m pytest -q tests
"""
import os
import sys

import pytest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zms import config  # noqa: E402
from zms.db import Database  # noqa: E402
from zms.services import BizError, Service  # noqa: E402
from zms.server import EmbeddedServer, port_open  # noqa: E402


@pytest.fixture(scope="module")
def svc():
    cfg = config.load()
    srv = None
    if cfg.mode == "embedded":
        srv = EmbeddedServer(cfg)
        srv.start()  # 已在執行就沿用；port 被別的程式佔用會自動換埠
    cfg.database = "zms_test"
    db = Database(cfg)
    db.ensure_database()
    for t in ("doc_lines", "stock_moves", "stock", "docs", "products", "shops", "warehouses", "vendors", "users",
              "user_perms", "ar_closings", "ar_payments", "ar_fees", "codes"):
        db.run("DELETE FROM %s" % t)
    s = Service(db)
    s.create_user("admin", "管理員", "1234", is_admin=True)
    s.login("admin", "1234")
    s.master_save("warehouses", dict(wh_no="W1", name="總倉", active=1), True)
    s.master_save("warehouses", dict(wh_no="W2", name="二倉", active=1), True)
    s.master_save("shops", dict(sh_no="S1", short_name="台北店", price_level=2, settle_mode="W", discount=80,
                                commission=0, active=1), True)
    s.master_save("shops", dict(sh_no="S2", short_name="新光專櫃", price_level=1, settle_mode="C", discount=100,
                                commission=30, active=1), True)
    s.master_save("vendors", dict(ma_no="V1", short_name="大廠", active=1), True)
    s.master_save("products", dict(prod_no="A100", color="01", size="M", name="襯衫", price1=1000, price2=900,
                                   price3=800, cost=400, active=1), True)
    s.master_save("products", dict(prod_no="A100", color="01", size="L", name="襯衫", price1=1000, price2=900,
                                   price3=800, cost=400, active=1), True)
    yield s
    db.run("DROP DATABASE zms_test")
    db.close()
    if srv:
        srv.stop()  # 測試自己開的資料庫，測完就關


def qty(s, t, loc, size="M"):
    return s.db.scalar("SELECT qty FROM stock WHERE loc_type=%s AND loc_no=%s AND prod_no='A100' AND color='01' "
                       "AND size=%s", (t, loc, size)) or 0


def test_login_fail(svc):
    with pytest.raises(BizError):
        Service(svc.db).login("admin", "wrong")


def test_flow(svc):
    pi = svc.save_doc("PI", dict(doc_date="115/11/01", wh_no="W1", ma_no="V1"),
                      [dict(prod_no="A100", color="01", size="M", qty=50),
                       dict(prod_no="A100", color="01", size="L", qty=30)])
    assert qty(svc, "W", "W1") == 50 and qty(svc, "W", "W1", "L") == 30
    h, lines = svc.get_doc(pi)
    assert h["doc_no"] == "PI1151101-001" and lines[0]["price"] == 400  # 進貨預設成本價

    gr = svc.save_doc("GR", dict(doc_date="115/11/02", wh_no="W1", sh_no="S1", discount=80),
                      [dict(prod_no="A100", color="01", size="M", qty=10)])
    assert qty(svc, "W", "W1") == 40 and qty(svc, "S", "S1") == 10
    h, lines = svc.get_doc(gr)
    assert lines[0]["price"] == 900 and h["total_amt"] == 7200  # 售價二 × 8 折

    # 修改出貨數量 → 庫存回沖再套用
    svc.save_doc("GR", dict(h, doc_date="115/11/02"), [dict(prod_no="A100", color="01", size="M", qty=15)], doc_id=gr)
    assert qty(svc, "W", "W1") == 35 and qty(svc, "S", "S1") == 15

    svc.save_doc("TA", dict(doc_date="115/11/03", sh_no="S1"), [dict(prod_no="A100", color="01", size="M", qty=4)])
    svc.save_doc("DR", dict(doc_date="115/11/04", sh_no="S1", wh_no="W1", discount=80),
                 [dict(prod_no="A100", color="01", size="M", qty=1)])
    assert qty(svc, "S", "S1") == 10 and qty(svc, "W", "W1") == 36
    svc.save_doc("MO", dict(doc_date="115/11/05", sh_no="S1", sh_no2="S2"),
                 [dict(prod_no="A100", color="01", size="M", qty=3)])
    assert qty(svc, "S", "S1") == 7 and qty(svc, "S", "S2") == 3
    svc.save_doc("CH", dict(doc_date="115/11/05", wh_no="W1", wh_no2="W2"),
                 [dict(prod_no="A100", color="01", size="L", qty=5)])
    assert qty(svc, "W", "W1", "L") == 25 and qty(svc, "W", "W2", "L") == 5

    # 訂單不動庫存
    svc.save_doc("OR", dict(doc_date="115/11/05", sh_no="S1"), [dict(prod_no="A100", color="01", size="M", qty=99)])
    assert qty(svc, "S", "S1") == 7

    # 刪除單據 → 庫存回沖
    svc.delete_doc(gr)
    assert qty(svc, "W", "W1") == 51 and qty(svc, "S", "S1") == -8

    # 校帳結果應與即時庫存相同
    before = svc.db.all("SELECT * FROM stock WHERE qty<>0 ORDER BY loc_type, loc_no, size")
    _, diff = svc.rebuild_stock()
    after = svc.db.all("SELECT * FROM stock WHERE qty<>0 ORDER BY loc_type, loc_no, size")
    assert diff == 0 and before == after


def test_validation(svc):
    with pytest.raises(BizError):
        svc.save_doc("GR", dict(wh_no="W1", sh_no="NOPE"), [dict(prod_no="A100", color="01", size="M", qty=1)])
    with pytest.raises(BizError):
        svc.save_doc("GR", dict(wh_no="W1", sh_no="S1"), [dict(prod_no="ZZZ", qty=1)])
    with pytest.raises(BizError):
        svc.save_doc("TA", dict(sh_no="S1"), [dict(prod_no="A100", color="01", size="M", qty=-1)])
    with pytest.raises(BizError):
        svc.master_delete("shops", ["S1"])  # 已有單據


def test_stocktake(svc):
    cur = qty(svc, "W", "W1")
    st = svc.save_doc("ST", dict(doc_date="115/11/20", wh_no="W1"),
                      [dict(prod_no="A100", color="01", size="M", qty=cur - 2)])
    _, diff = svc.stocktake_diff(st)
    assert any(x["size"] == "M" and x["diff"] == -2 for x in diff)
    svc.post_stocktake(st)
    assert qty(svc, "W", "W1") == cur - 2


def test_period_and_sales(svc):
    rows, used = svc.period_summary("W", "W1", "115/11/01", "115/11/30")
    m = next(r for r in rows if r["size"] == "M")
    assert m["opening"] == 0 and m["closing"] == qty(svc, "W", "W1")
    assert "PI" in used
    sales = svc.sales_analysis("115/11/01", "115/11/30", by="product")
    assert sales[0]["qty"] == 4


def test_ar(svc):
    svc.save_doc("TA", dict(doc_date="115/11/10", sh_no="S2"), [dict(prod_no="A100", color="01", size="M", qty=1)])
    svc.add_fee("S2", "115/11/15", "", 50)
    r = svc.ar_compute("S2", "202611")
    assert r["sales_amt"] == 1000 and r["commission_amt"] == 300 and r["amount"] == 650
    svc.ar_close("202611")
    svc.add_payment("S2", "115/12/01", 600, allowance=50)
    bal = {b["sh_no"]: b for b in svc.ar_balances()}
    assert bal["S2"]["billed"] - bal["S2"]["paid"] == 0
    hist = svc.ar_history("S2")
    assert hist[-1]["balance"] == 0


def test_perms(svc):
    svc.create_user("u1", "店員", "pw12")
    svc.set_perms("u1", ["D_TA", "Q1"])
    s2 = Service(svc.db)
    s2.login("u1", "pw12")
    assert s2.can("D_TA") and not s2.can("D_GR")
    with pytest.raises(BizError):
        svc.update_user("admin", "管理員", "", False, True)  # 不可移除最後一位管理員
    assert svc.db.scalar("SELECT is_admin FROM users WHERE user_no='admin'") == 1  # 已回復


def test_apparel(svc):
    svc.save_company(dict(name="測試服飾", prod_len=20, color_len=3, size_len=3,
                          size_group_a="XS*S*M*L*XL*", size_group_b="", size_group_c="", size_group_d=""))
    svc.save_code("color", "01", "白")
    svc.save_code("color", "02", "黑")
    svc.save_code("season", "SS", "春夏")
    made, skipped = svc.create_style(dict(prod_no="T200", name="T恤", year="2026", season="SS", price1=590,
                                          cost=200), ["02", "01"], ["XL", "S", "M"])
    assert (made, skipped) == (6, 0)
    assert svc.create_style(dict(prod_no="T200", name="T恤"), ["01"], ["S", "L"]) == (1, 1)
    assert svc.sort_sizes(["XL", "S", "L", "M"]) == ["S", "M", "L", "XL"]
    assert svc.sort_colors(["02", "01"]) == ["01", "02"]
    p = svc.master_get("products", ["T200", "01", "M"])
    assert p["season"] == "SS" and p["year"] == "2026"
    svc.save_doc("PI", dict(doc_date="115/11/01", wh_no="W1", ma_no="V1"),
                 [dict(prod_no="T200", color="01", size="S", qty=5), dict(prod_no="T200", color="02", size="XL", qty=7)])
    m = svc.matrix_for("T200", "W", "W1")
    assert m["sizes"] == ["S", "M", "L", "XL"] and m["colors"] == ["01", "02"] and m["stock"][("01", "S")] == 5
    sm = svc.stock_matrix("W", "W1", q="T200")
    assert sm[0]["sizes"] == ["S", "XL"] and sm[0]["total"] == 12
    svc.save_doc("TA", dict(doc_date="115/11/02", sh_no="S1"), [dict(prod_no="T200", color="01", size="M", qty=1)])
    assert svc.sales_analysis("115/11/01", "115/11/30", by="season")[0]["qty"] >= 1
    assert svc.sales_analysis("115/11/01", "115/11/30", by="size")


def test_reorder(svc):
    svc.create_style(dict(prod_no="R300", name="洋裝", price1=1200, cost=500), ["01"], ["S", "M"])
    # 總倉進 S 10 件、M 1 件；台北店 S 賣很快，專櫃 S 有存貨但沒賣
    svc.save_doc("PI", dict(doc_date="115/12/01", wh_no="W1", ma_no="V1"),
                 [dict(prod_no="R300", color="01", size="S", qty=10), dict(prod_no="R300", color="01", size="M", qty=1)])
    svc.save_doc("GR", dict(doc_date="115/12/02", wh_no="W1", sh_no="S1"), [dict(prod_no="R300", color="01", size="S", qty=2)])
    svc.save_doc("GR", dict(doc_date="115/12/02", wh_no="W1", sh_no="S2"), [dict(prod_no="R300", color="01", size="S", qty=6)])
    svc.save_doc("TA", dict(doc_date="115/12/10", sh_no="S1"), [dict(prod_no="R300", color="01", size="S", qty=2)])
    # W1 還有 S 2 件、M 1 件；S1 S 庫存 0、14 天賣 2 → 補到 14 天份＝2
    rows = svc.replenish_suggest("sales", "W1", ["S1", "S2"], days=14, cover=14, q="R300", end="115/12/14")
    r = next(x for x in rows if x["sh_no"] == "S1" and x["size"] == "S")
    assert (r["sold"], r["stock"], r["target"], r["suggest"], r["alloc"]) == (2, 0, 2, 2, 2)
    # 依庫存量（每規格 3 件）：倉庫只剩 M 1 件 → 只能配 1
    lv = svc.replenish_suggest("level", "W1", ["S1", "S2"], level=3, q="R300", end="115/12/14")
    assert sum(x["alloc"] for x in lv if x["size"] == "M") == 1
    nos = svc.make_ship_docs("W1", rows)
    assert nos and qty_of(svc, "S", "S1", "R300", "S") == 2
    # 轉貨：S2 有 6 件沒賣（保留 1）、S1 賣得快 → 建議 S2 調給 S1
    svc.save_doc("TA", dict(doc_date="115/12/12", sh_no="S1"), [dict(prod_no="R300", color="01", size="S", qty=2)])
    tr = svc.transfer_suggest(["S1", "S2"], days=14, cover=28, keep=1, q="R300", end="115/12/14")
    t = next(x for x in tr if x["size"] == "S")
    assert t["from_sh"] == "S2" and t["to_sh"] == "S1" and t["qty"] > 0
    svc.make_move_docs(tr)
    # 追加採購：全公司 14 天賣 4 件，補到 60 天份
    rc = svc.recut_suggest(days=14, cover=60, q="R300", end="115/12/14")
    assert rc and rc[0]["suggest"] > 0
    assert svc.make_purchase_doc("W1", "V1", rc).startswith("GE")


def qty_of(s, t, loc, p, size, color="01"):
    return s.db.scalar("SELECT qty FROM stock WHERE loc_type=%s AND loc_no=%s AND prod_no=%s AND color=%s AND size=%s",
                       (t, loc, p, color, size)) or 0


def test_labels(svc):
    from zms import labels
    svc.save_code("fabric", "C1", "棉100%")
    svc.create_style(dict(prod_no="L-500", name="亞麻襯衫", price1=990, price2=890, fabric="C1"), ["01"], ["M", "L"])
    items = svc.label_items([("L-500", "01", "M", 2), ("L-500", "01", "L", 0), ("NOPE", "", "", 1)])
    assert len(items) == 1 and items[0]["copies"] == 2 and items[0]["code"] == "L-500-01-M"
    assert items[0]["fabric_name"] == "棉100%"
    # 吊牌條碼掃回來要能找到同一個商品（貨號本身含 -）
    p = svc.product_by_code(items[0]["code"])
    assert (p["prod_no"], p["color"], p["size"]) == ("L-500", "01", "M")
    for lay in labels.LAYOUTS:
        h = labels.label_html(items, layout=lay, price_level="2", company="測試服飾")
        assert h.count('class="lb"') == 2 and "NT$ 890" in h and "<svg" in h
    assert "NT$" not in labels.label_html(items, price_level="0")
    doc = svc.save_doc("PI", dict(doc_date="115/12/20", wh_no="W1", ma_no="V1"),
                       [dict(prod_no="L-500", color="01", size="L", qty=3)])
    assert svc.label_items_from_doc(doc)[0]["copies"] == 3


def test_specials(svc):
    svc.create_style(dict(prod_no="SP1", name="特價外套", price1=2000, price2=1800, cost=800), ["01"], ["M", "L"])
    # 全店 8 折（12 月）、S1 店 M 號特價 1200（12/10～12/20）
    svc.save_special(dict(sh_no="", prod_no="SP1", start_date="115/12/01", end_date="115/12/31", discount=80, memo="週年慶"))
    svc.save_special(dict(sh_no="S1", prod_no="SP1", size="M", start_date="115/12/10", end_date="115/12/20",
                          special_price=1200))
    p_m = svc.master_get("products", ["SP1", "01", "M"])
    p_l = svc.master_get("products", ["SP1", "01", "L"])
    # S2 用售價一 2000 → 八折 1600；S1 用售價二 1800 → M 號特價 1200、L 號八折 1440
    assert svc.price_info("TA", p_m, dict(sh_no="S2", doc_date="115/12/15")) == (Decimal(1600), "特價（週年慶）")
    assert svc.price_info("TA", p_m, dict(sh_no="S1", doc_date="115/12/15"))[0] == 1200
    assert svc.price_info("TA", p_l, dict(sh_no="S1", doc_date="115/12/15"))[0] == 1440
    assert svc.price_info("TA", p_m, dict(sh_no="S1", doc_date="116/01/05")) == (Decimal(1800), "")   # 過期
    assert svc.price_info("PI", p_m, dict(doc_date="115/12/15"))[0] == 800                        # 進貨用成本
    did = svc.save_doc("TA", dict(doc_date="115/12/15", sh_no="S2"), [dict(prod_no="SP1", color="01", size="L", qty=1)])
    _, lines = svc.get_doc(did)
    assert lines[0]["price"] == 1600 and lines[0]["memo"].startswith("特價")
    with pytest.raises(BizError):
        svc.save_special(dict(prod_no="SP1", start_date="115/12/10", end_date="115/12/01", discount=80))
    with pytest.raises(BizError):
        svc.save_special(dict(prod_no="SP1", start_date="115/12/01", end_date="115/12/31"))
    assert len(svc.list_specials("shop")) == 1


def test_box_labels(svc):
    from zms import labels
    svc.master_save("shops", dict(sh_no="S1", short_name="台北店", full_name="台北旗艦店", tel1="02-1234-5678",
                                  address3="台北市信義區松高路 1 號", price_level=2, settle_mode="W", discount=80,
                                  commission=0, active=1), False)
    did = svc.save_doc("GR", dict(doc_date="115/12/05", wh_no="W1", sh_no="S1"), [dict(prod_no="T200", color="01", size="M", qty=3)])
    info = svc.box_info(did)
    assert info["to"]["name"] == "台北旗艦店" and "松高路" in info["to"]["address"]
    for lay in labels.BOX_LAYOUTS:
        h = labels.box_html(info, boxes=3, layout=lay)
        assert h.count('class="lb"') == 3 and "第 <b>3</b> / 3 箱" in h and info["doc_no"] in h
    pi = svc.list_docs("PI", limit=1)[0]["id"]
    with pytest.raises(BizError):
        svc.box_info(pi)


def test_mobile_user(svc):
    """手機專用帳號：能讀寫資料，但不能改資料表結構。"""
    import pymysql
    from zms import lan
    cfg = svc.db.cfg
    pw = lan.ensure_mobile_user(svc.db, cfg)
    try:
        c = pymysql.connect(host=cfg.host, port=int(cfg.port), user=lan.MOBILE_USER, password=pw, database=cfg.database)
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products")
            assert cur.fetchone()[0] > 0
            with pytest.raises(pymysql.err.OperationalError):
                cur.execute("DROP TABLE products")
        c.close()
        m = Service(Database(config.Config(**{**cfg.__dict__, "user": lan.MOBILE_USER, "password": pw})))
        m.login("admin", "1234")
        did = m.save_doc("TA", dict(doc_date="115/12/21", sh_no="S1"), [dict(prod_no="T200", color="01", size="M", qty=1)])
        assert did
    finally:
        lan.drop_mobile_user(svc.db)
    assert lan.lan_ips() is not None


def test_migrate(svc):
    """搬移：複製到另一個資料庫，筆數一致，原資料庫不變。"""
    from zms import migrate
    src_cfg = svc.db.cfg
    before = migrate.exact_counts(svc.db, ["products", "docs", "doc_lines", "stock"])
    target = config.Config(**{**src_cfg.__dict__})
    target.database = "zms_migtest"
    try:
        assert not migrate.target_has_data(target)
        copied = migrate.migrate(svc.db, target, log=lambda m: None)
        assert copied["products"] == before["products"] and copied["docs"] == before["docs"]
        assert migrate.target_has_data(target)
        t = Service(Database(target))
        t.login("admin", "1234")                      # 使用者與密碼雜湊也一起搬過去
        assert t.db.scalar("SELECT SUM(qty) FROM stock") == svc.db.scalar("SELECT SUM(qty) FROM stock")
        t.db.close()
        assert migrate.exact_counts(svc.db, ["products", "docs", "doc_lines", "stock"]) == before
    finally:
        svc.db.run("DROP DATABASE IF EXISTS zms_migtest")
