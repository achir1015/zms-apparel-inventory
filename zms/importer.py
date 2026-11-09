"""舊系統（凱新 VD20 進銷存，KS 資料夾）DBF → MariaDB 匯入。

做法：清空新系統的基本資料與單據 → 匯入 → 依單據重算庫存。
對照規則見 analysis/分析報告.md。
"""
import datetime as _dt
from decimal import Decimal

from . import dates
from .dbf import find_table, read_dbf
from .security import hash_pw

# 單據：新代碼 → (主檔, 明細, 單號欄, 日期欄, 表頭對照{新:舊}, 明細單價欄, 數量正負)
DOC_MAP = {
    "PI": ("P_PURI", "P_PURI_SUB", "PI_NO", "PI_DATE", dict(wh_no="WH_NO", ma_no="MA_NO", ref_no="GE_NO", bill_no="PI_BILL", memo="PI_MEMO"), "P_COST", 1),
    "PO": ("P_PURO", "P_PURO_SUB", "PO_NO", "PO_DATE", dict(wh_no="WH_NO", ma_no="MA_NO", bill_no="PO_BILL", memo="PO_MEMO"), "P_COST", 1),
    "CH": ("P_CHANG", "P_CHANG_SUB", "CH_NO", "CH_DATE", dict(wh_no="PO_WH", wh_no2="PI_WH", memo="CH_MEMO"), "P_COST", 1),
    "NU": ("P_NUL", "P_NUL_SUB", "NU_NO", "NU_DATE", dict(wh_no="WH_NO", reason="NU_REASON", memo="NU_MEMO"), "P_COST", 1),
    "GE": ("P_GET", "P_GET_SUB", "GE_NO", "GE_DATE", dict(wh_no="WH_NO", ma_no="MA_NO", memo="GE_MEMO"), "P_COST", 1),
    "MA": ("P_MATATE", "P_MATATE_SUB", "MA_NO", "MA_DATE", dict(wh_no="WH_NO", reason="MA_REASON", memo="MA_MEMO"), "P_PRICE", -1),
    "ST": ("P_STK", "P_STK_SUB", "ST_NO", "ST_DATE", dict(wh_no="WH_NO", memo="ST_MEMO"), "P_PRICE", 1),
    "GR": ("P_GRES", "P_GRES_SUB", "GR_NO", "GR_DATE", dict(wh_no="WH_NO", sh_no="SH_NO", per_no="PER_NO", bill_no="GR_BILL", memo="GR_MEMO", discount="GPER_NO"), "P_PRICE", 1),
    "DR": ("P_DREW", "P_DREW_SUB", "DR_NO", "DR_DATE", dict(wh_no="WH_NO", sh_no="SH_NO", per_no="PER_NO", bill_no="DR_BILL", memo="DR_MEMO", discount="DPER_NO"), "P_PRICE", 1),
    "TA": ("P_TAKE", "P_TAKE_SUB", "TA_NO", "TA_DATE", dict(sh_no="SH_NO", per_no="PER_NO1", memo="TA_MEMO"), "P_PRICE", 1),
    "MO": ("P_MOVE", "P_MOVE_SUB", "MO_NO", "MO_DATE", dict(sh_no="SH_NO", sh_no2="MI_SH_NO", per_no="PER_NO", memo="MO_MEMO"), "P_PRICE", 1),
    "OR": ("P_ORDER", "P_ORDER_SUB", "OR_NO", "OR_DATE", dict(sh_no="SH_NO", per_no="PER_NO", memo="OR_MEMO", discount="OPER_NO"), "P_PRICE", 1),
    "TR": ("P_TRANS", "P_TRANS_SUB", "TR_NO", "TR_DATE", dict(sh_no="SH_NO", reason="TR_REASON", memo="TR_MEMO"), "P_PRICE", 1),
    "CK": ("P_CHECK", "P_CHECK_SUB", "CK_NO", "CK_DATE", dict(sh_no="SH_NO", per_no="PER_NO", memo="CK_MEMO"), "P_PRICE", 1),
}

CODE_MAP = [("P_COLOR", "color", "PROD_CO", "CO_NA", "C_MEMO"), ("P_SIZE", "size", "PROD_SI", "SI_NA", "SI_MEMO"),
            ("P_CLASS", "class", "P_CLASS", "CL_NA", "CL_MOME"), ("P_KIND", "brand", "P_KIND", "KI_NA", "KI_MEMO"),
            ("P_SERI", "series", "P_SERI", "SE_NA", "SE_MEMO"), ("P_REASON", "reason", "REA_NO", "REA_NA", "REA_MOME"),
            ("P_SUBJECT", "subject", "SU_NO", "SU_NA", "MEMO")]


def _d(v):
    """舊日期字串 YYYYMMDD（偶有民國）→ date"""
    if isinstance(v, _dt.date):
        return v
    s = (v or "").strip().replace("/", "").replace("-", "")[:8]
    if not s:
        return None
    try:
        return dates.parse(s)
    except ValueError:
        return None


def _s(v, n):
    return ("" if v is None else str(v)).strip()[:n]


class LegacyImporter:
    def __init__(self, svc, folder, log=print):
        self.svc, self.db, self.folder, self.log = svc, svc.db, folder, log
        self.stats = {}

    def table(self, name):
        p = find_table(self.folder, name)
        return read_dbf(p) if p else []

    def run(self, import_users=True):
        if not find_table(self.folder, "P_SYSTEM") and not find_table(self.folder, "PROD"):
            raise ValueError("這個資料夾看起來不是舊系統資料（找不到 P_SYSTEM.DBF / PROD.DBF）")
        db = self.db
        with db.tx():
            for t in ("doc_lines", "stock_moves", "stock", "docs", "products", "codes", "shops", "vendors",
                      "warehouses", "employees", "ar_closings", "ar_payments", "ar_fees"):
                db.run("DELETE FROM %s" % t)
            self._company()
            self._codes()
            self._masters()
            if import_users:
                self._users()
            for code in DOC_MAP:
                self._docs(code)
        n, _ = self.svc.rebuild_stock()
        self.log("庫存重算完成（%d 張單據）" % n)
        self.svc.log("legacy_import", self.folder, str(self.stats))
        return self.stats

    def _count(self, k, n):
        self.stats[k] = n
        self.log("%s：%d 筆" % (k, n))

    def _company(self):
        rows = self.table("P_SYSTEM")
        if not rows:
            return
        r = rows[0]
        self.db.run("UPDATE company SET name=%s, prod_len=%s, color_len=%s, size_len=%s, size_group_a=%s, "
                    "size_group_b=%s, size_group_c=%s, size_group_d=%s WHERE id=1",
                    (_s(r.get("SYS_NA"), 60) or "我的公司", int(r.get("SYS_L1") or 20), int(r.get("SYS_L2") or 3),
                     int(r.get("SYS_L3") or 3), _s(r.get("SYS_A"), 120), _s(r.get("SYS_B"), 120),
                     _s(r.get("SYS_C"), 120), _s(r.get("SYS_D"), 120)))
        self._count("公司設定", 1)

    def _codes(self):
        for tbl, kind, k, n, m in CODE_MAP:
            rows = [(kind, _s(r.get(k), 10), _s(r.get(n), 40), _s(r.get(m), 60)) for r in self.table(tbl)
                    if _s(r.get(k), 10)]
            self.db.many("REPLACE INTO codes (kind, code, name, memo) VALUES (%s,%s,%s,%s)", rows)
            self._count("代碼-" + kind, len(rows))
        rows = [("unit", _s(r.get("UNIT_NO"), 10), _s(r.get("UNIT_NA"), 40), "") for r in self.table("UNIT")
                if _s(r.get("UNIT_NO"), 10)]
        self.db.many("REPLACE INTO codes (kind, code, name, memo) VALUES (%s,%s,%s,%s)", rows)

    def _masters(self):
        db = self.db
        wh = [(_s(r["WH_NO"], 4), _s(r.get("WH_NA") or r.get("WH_NAME") or r.get("WH_AREA"), 30),
               _s(r.get("WH_NAME"), 20), _s(r.get("WH_TEL"), 20), _s(r.get("WH_AREA"), 20), _s(r.get("WH_ADD"), 100),
               _s(r.get("WH_MEMO"), 60)) for r in self.table("P_WH") if _s(r.get("WH_NO"), 4)]
        db.many("REPLACE INTO warehouses (wh_no, name, contact, tel, area, address, memo) VALUES (%s,%s,%s,%s,%s,%s,%s)", wh)
        self._count("倉庫", len(wh))

        per = {_s(r["SH_NO"], 10): r for r in self.table("P_SHOP_PER")}
        shops = []
        for r in self.table("P_SHOP"):
            no = _s(r.get("SH_NO"), 10)
            if not no:
                continue
            pp = per.get(no, {})
            lvl = int(r.get("SH_PR") or 1) if str(r.get("SH_PR") or "1").isdigit() else 1
            disc = pp.get("SH_PER") or Decimal(100)
            shops.append((no, _s(r.get("SH_NA1"), 30) or no, _s(r.get("SH_NA2"), 60), _s(r.get("SH_NA3"), 20),
                          _s(r.get("SH_NA4"), 20), _s(r.get("SH_TEL1"), 20), _s(r.get("SH_TEL2"), 20),
                          _s(r.get("SH_TEL3"), 20), _s(r.get("SH_MAIL"), 60), _s(r.get("SH_CLASS"), 10),
                          lvl if lvl in (1, 2, 3) else 1, disc if disc else Decimal(100), pp.get("SH_ACC") or 0,
                          _s(r.get("SH_UNO"), 10), _s(r.get("SH_TAX"), 4), _s(r.get("SH_SALE"), 10),
                          r.get("SH_LIM") or 0, _s(r.get("SH_ADD1"), 100), _s(r.get("SH_ADD2"), 100),
                          _s(r.get("SH_ADD3"), 100), _s(r.get("SH_MEMO"), 100)))
        db.many("REPLACE INTO shops (sh_no, short_name, full_name, contact, contact2, tel1, tel2, fax, email, sh_class, "
                "price_level, discount, commission, tax_id, tax_type, salesman, credit_limit, address1, address2, "
                "address3, memo) VALUES (" + ",".join(["%s"] * 21) + ")", shops)
        self._count("店家", len(shops))

        vend = [(_s(r["MA_NO"], 10), _s(r.get("MA_NA1"), 30) or _s(r["MA_NO"], 10), _s(r.get("MA_NA2"), 60),
                 _s(r.get("MA_NA3"), 20), _s(r.get("MA_NA4"), 20), _s(r.get("MA_TEL1"), 20), _s(r.get("MA_TEL2"), 20),
                 _s(r.get("MA_TEL3"), 20), _s(r.get("SH_UNO"), 10), _s(r.get("SH_TAX"), 4), _s(r.get("MA_MADE"), 20),
                 _s(r.get("MA_ADD1"), 100), _s(r.get("MA_ADD2"), 100), _s(r.get("MA_MEMO"), 100))
                for r in self.table("P_MAKER") if _s(r.get("MA_NO"), 10)]
        db.many("REPLACE INTO vendors (ma_no, short_name, full_name, contact, contact2, tel1, tel2, fax, tax_id, tax_type, "
                "made_in, address1, address2, memo) VALUES (" + ",".join(["%s"] * 14) + ")", vend)
        self._count("廠商", len(vend))

        emp = [(_s(r["PER_NO"], 10), _s(r.get("PER_NA"), 20), _s(r.get("PER_EA"), 20), _s(r.get("P_ID"), 14),
                _s(r.get("P_SEX"), 2), _s(r.get("P_TEL1"), 20), _s(r.get("P_TEL2"), 20), _s(r.get("P_TEL3"), 20),
                _s(r.get("P_MAIL"), 60), _s(r.get("SH_NO"), 10), _s(r.get("DEPT_NO"), 20), _s(r.get("P_JOB"), 20),
                _d(r.get("P_BIRT")), _d(r.get("P_DATE1")), _s(r.get("P_BANK"), 30), _s(r.get("BANK_NO"), 20),
                _s(r.get("P_ADD1"), 100), _s(r.get("P_MEMO"), 100)) for r in self.table("P_PERSON") if _s(r.get("PER_NO"), 10)]
        db.many("REPLACE INTO employees (per_no, name, en_name, id_no, sex, tel1, tel2, mobile, email, sh_no, dept, job, "
                "birth, hire_date, bank, bank_acct, address, memo) VALUES (" + ",".join(["%s"] * 18) + ")", emp)
        self._count("員工", len(emp))

        prods = [(_s(r["PROD_NO"], 20), _s(r.get("PROD_CO"), 3), _s(r.get("PROD_SI"), 3), _s(r.get("P_SPEC"), 60),
                  _s(r.get("P_TYPE"), 60), _s(r.get("P_KIND"), 10), _s(r.get("P_SERI"), 10), _s(r.get("P_UNIT"), 10),
                  r.get("P_PRICE1") or 0, r.get("P_PRICE2") or 0, r.get("P_PRICE3") or 0, r.get("P_COST") or 0,
                  _s(r.get("SOUCE_NO"), 20), _s(r.get("P_PATH"), 200)) for r in self.table("PROD") if _s(r.get("PROD_NO"), 20)]
        db.many("REPLACE INTO products (prod_no, color, size, name, spec, brand, series, unit, price1, price2, price3, "
                "cost, source_no, image_path) VALUES (" + ",".join(["%s"] * 14) + ")", prods)
        self._count("產品", len(prods))

    def _users(self):
        rows = self.table("P_PASS")
        n = 0
        for r in rows:
            no = _s(r.get("USER_NO"), 12)
            if not no or self.db.one("SELECT 1 FROM users WHERE user_no=%s", (no,)):
                continue
            self.db.run("INSERT INTO users (user_no, name, dept, pw_hash, is_admin) VALUES (%s,%s,%s,%s,%s)",
                        (no, _s(r.get("USER_NA"), 30) or no, _s(r.get("DEPT_NA"), 30), hash_pw(_s(r.get("PASS_WD"), 20)),
                         1 if _s(r.get("USER_SY"), 1) == "A" else 0))
            n += 1
        self._count("使用者", n)

    def _ensure(self, table, key, name_col, value):
        if value and not self.db.one("SELECT 1 FROM %s WHERE %s=%%s" % (table, key), (value,)):
            self.db.run("INSERT INTO %s (%s, %s) VALUES (%%s, %%s)" % (table, key, name_col), (value, "(舊資料)" + value))

    def _docs(self, code):
        head_t, line_t, no_f, date_f, hmap, price_f, sign = DOC_MAP[code]
        heads = self.table(head_t)
        lines = self.table(line_t)
        by_no = {}
        for ln in lines:
            by_no.setdefault(_s(ln.get(no_f), 20), []).append(ln)
        n = 0
        for h in heads:
            no = _s(h.get(no_f), 20)
            if not no:
                continue
            d = _d(h.get(date_f)) or _d(h.get("USER_DATE")) or dates.today()
            vals = {k: (h.get(v) if k == "discount" else _s(h.get(v), 120 if k == "memo" else 20))
                    for k, v in hmap.items()}
            if "discount" in vals:
                vals["discount"] = vals["discount"] or Decimal(100)
            for f, tbl, key, nm in (("wh_no", "warehouses", "wh_no", "name"), ("wh_no2", "warehouses", "wh_no", "name"),
                                    ("sh_no", "shops", "sh_no", "short_name"), ("sh_no2", "shops", "sh_no", "short_name"),
                                    ("ma_no", "vendors", "ma_no", "short_name")):
                if vals.get(f):
                    vals[f] = vals[f][:4] if tbl == "warehouses" else vals[f][:10]
                    self._ensure(tbl, key, nm, vals[f])
            disc = Decimal(vals.get("discount") or 100)
            items = sorted(by_no.get(no, []), key=lambda x: _s(x.get("SEQ"), 5))
            pay = dict(cash=Decimal(0), card=Decimal(0), voucher=Decimal(0))
            out = []
            for i, ln in enumerate(items, 1):
                pn, co, si = _s(ln.get("PROD_NO"), 20), _s(ln.get("PROD_CO"), 3), _s(ln.get("PROD_SI"), 3)
                qty = int(ln.get("QTY") or 0) * sign
                if not pn or qty == 0:
                    continue
                if not self.db.one("SELECT 1 FROM products WHERE prod_no=%s AND color=%s AND size=%s", (pn, co, si)):
                    self.db.run("INSERT INTO products (prod_no, color, size, name) VALUES (%s,%s,%s,'(舊資料)')", (pn, co, si))
                price = Decimal(ln.get(price_f) or 0)
                cost = Decimal(ln.get("P_COST") or 0)
                amount = (qty * price * disc / 100).quantize(Decimal("0.01"))
                if code == "TA":
                    earn = Decimal(ln.get("EARN") or 0)
                    if earn:
                        amount = earn
                    pay["cash"] += Decimal(ln.get("CASH") or 0)
                    pay["card"] += Decimal(ln.get("CARD") or 0)
                    pay["voucher"] += Decimal(ln.get("CROP") or 0)
                out.append((i, pn, co, si, qty, price, cost, amount))
            doc_id = self.db.run(
                "INSERT INTO docs (doc_type, doc_no, doc_date, wh_no, wh_no2, sh_no, sh_no2, ma_no, per_no, reason, ref_no, "
                "bill_no, discount, total_qty, total_amt, total_cost, pay_cash, pay_card, pay_voucher, memo, created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (code, no, d, vals.get("wh_no", ""), vals.get("wh_no2", ""), vals.get("sh_no", ""),
                 vals.get("sh_no2", ""), vals.get("ma_no", ""), vals.get("per_no", ""), vals.get("reason", ""),
                 vals.get("ref_no", ""), vals.get("bill_no", ""), disc, sum(x[4] for x in out),
                 sum(x[7] for x in out), sum(x[4] * x[6] for x in out), pay["cash"], pay["card"], pay["voucher"],
                 vals.get("memo", ""), _s(h.get("USER_NO"), 12)))
            self.db.many("INSERT INTO doc_lines (doc_id, seq, prod_no, color, size, qty, price, cost, amount) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", [(doc_id,) + x for x in out])
            n += 1
        self._count("單據-" + code, n)
