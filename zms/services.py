"""業務邏輯：基本資料、單據與庫存、查詢報表、應收帳款、使用者權限。"""
import datetime as _dt
import math
from decimal import Decimal, ROUND_HALF_UP

from . import dates
from .db import Database
from .doctypes import BY_CODE, DOC_TYPES
from .security import check_pw, hash_pw


class BizError(Exception):
    """可直接顯示給使用者的錯誤。"""


def D(x) -> Decimal:
    if x in (None, ""):
        return Decimal(0)
    return Decimal(str(x))


def money(x) -> Decimal:
    return D(x).quantize(Decimal("0.01"), ROUND_HALF_UP)


# ---------------------------------------------------------------- 基本資料
# 欄位：(欄位名, 標題, 型別, 寬度)；型別 s 字串 / n 數字 / d 日期 / b 是否 / c:<kind> 代碼 / sel:<k=v,...>
MASTERS = {
    "products": dict(title="產品資料", pk=("prod_no", "color", "size"), cols=[
        ("prod_no", "貨號", "s", 140), ("color", "顏色", "c:color", 70), ("size", "尺寸", "c:size", 70),
        ("name", "品名", "s", 200), ("spec", "規格", "s", 120), ("class", "類別", "c:class", 80),
        ("brand", "品牌", "c:brand", 80), ("series", "系列", "c:series", 80),
        ("year", "年度", "s", 60), ("season", "季別", "c:season", 80), ("style", "款式", "c:style", 90),
        ("fabric", "布料", "c:fabric", 90), ("gender", "性別", "sel:=（不分）,男=男裝,女=女裝,童=童裝,中=中性", 80),
        ("unit", "單位", "c:unit", 60),
        ("price1", "售價一", "n", 80), ("price2", "售價二", "n", 80), ("price3", "售價三", "n", 80),
        ("cost", "成本", "n", 80), ("barcode", "條碼", "s", 130), ("safe_qty", "安全存量", "n", 70),
        ("source_no", "廠商貨號", "s", 100), ("active", "使用中", "b", 60)]),
    "shops": dict(title="店家／客戶", pk=("sh_no",), cols=[
        ("sh_no", "店家代號", "s", 100), ("short_name", "簡稱", "s", 140), ("full_name", "全名", "s", 200),
        ("contact", "負責人", "s", 90), ("contact2", "聯絡人", "s", 90), ("tel1", "電話一", "s", 110),
        ("tel2", "電話二", "s", 110), ("fax", "傳真", "s", 110), ("email", "Email", "s", 160),
        ("sh_class", "類別", "s", 60), ("price_level", "售價等級", "sel:1=售價一,2=售價二,3=售價三", 80),
        ("settle_mode", "結帳方式", "sel:W=批發(出退貨),C=專櫃(銷售扣抽成)", 120),
        ("discount", "出貨折數%", "n", 80), ("commission", "專櫃抽成%", "n", 80),
        ("tax_id", "統一編號", "s", 90), ("salesman", "業務員", "s", 80), ("credit_limit", "信用額度", "n", 90),
        ("address1", "公司地址", "s", 220), ("address2", "發票地址", "s", 220), ("address3", "送貨地址", "s", 220),
        ("memo", "備註", "s", 200), ("active", "使用中", "b", 60)]),
    "vendors": dict(title="廠商資料", pk=("ma_no",), cols=[
        ("ma_no", "廠商代號", "s", 100), ("short_name", "簡稱", "s", 140), ("full_name", "全名", "s", 200),
        ("contact", "負責人", "s", 90), ("contact2", "聯絡人", "s", 90), ("tel1", "電話一", "s", 110),
        ("tel2", "電話二", "s", 110), ("fax", "傳真", "s", 110), ("email", "Email", "s", 160),
        ("tax_id", "統一編號", "s", 90), ("made_in", "產地", "s", 80), ("address1", "公司地址", "s", 220),
        ("address2", "發票地址", "s", 220), ("memo", "備註", "s", 200), ("active", "使用中", "b", 60)]),
    "employees": dict(title="公司人員", pk=("per_no",), cols=[
        ("per_no", "員工代號", "s", 90), ("name", "姓名", "s", 100), ("en_name", "英文名", "s", 100),
        ("sex", "性別", "sel:男=男,女=女", 60), ("id_no", "身分證號", "s", 110), ("tel1", "電話", "s", 110),
        ("mobile", "手機", "s", 110), ("email", "Email", "s", 160), ("sh_no", "所屬店家", "s", 90),
        ("dept", "部門", "s", 90), ("job", "職稱", "s", 90), ("birth", "生日", "d", 90),
        ("hire_date", "到職日", "d", 90), ("leave_date", "離職日", "d", 90), ("bank", "銀行", "s", 120),
        ("bank_acct", "帳號", "s", 120), ("address", "地址", "s", 220), ("memo", "備註", "s", 200),
        ("active", "在職", "b", 60)]),
    "warehouses": dict(title="倉庫資料", pk=("wh_no",), cols=[
        ("wh_no", "倉庫代號", "s", 80), ("name", "倉庫名稱", "s", 140), ("contact", "負責人", "s", 90),
        ("tel", "電話", "s", 110), ("area", "區域", "s", 90), ("address", "地址", "s", 240),
        ("memo", "備註", "s", 200), ("active", "使用中", "b", 60)]),
}

CODE_KINDS = {"color": "顏色", "size": "尺寸", "class": "類別", "brand": "品牌", "series": "系列",
              "season": "季別", "style": "款式", "fabric": "布料",
              "unit": "單位", "reason": "異動原因", "subject": "費用科目"}
# 常見服飾尺碼順序（公司尺寸組沒涵蓋時使用；數字尺碼會依數字大小排）
STD_SIZES = ["XXS", "XS", "SS", "S", "M", "L", "XL", "LL", "2L", "XXL", "2XL", "3L", "XXXL", "3XL", "4L", "4XL",
             "5L", "5XL", "6XL", "F", "FREE"]
GENDERS = {"": "", "男": "男裝", "女": "女裝", "童": "童裝", "中": "中性"}

REFS = {  # 刪除前檢查有沒有被單據使用
    "products": ("SELECT 1 FROM doc_lines WHERE prod_no=%s AND color=%s AND size=%s LIMIT 1",),
    "shops": ("SELECT 1 FROM docs WHERE sh_no=%s OR sh_no2=%s LIMIT 1",),
    "vendors": ("SELECT 1 FROM docs WHERE ma_no=%s LIMIT 1",),
    "warehouses": ("SELECT 1 FROM docs WHERE wh_no=%s OR wh_no2=%s LIMIT 1",),
    "employees": ("SELECT 1 FROM docs WHERE per_no=%s LIMIT 1",),
}

# 功能清單（權限）：代號、名稱、分組
FUNCS = [
    ("A1", "產品資料", "基本資料"), ("A2", "店家資料", "基本資料"), ("A3", "廠商資料", "基本資料"),
    ("A4", "公司人員", "基本資料"), ("A5", "倉庫資料", "基本資料"), ("A6", "代碼資料", "基本資料"),
    ("A7", "吊牌標籤", "基本資料"), ("A8", "特價品", "基本資料"),
] + [("D_" + d.code, d.name, d.group + "單據") for d in DOC_TYPES] + [
    ("Q1", "庫存查詢", "查詢"), ("Q2", "進銷存查詢", "查詢"), ("Q3", "銷售分析", "查詢"),
    ("Q4", "訂單／採購追蹤", "查詢"), ("Q5", "產品異動明細", "查詢"),
    ("R1", "補貨建議", "補貨調度"), ("R2", "轉貨建議", "補貨調度"), ("R3", "追加採購建議", "補貨調度"),
    ("G1", "應收結帳", "帳款"), ("G2", "收款沖帳", "帳款"), ("G3", "店家費用", "帳款"), ("G4", "應收查詢", "帳款"),
    ("M1", "使用者與權限", "維護"), ("M2", "公司設定", "維護"), ("M3", "庫存校帳", "維護"),
    ("M4", "備份回存", "維護"), ("M5", "舊系統資料匯入", "維護"),
]


class Service:
    def __init__(self, db: Database):
        self.db = db
        self.user = None  # 目前登入者 dict

    # ------------------------------------------------ 使用者
    @property
    def uid(self):
        return self.user["user_no"] if self.user else ""

    def has_users(self) -> bool:
        return bool(self.db.scalar("SELECT COUNT(*) FROM users"))

    def create_user(self, user_no, name, pw, is_admin=False, dept=""):
        user_no = (user_no or "").strip()
        if not user_no:
            raise BizError("請輸入使用者代號")
        if self.db.one("SELECT 1 FROM users WHERE user_no=%s", (user_no,)):
            raise BizError("使用者代號已存在")
        self.db.run("INSERT INTO users (user_no, name, dept, pw_hash, is_admin) VALUES (%s,%s,%s,%s,%s)",
                    (user_no, name or user_no, dept, hash_pw(pw or ""), 1 if is_admin else 0))

    def update_user(self, user_no, name, dept, is_admin, active, pw=None):
        with self.db.tx():
            self.db.run("UPDATE users SET name=%s, dept=%s, is_admin=%s, active=%s WHERE user_no=%s",
                        (name, dept, 1 if is_admin else 0, 1 if active else 0, user_no))
            if pw:
                self.db.run("UPDATE users SET pw_hash=%s WHERE user_no=%s", (hash_pw(pw), user_no))
            if not self.db.scalar("SELECT COUNT(*) FROM users WHERE is_admin=1 AND active=1"):
                raise BizError("至少要保留一位啟用中的系統管理員")

    def delete_user(self, user_no):
        if user_no == self.uid:
            raise BizError("不能刪除自己")
        with self.db.tx():
            self.db.run("DELETE FROM users WHERE user_no=%s", (user_no,))
            self.db.run("DELETE FROM user_perms WHERE user_no=%s", (user_no,))
            if not self.db.scalar("SELECT COUNT(*) FROM users WHERE is_admin=1 AND active=1"):
                raise BizError("至少要保留一位啟用中的系統管理員")

    def list_users(self):
        return self.db.all("SELECT user_no, name, dept, is_admin, active FROM users ORDER BY user_no")

    def login(self, user_no, pw):
        u = self.db.one("SELECT * FROM users WHERE user_no=%s", ((user_no or "").strip(),))
        if not u or not u["active"] or not check_pw(pw or "", u["pw_hash"]):
            raise BizError("代號或密碼錯誤")
        u["perms"] = {r["func_id"] for r in self.db.all("SELECT func_id FROM user_perms WHERE user_no=%s",
                                                         (u["user_no"],))}
        self.user = u
        self.log("login", u["user_no"])
        return u

    def change_password(self, old, new):
        if not check_pw(old or "", self.db.scalar("SELECT pw_hash FROM users WHERE user_no=%s", (self.uid,))):
            raise BizError("舊密碼不對")
        if len(new or "") < 4:
            raise BizError("新密碼至少 4 個字")
        self.db.run("UPDATE users SET pw_hash=%s WHERE user_no=%s", (hash_pw(new), self.uid))

    def can(self, func_id) -> bool:
        if not self.user:
            return False
        return bool(self.user["is_admin"]) or func_id in self.user["perms"]

    def get_perms(self, user_no):
        return {r["func_id"] for r in self.db.all("SELECT func_id FROM user_perms WHERE user_no=%s", (user_no,))}

    def set_perms(self, user_no, funcs):
        with self.db.tx():
            self.db.run("DELETE FROM user_perms WHERE user_no=%s", (user_no,))
            self.db.many("INSERT INTO user_perms (user_no, func_id) VALUES (%s,%s)", [(user_no, f) for f in funcs])

    def log(self, action, target="", detail=""):
        self.db.run("INSERT INTO audit_log (user_no, action, target, detail) VALUES (%s,%s,%s,%s)",
                    (self.uid, action, str(target)[:60], str(detail)[:255]))

    # ------------------------------------------------ 公司設定
    def company(self):
        return self.db.one("SELECT * FROM company WHERE id=1")

    def save_company(self, row):
        cols = ["name", "tax_id", "tel", "address", "prod_len", "color_len", "size_len",
                "size_group_a", "size_group_b", "size_group_c", "size_group_d"]
        self.db.run("UPDATE company SET " + ",".join("%s=%%s" % c for c in cols) + " WHERE id=1",
                    [row.get(c, "") for c in cols])

    def size_groups(self):
        """尺寸組 A～D（舊系統 SYS_A..D，以 * 分隔）→ {'A': ['S','M',...]}"""
        c = self.company() or {}
        out = {}
        for g in "abcd":
            raw = c.get("size_group_" + g) or ""
            sizes = [s.strip() for s in raw.split("*") if s.strip()]
            if sizes:
                out[g.upper()] = sizes
        return out

    def sort_sizes(self, sizes):
        """尺寸排序：依公司尺寸組 A～D 的順序（S M L XL…），其次依尺寸代碼表，最後數字／字母。"""
        sizes = list(dict.fromkeys(sizes))
        best, best_hits = [], 0
        for grp in list(self.size_groups().values()) + [STD_SIZES]:
            hits = sum(1 for s in grp if s.upper() in {x.upper() for x in sizes})
            if hits > best_hits:
                best, best_hits = grp, hits
        if best is STD_SIZES:
            upper = {s.upper(): s for s in sizes}
            best = [upper[s.upper()] for s in STD_SIZES if s.upper() in upper]
        code_order = [r["code"] for r in self.codes("size")]

        def key(s):
            if s in best:
                return (0, best.index(s), "")
            if s in code_order:
                return (1, code_order.index(s), "")
            return (2, int(s) if s.isdigit() else 10 ** 6, s)
        return sorted(sizes, key=key)

    def sort_colors(self, colors):
        order = [r["code"] for r in self.codes("color")]
        return sorted(dict.fromkeys(colors), key=lambda c: (order.index(c) if c in order else 10 ** 6, c))

    # ------------------------------------------------ 服飾：整款建檔／尺寸矩陣
    def variants(self, prod_no):
        return self.db.all("SELECT * FROM products WHERE prod_no=%s ORDER BY color, size", (prod_no,))

    def create_style(self, base, colors, sizes):
        """整款建檔：同一貨號依「顏色 × 尺寸」一次產生全部產品；已存在的組合略過。回傳 (新增, 略過)。"""
        prod_no = (base.get("prod_no") or "").strip()
        if not prod_no:
            raise BizError("請輸入貨號")
        colors = [c.strip() for c in colors if c and c.strip()] or [""]
        sizes = [s.strip() for s in sizes if s and s.strip()] or [""]
        if len(colors) * len(sizes) > 400:
            raise BizError("一次最多 400 個顏色尺寸組合")
        made = skipped = 0
        with self.db.tx():
            for c in colors:
                for s in sizes:
                    row = dict(base, prod_no=prod_no, color=c, size=s, active=1)
                    if self.master_get("products", [prod_no, c, s]):
                        skipped += 1
                        continue
                    self.master_save("products", row, True)
                    made += 1
        return made, skipped

    def matrix_for(self, prod_no, loc_type=None, loc_no=None):
        """尺寸矩陣資料：顏色列、尺寸欄、該位置目前庫存。"""
        vs = self.variants(prod_no)
        if not vs:
            return None
        stock = {}
        if loc_type and loc_no:
            stock = {(r["color"], r["size"]): int(r["qty"]) for r in self.db.all(
                "SELECT color, size, qty FROM stock WHERE loc_type=%s AND loc_no=%s AND prod_no=%s",
                (loc_type, loc_no, prod_no))}
        return dict(prod_no=prod_no, name=vs[0]["name"], variants={(v["color"], v["size"]): v for v in vs},
                    colors=self.sort_colors([v["color"] for v in vs]), sizes=self.sort_sizes([v["size"] for v in vs]),
                    stock=stock, color_names=self.code_map("color"))

    def stock_matrix(self, loc_type="W", loc_no="", q="", brand="", season="", year="", nonzero=True, limit=300):
        """庫存尺寸分布：每個貨號一張「(位置, 顏色) × 尺寸」表。"""
        where, args = ["s.loc_type=%s"], [loc_type]
        if loc_no:
            where.append("s.loc_no=%s"); args.append(loc_no)
        if q:
            where.append("(s.prod_no LIKE %s OR p.name LIKE %s)"); args += [q + "%", "%" + q + "%"]
        for f, v in (("brand", brand), ("season", season), ("year", year)):
            if v:
                where.append("p.%s=%%s" % f); args.append(v)
        rows = self.db.all(
            "SELECT s.loc_no, s.prod_no, s.color, s.size, s.qty, p.name FROM stock s LEFT JOIN products p ON "
            "p.prod_no=s.prod_no AND p.color=s.color AND p.size=s.size WHERE " + " AND ".join(where) +
            " ORDER BY s.prod_no, s.loc_no, s.color", args)
        names = {r["k"]: r["n"] for r in self.db.all(
            "SELECT wh_no k, name n FROM warehouses" if loc_type == "W" else "SELECT sh_no k, short_name n FROM shops")}
        cnames = self.code_map("color")
        out, by = [], {}
        for r in rows:
            p = by.get(r["prod_no"])
            if p is None:
                p = by[r["prod_no"]] = dict(prod_no=r["prod_no"], name=r["name"] or "", cells={}, sizes=set())
                out.append(p)
            p["sizes"].add(r["size"])
            key = (r["loc_no"], r["color"])
            p["cells"].setdefault(key, {})[r["size"]] = p["cells"].get(key, {}).get(r["size"], 0) + int(r["qty"])
        corder = {c: i for i, c in enumerate(r["code"] for r in self.codes("color"))}
        result = []
        for p in out:
            sizes = self.sort_sizes(list(p["sizes"]))
            lines = []
            for (loc, color), cells in sorted(p["cells"].items(),
                                              key=lambda kv: (kv[0][0], corder.get(kv[0][1], 10 ** 6), kv[0][1])):
                tot = sum(cells.values())
                if nonzero and not any(cells.values()):
                    continue
                lines.append(dict(loc=loc, loc_name=names.get(loc, ""), color=color, color_name=cnames.get(color, ""),
                                  cells=cells, total=tot))
            if lines:
                col_tot = {s: sum(l["cells"].get(s, 0) for l in lines) for s in sizes}
                result.append(dict(prod_no=p["prod_no"], name=p["name"], sizes=sizes, lines=lines,
                                   col_tot=col_tot, total=sum(col_tot.values())))
            if len(result) >= limit:
                break
        return result

    # ------------------------------------------------ 吊牌條碼標籤
    @staticmethod
    def barcode_text(p):
        """吊牌上的條碼內容：產品資料有填條碼就用它，否則用「貨號-顏色-尺寸」（開單掃描可直接帶出）。"""
        bc = (p.get("barcode") or "").strip()
        return bc or "-".join(x for x in (p["prod_no"], p.get("color") or "", p.get("size") or ""))

    def label_items(self, picks):
        """picks=[(prod_no, color, size, 張數)] → 標籤資料（含顏色、布料名稱、條碼內容）。"""
        cn, fn = self.code_map("color"), self.code_map("fabric")
        out = []
        for pn, c, s, n in picks:
            n = int(n or 0)
            if n <= 0:
                continue
            p = self.master_get("products", [pn, c, s])
            if not p:
                continue
            sp = self.special_for(p, "")  # 全部店家適用、今天有效的特價
            p = dict(p, copies=n, color_name=cn.get(p["color"], ""), fabric_name=fn.get(p.get("fabric") or "", ""),
                     code=self.barcode_text(p),
                     special_price=sp["special_price"] if sp else None, special_discount=sp["discount"] if sp else None)
            out.append(p)
        return out

    BOX_TO = {"GR": ("sh_no", "shops"), "MO": ("sh_no2", "shops"), "DR": ("wh_no", "warehouses"),
              "CH": ("wh_no2", "warehouses"), "PO": ("ma_no", "vendors")}

    def box_info(self, doc_id):
        """裝箱標籤資料（舊系統 C1_D）：寄件方、收件方、地址電話、單號、總件數。"""
        h, lines = self.get_doc(doc_id)
        if h["doc_type"] not in self.BOX_TO:
            raise BizError("這種單據不需要裝箱標籤")
        f, tbl = self.BOX_TO[h["doc_type"]]
        r = self.master_get(tbl, [h[f]]) or {}
        if tbl == "shops":
            to = dict(no=h[f], name=r.get("full_name") or r.get("short_name") or h[f], contact=r.get("contact2") or r.get("contact"),
                      tel=r.get("tel1") or r.get("tel2"), address=r.get("address3") or r.get("address1"))
        elif tbl == "vendors":
            to = dict(no=h[f], name=r.get("full_name") or r.get("short_name") or h[f], contact=r.get("contact2") or r.get("contact"),
                      tel=r.get("tel1"), address=r.get("address1"))
        else:
            to = dict(no=h[f], name="%s（倉庫）" % (r.get("name") or h[f]), contact=r.get("contact"), tel=r.get("tel"),
                      address=r.get("address"))
        comp = self.company() or {}
        return dict(doc_no=h["doc_no"], doc_type=BY_CODE[h["doc_type"]].name, doc_date=h["doc_date"],
                    total_qty=h["total_qty"], memo=h["memo"] or "", to=to,
                    sender=dict(name=comp.get("name") or "", tel=comp.get("tel") or "", address=comp.get("address") or ""))

    def label_items_from_doc(self, doc_id):
        _, lines = self.get_doc(doc_id)
        return self.label_items([(l["prod_no"], l["color"], l["size"], abs(int(l["qty"]))) for l in lines])

    # ------------------------------------------------ 補貨調度（舊系統 61～66）
    def _sku_filter(self, q="", brand="", season="", alias="p"):
        where, args = [], []
        if q:
            where.append("(%s.prod_no LIKE %%s OR %s.name LIKE %%s)" % (alias, alias)); args += [q + "%", "%" + q + "%"]
        if brand:
            where.append("%s.brand=%%s" % alias); args.append(brand)
        if season:
            where.append("%s.season=%%s" % alias); args.append(season)
        return where, args

    def _shop_sales(self, days, end=None, shops=None):
        """最近 days 天各店各規格銷量（店家銷貨單）。"""
        end = dates.parse(end or dates.today())
        start = end - _dt.timedelta(days=int(days) - 1)
        sql = ("SELECT d.sh_no, l.prod_no, l.color, l.size, SUM(l.qty) q FROM docs d JOIN doc_lines l ON "
               "l.doc_id=d.id WHERE d.doc_type='TA' AND d.doc_date BETWEEN %s AND %s")
        args = [start, end]
        if shops:
            sql += " AND d.sh_no IN (%s)" % ",".join(["%s"] * len(shops)); args += list(shops)
        sql += " GROUP BY d.sh_no, l.prod_no, l.color, l.size"
        return {(r["sh_no"], r["prod_no"], r["color"], r["size"]): int(r["q"]) for r in self.db.all(sql, args)}

    def _stock_map(self, loc_type, loc_no=None):
        sql, args = "SELECT loc_no, prod_no, color, size, qty FROM stock WHERE loc_type=%s", [loc_type]
        if loc_no:
            sql += " AND loc_no=%s"; args.append(loc_no)
        return {(r["loc_no"], r["prod_no"], r["color"], r["size"]): int(r["qty"]) for r in self.db.all(sql, args)}

    def _products_info(self, keys, q="", brand="", season=""):
        """keys=[(prod_no,color,size)] → 符合篩選條件的產品資料 dict。"""
        if not keys:
            return {}
        where, args = self._sku_filter(q, brand, season)
        rows = self.db.all("SELECT p.prod_no, p.color, p.size, p.name, p.safe_qty FROM products p" +
                           (" WHERE " + " AND ".join(where) if where else ""), args)
        ks = set(keys)
        return {(r["prod_no"], r["color"], r["size"]): r for r in rows if (r["prod_no"], r["color"], r["size"]) in ks}

    def replenish_suggest(self, method, wh_no, shops=None, days=14, cover=14, level=2, q="", brand="", season="",
                          end=None):
        """補貨建議（總倉 → 店家）。
        method：sales 依銷售（補到 cover 天份）／level 依庫存量（每規格補到 level 件）／safe 依安全存量（產品設定）。
        建議量＝目標量－店庫存；再依倉庫可用量分配，銷量高、缺口大的店優先。"""
        if not wh_no:
            raise BizError("請選擇出貨倉庫")
        days, cover, level = max(int(days or 14), 1), max(int(cover or 14), 1), max(int(level or 0), 0)
        shops = shops or [r["sh_no"] for r in self.db.all("SELECT sh_no FROM shops WHERE active=1 ORDER BY sh_no")]
        sales = self._shop_sales(days, end, shops)
        sstock = self._stock_map("S")
        wstock = {k[1:]: v for k, v in self._stock_map("W", wh_no).items()}
        cand = set()
        if method == "sales":
            cand = {k for k, v in sales.items() if v > 0}
        elif method == "level":
            cand = {(sh,) + sku for sh in shops for sku, v in wstock.items() if v > 0}
        elif method == "safe":
            safe = self.db.all("SELECT prod_no, color, size FROM products WHERE safe_qty>0 AND active=1")
            cand = {(sh, r["prod_no"], r["color"], r["size"]) for sh in shops for r in safe}
        else:
            raise BizError("未知的補貨方式")
        info = self._products_info([k[1:] for k in cand], q, brand, season)
        need = []
        for k in cand:
            sku = k[1:]
            p = info.get(sku)
            if not p:
                continue
            sold = sales.get(k, 0)
            stock = sstock.get(k, 0)
            if method == "sales":
                target = math.ceil(sold / days * cover)
            elif method == "level":
                target = level
            else:
                target = int(p["safe_qty"] or 0)
            suggest = target - max(stock, 0)
            if suggest > 0:
                need.append(dict(sh_no=k[0], prod_no=sku[0], color=sku[1], size=sku[2], name=p["name"], sold=sold,
                                 stock=stock, target=target, suggest=suggest))
        # 依倉庫可用量分配：同一規格，銷量高、缺口大的先配
        need.sort(key=lambda r: (r["prod_no"], r["color"], r["size"], -r["sold"], -r["suggest"], r["sh_no"]))
        left = {}
        for r in need:
            sku = (r["prod_no"], r["color"], r["size"])
            if sku not in left:
                left[sku] = max(wstock.get(sku, 0), 0)
            r["wh_avail"] = left[sku]
            r["alloc"] = min(r["suggest"], left[sku])
            left[sku] -= r["alloc"]
        names = {r["sh_no"]: r["short_name"] for r in self.db.all("SELECT sh_no, short_name FROM shops")}
        for r in need:
            r["sh_name"] = names.get(r["sh_no"], "")
        need.sort(key=lambda r: (r["sh_no"], r["prod_no"], r["color"], self.sort_sizes([r["size"]])[0]))
        return need

    def make_ship_docs(self, wh_no, rows, memo="補貨建議"):
        """把補貨建議（alloc>0）依店家產生出貨單，回傳單號清單。"""
        by = {}
        for r in rows:
            q = int(r.get("alloc") or 0)
            if q > 0:
                by.setdefault(r["sh_no"], []).append(dict(prod_no=r["prod_no"], color=r["color"], size=r["size"], qty=q))
        if not by:
            raise BizError("沒有可配貨的數量（倉庫沒貨或都已足量）")
        out = []
        for sh, lines in by.items():
            did = self.save_doc("GR", dict(wh_no=wh_no, sh_no=sh, discount=self.shop_discount(sh), memo=memo), lines)
            out.append(self.db.scalar("SELECT doc_no FROM docs WHERE id=%s", (did,)))
        return out

    def transfer_suggest(self, shops=None, days=30, cover=14, keep=1, q="", brand="", season="", end=None):
        """轉貨建議（店家 ↔ 店家）：賣得慢、庫存多的店調給賣得快、缺貨的店。
        目標量＝近 days 天日均銷量 × cover 天；多餘量＝庫存－max(目標量, 保留量 keep)；缺口＝目標量－庫存。"""
        days, cover, keep = max(int(days or 30), 1), max(int(cover or 14), 1), max(int(keep or 0), 0)
        shops = shops or [r["sh_no"] for r in self.db.all("SELECT sh_no FROM shops WHERE active=1 ORDER BY sh_no")]
        sales = self._shop_sales(days, end, shops)
        sstock = {k: v for k, v in self._stock_map("S").items() if k[0] in shops}
        skus = {k[1:] for k in list(sales) + list(sstock)}
        info = self._products_info(list(skus), q, brand, season)
        names = {r["sh_no"]: r["short_name"] for r in self.db.all("SELECT sh_no, short_name FROM shops")}
        out = []
        for sku in sorted(info):
            give, take = [], []
            for sh in shops:
                st, sold = sstock.get((sh,) + sku, 0), sales.get((sh,) + sku, 0)
                target = math.ceil(sold / days * cover)
                extra = st - max(target, keep)
                short = target - max(st, 0)
                if extra > 0:
                    give.append([sh, extra, st, sold])
                elif short > 0:
                    take.append([sh, short, st, sold])
            give.sort(key=lambda x: (-x[1], x[0]))
            take.sort(key=lambda x: (-x[3], -x[1], x[0]))
            for t in take:
                for g in give:
                    if t[1] <= 0:
                        break
                    if g[1] <= 0:
                        continue
                    q2 = min(g[1], t[1])
                    g[1] -= q2
                    t[1] -= q2
                    out.append(dict(from_sh=g[0], from_name=names.get(g[0], ""), to_sh=t[0], to_name=names.get(t[0], ""),
                                    prod_no=sku[0], color=sku[1], size=sku[2], name=info[sku]["name"], qty=q2,
                                    from_stock=g[2], from_sold=g[3], to_stock=t[2], to_sold=t[3]))
        return out

    def make_move_docs(self, rows, memo="轉貨建議"):
        by = {}
        for r in rows:
            q = int(r.get("qty") or 0)
            if q > 0:
                by.setdefault((r["from_sh"], r["to_sh"]), []).append(
                    dict(prod_no=r["prod_no"], color=r["color"], size=r["size"], qty=q))
        if not by:
            raise BizError("沒有要調撥的數量")
        out = []
        for (a, b), lines in by.items():
            did = self.save_doc("MO", dict(sh_no=a, sh_no2=b, memo=memo), lines)
            out.append(self.db.scalar("SELECT doc_no FROM docs WHERE id=%s", (did,)))
        return out

    def recut_suggest(self, days=30, cover=30, q="", brand="", season="", end=None):
        """追加採購／追裁建議（全公司）：目標量＝近 days 天日均銷量 × cover 天；
        建議量＝目標量－（倉庫＋店家庫存）－已採購未進貨。"""
        days, cover = max(int(days or 30), 1), max(int(cover or 30), 1)
        sales = {}
        for k, v in self._shop_sales(days, end).items():
            sales[k[1:]] = sales.get(k[1:], 0) + v
        total = {}
        for r in self.db.all("SELECT prod_no, color, size, SUM(qty) q FROM stock GROUP BY prod_no, color, size"):
            total[(r["prod_no"], r["color"], r["size"])] = int(r["q"])
        pending = {}
        for r in self.tracking("GE"):
            left = int(r["ordered"]) - int(r["done"])
            if left > 0:
                k = (r["prod_no"], r["color"], r["size"])
                pending[k] = pending.get(k, 0) + left
        info = self._products_info([k for k, v in sales.items() if v > 0], q, brand, season)
        out = []
        for sku, p in info.items():
            sold = sales.get(sku, 0)
            target = math.ceil(sold / days * cover)
            stock, pend = total.get(sku, 0), pending.get(sku, 0)
            sug = target - stock - pend
            if sug > 0:
                rate = sold / days
                out.append(dict(prod_no=sku[0], color=sku[1], size=sku[2], name=p["name"], sold=sold, stock=stock,
                                pending=pend, target=target, suggest=sug,
                                days_left=round(max(stock, 0) / rate, 1) if rate else None))
        out.sort(key=lambda r: (r["prod_no"], r["color"], self.sort_sizes([r["size"]])[0]))
        return out

    def make_purchase_doc(self, wh_no, ma_no, rows, memo="追加採購建議"):
        lines = [dict(prod_no=r["prod_no"], color=r["color"], size=r["size"], qty=int(r.get("suggest") or 0))
                 for r in rows if int(r.get("suggest") or 0) > 0]
        if not lines:
            raise BizError("沒有建議採購的數量")
        did = self.save_doc("GE", dict(wh_no=wh_no, ma_no=ma_no, memo=memo), lines)
        return self.db.scalar("SELECT doc_no FROM docs WHERE id=%s", (did,))

    # ------------------------------------------------ 代碼
    def codes(self, kind):
        return self.db.all("SELECT code, name, memo FROM codes WHERE kind=%s ORDER BY code", (kind,))

    def code_map(self, kind):
        return {r["code"]: r["name"] for r in self.codes(kind)}

    def save_code(self, kind, code, name, memo=""):
        code = (code or "").strip()
        if not code:
            raise BizError("請輸入代碼")
        self.db.run("REPLACE INTO codes (kind, code, name, memo) VALUES (%s,%s,%s,%s)", (kind, code, name, memo))

    def delete_code(self, kind, code):
        self.db.run("DELETE FROM codes WHERE kind=%s AND code=%s", (kind, code))

    # ------------------------------------------------ 基本資料 CRUD
    def master_list(self, table, q="", limit=500, active_only=False):
        m = MASTERS[table]
        where, args = [], []
        if q:
            like = "%" + q + "%"
            cs = [c[0] for c in m["cols"] if c[2] == "s"][:4]
            where.append("(" + " OR ".join("%s LIKE %%s" % c for c in cs) + ")")
            args += [like] * len(cs)
        if active_only:
            where.append("active=1")
        sql = "SELECT * FROM %s" % table + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY " + ",".join(m["pk"]) + " LIMIT %d" % limit
        return self.db.all(sql, args)

    def master_get(self, table, key):
        m = MASTERS[table]
        return self.db.one("SELECT * FROM %s WHERE " % table + " AND ".join("%s=%%s" % k for k in m["pk"]), key)

    def master_save(self, table, row, is_new):
        m = MASTERS[table]
        cols = [c[0] for c in m["cols"]]
        clean = {}
        for name, title, typ, _ in m["cols"]:
            v = row.get(name)
            if typ == "n":
                try:
                    v = D(v or 0)
                except Exception:
                    raise BizError("%s 必須是數字" % title)
            elif typ == "d":
                v = dates.parse(v) if v not in (None, "") else None
            elif typ == "b":
                v = 1 if v in (True, 1, "1", "Y", "y") else 0
            else:
                v = ("" if v is None else str(v)).strip()
            clean[name] = v
        for k in m["pk"]:
            if k == "prod_no" and not clean[k]:
                raise BizError("請輸入貨號")
            if k not in ("color", "size") and not clean[k]:
                raise BizError("請輸入%s" % next(c[1] for c in m["cols"] if c[0] == k))
        key = [clean[k] for k in m["pk"]]
        exists = self.master_get(table, key)
        if is_new and exists:
            raise BizError("代號已存在")
        if is_new:
            self.db.run("INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(cols), ",".join(["%s"] * len(cols))),
                        [clean[c] for c in cols])
        else:
            if not exists:
                raise BizError("資料不存在（可能已被刪除）")
            sets = [c for c in cols if c not in m["pk"]]
            self.db.run("UPDATE %s SET %s WHERE %s" % (table, ",".join("%s=%%s" % c for c in sets),
                                                       " AND ".join("%s=%%s" % k for k in m["pk"])),
                        [clean[c] for c in sets] + key)
        self.log("save_" + table, "/".join(key))
        return clean

    def master_delete(self, table, key):
        chk = REFS.get(table)
        if chk:
            sql = chk[0]
            args = list(key) * (sql.count("%s") // len(key))
            if self.db.one(sql, args):
                raise BizError("已有單據使用，不能刪除（可改成「不使用」）")
        m = MASTERS[table]
        self.db.run("DELETE FROM %s WHERE " % table + " AND ".join("%s=%%s" % k for k in m["pk"]), key)
        self.log("del_" + table, "/".join(key))

    def options(self, table):
        """下拉選單：[(代號, 顯示)]"""
        if table == "warehouses":
            rows = self.db.all("SELECT wh_no k, name n FROM warehouses WHERE active=1 ORDER BY wh_no")
        elif table == "shops":
            rows = self.db.all("SELECT sh_no k, short_name n FROM shops WHERE active=1 ORDER BY sh_no")
        elif table == "vendors":
            rows = self.db.all("SELECT ma_no k, short_name n FROM vendors WHERE active=1 ORDER BY ma_no")
        elif table == "employees":
            rows = self.db.all("SELECT per_no k, name n FROM employees WHERE active=1 ORDER BY per_no")
        elif table == "reason":
            rows = self.db.all("SELECT code k, name n FROM codes WHERE kind='reason' ORDER BY code")
        else:
            rows = []
        return [(r["k"], "%s %s" % (r["k"], r["n"] or "")) for r in rows]

    def find_products(self, q, limit=50):
        like = q + "%"
        return self.db.all(
            "SELECT prod_no, color, size, name, price1, price2, price3, cost FROM products "
            "WHERE active=1 AND (prod_no LIKE %s OR barcode=%s OR name LIKE %s) "
            "ORDER BY prod_no, color, size LIMIT %s", (like, q, "%" + q + "%", limit))

    def product_by_code(self, code):
        """掃條碼或輸入「貨號-顏色-尺寸」。"""
        code = (code or "").strip()
        if not code:
            return None
        p = self.db.one("SELECT * FROM products WHERE barcode=%s LIMIT 1", (code,))
        if p:
            return p
        parts = code.replace(" ", "-").rsplit("-", 2)   # 吊牌條碼格式：貨號-顏色-尺寸（貨號本身可含 -）
        if len(parts) == 3:
            p = self.db.one("SELECT * FROM products WHERE prod_no=%s AND color=%s AND size=%s",
                            (parts[0], parts[1], parts[2]))
            if p:
                return p
        rows = self.db.all("SELECT * FROM products WHERE prod_no=%s ORDER BY color, size LIMIT 2", (code,))
        return rows[0] if len(rows) == 1 else None

    # ------------------------------------------------ 單據
    def next_doc_no(self, code, d=None):
        d = dates.parse(d or dates.today())
        prefix = "%s%s-" % (code, dates.roc_compact(d))
        last = self.db.scalar("SELECT MAX(doc_no) FROM docs WHERE doc_type=%s AND doc_no LIKE %s",
                              (code, prefix + "%"))
        n = int(last.split("-")[-1]) + 1 if last and last.split("-")[-1].isdigit() else 1
        return "%s%03d" % (prefix, n)

    def default_price(self, code, prod, header):
        return self.price_info(code, prod, header)[0]

    def price_info(self, code, prod, header):
        """明細預設單價 → (單價, 特價說明或 '')。售價類單據會套用有效期間內的特價。"""
        dt = BY_CODE[code]
        if dt.price == "cost":
            return D(prod.get("cost")), ""
        lvl = 1
        sh = header.get("sh_no") or ""
        if sh:
            lvl = self.db.scalar("SELECT price_level FROM shops WHERE sh_no=%s", (sh,)) or 1
        base = D(prod.get("price%d" % lvl) or prod.get("price1"))
        try:
            on = dates.parse(header.get("doc_date") or dates.today())
        except ValueError:
            on = dates.today()
        sp = self.special_for(prod, sh, on)
        if sp:
            price = money(sp["special_price"]) if sp["special_price"] is not None else money(base * D(sp["discount"]) / 100)
            if price < base or base == 0:
                return price, "特價" + ("（%s）" % sp["memo"] if sp["memo"] else "")
        return base, ""

    # ------------------------------------------------ 特價品
    def special_for(self, prod, sh_no="", on=None):
        """找出某商品在某店、某日的有效特價：指定店家優先於全部店家，指定顏色尺寸優先於整個貨號。"""
        on = dates.parse(on or dates.today())
        rows = self.db.all(
            "SELECT * FROM specials WHERE active=1 AND prod_no=%s AND %s BETWEEN start_date AND end_date "
            "AND (sh_no='' OR sh_no=%s) AND (color='' OR color=%s) AND (size='' OR size=%s)",
            (prod["prod_no"], on, sh_no or "", prod.get("color") or "", prod.get("size") or ""))
        if not rows:
            return None
        rows.sort(key=lambda r: (r["sh_no"] == "", r["color"] == "" and r["size"] == "", -r["id"]))
        return rows[0]

    def list_specials(self, kind="", q="", current_only=False):
        where, args = [], []
        if kind == "prod":
            where.append("s.sh_no=''")
        elif kind == "shop":
            where.append("s.sh_no<>''")
        if q:
            where.append("(s.prod_no LIKE %s OR s.sh_no LIKE %s OR s.memo LIKE %s)"); args += [q + "%", q + "%", "%" + q + "%"]
        if current_only:
            where.append("s.active=1 AND CURDATE() BETWEEN s.start_date AND s.end_date")
        return self.db.all(
            "SELECT s.*, IFNULL(h.short_name,'（全部店家）') sh_name, "
            "(SELECT p.name FROM products p WHERE p.prod_no=s.prod_no LIMIT 1) prod_name FROM specials s "
            "LEFT JOIN shops h ON h.sh_no=s.sh_no" + (" WHERE " + " AND ".join(where) if where else "") +
            " ORDER BY s.end_date DESC, s.prod_no LIMIT 1000", args)

    def save_special(self, row, sid=None):
        pn = (row.get("prod_no") or "").strip()
        if not pn or not self.db.one("SELECT 1 FROM products WHERE prod_no=%s", (pn,)):
            raise BizError("貨號不存在：%s" % pn)
        sh = (row.get("sh_no") or "").strip()
        if sh and not self.db.one("SELECT 1 FROM shops WHERE sh_no=%s", (sh,)):
            raise BizError("店家不存在：%s" % sh)
        d1, d2 = dates.parse(row.get("start_date")), dates.parse(row.get("end_date"))
        if d2 < d1:
            raise BizError("結束日不能早於開始日")
        sp = row.get("special_price")
        dc = row.get("discount")
        sp = D(sp) if sp not in (None, "") else None
        dc = D(dc) if dc not in (None, "") else None
        if sp is None and dc is None:
            raise BizError("請輸入特價或折數")
        if dc is not None and not (0 < dc < 100):
            raise BizError("折數請填 1～99（例：80＝打八折）")
        vals = (sh, pn, (row.get("color") or "").strip(), (row.get("size") or "").strip(), d1, d2, sp, dc,
                (row.get("memo") or "")[:60], 1 if row.get("active", 1) in (1, True, "1") else 0)
        if sid:
            self.db.run("UPDATE specials SET sh_no=%s, prod_no=%s, color=%s, size=%s, start_date=%s, end_date=%s, "
                        "special_price=%s, discount=%s, memo=%s, active=%s WHERE id=%s", vals + (sid,))
        else:
            sid = self.db.run("INSERT INTO specials (sh_no, prod_no, color, size, start_date, end_date, special_price, "
                              "discount, memo, active, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                              vals + (self.uid,))
        self.log("save_special", pn, sid)
        return sid

    def delete_special(self, sid):
        self.db.run("DELETE FROM specials WHERE id=%s", (sid,))

    def shop_discount(self, sh_no):
        v = self.db.scalar("SELECT discount FROM shops WHERE sh_no=%s", (sh_no,))
        return D(v if v is not None else 100)

    def list_docs(self, code=None, d1=None, d2=None, party="", q="", limit=300):
        where, args = [], []
        if code:
            where.append("d.doc_type=%s"); args.append(code)
        if d1:
            where.append("d.doc_date>=%s"); args.append(dates.parse(d1))
        if d2:
            where.append("d.doc_date<=%s"); args.append(dates.parse(d2))
        if party:
            where.append("(d.sh_no=%s OR d.sh_no2=%s OR d.wh_no=%s OR d.wh_no2=%s OR d.ma_no=%s)")
            args += [party] * 5
        if q:
            where.append("(d.doc_no LIKE %s OR d.memo LIKE %s OR d.ref_no LIKE %s)"); args += ["%" + q + "%"] * 3
        sql = ("SELECT d.*, s.short_name sh_name, w.name wh_name, v.short_name ma_name FROM docs d "
               "LEFT JOIN shops s ON s.sh_no=d.sh_no LEFT JOIN warehouses w ON w.wh_no=d.wh_no "
               "LEFT JOIN vendors v ON v.ma_no=d.ma_no")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY d.doc_date DESC, d.doc_no DESC LIMIT %d" % limit
        return self.db.all(sql, args)

    def get_doc(self, doc_id):
        h = self.db.one("SELECT * FROM docs WHERE id=%s", (doc_id,))
        if not h:
            raise BizError("單據不存在")
        lines = self.db.all(
            "SELECT l.*, p.name FROM doc_lines l LEFT JOIN products p ON p.prod_no=l.prod_no "
            "AND p.color=l.color AND p.size=l.size WHERE l.doc_id=%s ORDER BY l.seq, l.id", (doc_id,))
        return h, lines

    def _validate_header(self, dt, h):
        need = {"wh_no": ("warehouses", "wh_no", "倉庫"), "wh_no2": ("warehouses", "wh_no", "調入倉庫"),
                "sh_no": ("shops", "sh_no", "店家"), "sh_no2": ("shops", "sh_no", "調入店家"),
                "ma_no": ("vendors", "ma_no", "廠商")}
        for f in dt.fields:
            if f in need:
                tbl, k, title = need[f]
                v = (h.get(f) or "").strip()
                if not v:
                    raise BizError("請選擇%s" % title)
                if not self.db.one("SELECT 1 FROM %s WHERE %s=%%s" % (tbl, k), (v,)):
                    raise BizError("%s「%s」不存在" % (title, v))
        if "wh_no2" in dt.fields and h.get("wh_no") == h.get("wh_no2"):
            raise BizError("調出與調入倉庫不能相同")
        if "sh_no2" in dt.fields and h.get("sh_no") == h.get("sh_no2"):
            raise BizError("調出與調入店家不能相同")

    def save_doc(self, code, header, lines, doc_id=None):
        """新增或修改單據；庫存在同一個交易內回沖舊量、套用新量。回傳 doc_id。"""
        dt = BY_CODE[code]
        h = dict(header)
        h["doc_date"] = dates.parse(h.get("doc_date") or dates.today())
        self._validate_header(dt, h)
        disc = D(h.get("discount") or 100) if "discount" in dt.fields else Decimal(100)
        clean = []
        for i, ln in enumerate(lines, 1):
            pn = (ln.get("prod_no") or "").strip()
            if not pn:
                continue
            try:
                qty = int(D(ln.get("qty") or 0))
            except Exception:
                raise BizError("第 %d 筆數量不是數字" % i)
            if qty == 0:
                continue
            if qty < 0 and not dt.signed:
                raise BizError("第 %d 筆數量不能是負數" % i)
            color, size = (ln.get("color") or "").strip(), (ln.get("size") or "").strip()
            p = self.db.one("SELECT * FROM products WHERE prod_no=%s AND color=%s AND size=%s", (pn, color, size))
            if not p:
                raise BizError("第 %d 筆產品 %s-%s-%s 不存在" % (i, pn, color, size))
            memo = (ln.get("memo") or "")
            if ln.get("price") not in (None, ""):
                price = D(ln["price"])
            else:
                price, tag = self.price_info(code, p, h)
                memo = memo or tag
            cost = D(p["cost"])
            amount = money(qty * price * disc / 100)
            clean.append(dict(seq=len(clean) + 1, prod_no=pn, color=color, size=size, qty=qty, price=price,
                              cost=cost, amount=amount, memo=memo[:60]))
        if not clean:
            raise BizError("沒有任何明細")
        h["total_qty"] = sum(x["qty"] for x in clean)
        h["total_amt"] = sum(x["amount"] for x in clean)
        h["total_cost"] = money(sum(x["qty"] * x["cost"] for x in clean))
        h["discount"] = disc
        hcols = ["doc_date", "wh_no", "wh_no2", "sh_no", "sh_no2", "ma_no", "per_no", "reason", "ref_no",
                 "bill_no", "discount", "total_qty", "total_amt", "total_cost", "pay_cash", "pay_card",
                 "pay_voucher", "memo"]
        vals = []
        for c in hcols:
            v = h.get(c)
            if c.startswith("pay_"):
                v = D(v or 0)
            elif v is None:
                v = ""
            vals.append(v)
        with self.db.tx():
            if doc_id:
                old = self.db.one("SELECT doc_type FROM docs WHERE id=%s FOR UPDATE", (doc_id,))
                if not old:
                    raise BizError("單據不存在（可能已被刪除）")
                self.db.run("UPDATE docs SET " + ",".join("%s=%%s" % c for c in hcols) + ", updated_by=%s WHERE id=%s",
                            vals + [self.uid, doc_id])
                self.db.run("DELETE FROM doc_lines WHERE doc_id=%s", (doc_id,))
            else:
                doc_no = (h.get("doc_no") or "").strip() or self.next_doc_no(code, h["doc_date"])
                if self.db.one("SELECT 1 FROM docs WHERE doc_type=%s AND doc_no=%s", (code, doc_no)):
                    doc_no = self.next_doc_no(code, h["doc_date"])
                doc_id = self.db.run("INSERT INTO docs (doc_type, doc_no, created_by, updated_by, " + ",".join(hcols) +
                                     ") VALUES (%s,%s,%s,%s," + ",".join(["%s"] * len(hcols)) + ")",
                                     [code, doc_no, self.uid, self.uid] + vals)
            self.db.many("INSERT INTO doc_lines (doc_id, seq, prod_no, color, size, qty, price, cost, amount, memo) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                         [(doc_id, x["seq"], x["prod_no"], x["color"], x["size"], x["qty"], x["price"], x["cost"],
                           x["amount"], x["memo"]) for x in clean])
            self._repost(doc_id)
        self.log("save_doc", code, doc_id)
        return doc_id

    def delete_doc(self, doc_id):
        with self.db.tx():
            self._unpost(doc_id)
            self.db.run("DELETE FROM docs WHERE id=%s", (doc_id,))
        self.log("del_doc", doc_id)

    def _unpost(self, doc_id):
        self.db.run(
            "UPDATE stock s JOIN (SELECT loc_type, loc_no, prod_no, color, size, SUM(qty) q FROM stock_moves "
            "WHERE doc_id=%s GROUP BY loc_type, loc_no, prod_no, color, size) m "
            "ON s.loc_type=m.loc_type AND s.loc_no=m.loc_no AND s.prod_no=m.prod_no AND s.color=m.color "
            "AND s.size=m.size SET s.qty=s.qty-m.q", (doc_id,))
        self.db.run("DELETE FROM stock_moves WHERE doc_id=%s", (doc_id,))

    def _moves_for(self, doc_id):
        h = self.db.one("SELECT * FROM docs WHERE id=%s", (doc_id,))
        dt = BY_CODE[h["doc_type"]]
        lines = self.db.all("SELECT prod_no, color, size, qty FROM doc_lines WHERE doc_id=%s", (doc_id,))
        out = []
        for f, sign in dt.effects:
            loc_type = "W" if f.startswith("wh") else "S"
            loc = h[f]
            for ln in lines:
                q = ln["qty"] if sign == 0 else sign * ln["qty"]  # 舊資料可能有負數，照舊系統直接相乘
                out.append((doc_id, h["doc_type"], h["doc_date"], loc_type, loc, ln["prod_no"], ln["color"],
                            ln["size"], q))
        return out

    def _repost(self, doc_id):
        self._unpost(doc_id)
        mv = self._moves_for(doc_id)
        self.db.many("INSERT INTO stock_moves (doc_id, doc_type, doc_date, loc_type, loc_no, prod_no, color, size, qty) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", mv)
        self.db.run(
            "INSERT INTO stock (loc_type, loc_no, prod_no, color, size, qty) "
            "SELECT loc_type, loc_no, prod_no, color, size, SUM(qty) FROM stock_moves WHERE doc_id=%s "
            "GROUP BY loc_type, loc_no, prod_no, color, size "
            "ON DUPLICATE KEY UPDATE qty=stock.qty+VALUES(qty)", (doc_id,))

    def rebuild_stock(self):
        """校帳：由所有單據重新展開異動帳並重算庫存（舊系統 A2/A3）。回傳 (單據數, 差異筆數)。"""
        before = {(r["loc_type"], r["loc_no"], r["prod_no"], r["color"], r["size"]): r["qty"]
                  for r in self.db.all("SELECT * FROM stock")}
        ids = [r["id"] for r in self.db.all("SELECT id FROM docs ORDER BY id")]
        with self.db.tx():
            self.db.run("DELETE FROM stock_moves")
            self.db.run("DELETE FROM stock")
            batch = []
            for i in ids:
                batch += self._moves_for(i)
                if len(batch) > 5000:
                    self.db.many("INSERT INTO stock_moves (doc_id, doc_type, doc_date, loc_type, loc_no, prod_no, "
                                 "color, size, qty) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", batch)
                    batch = []
            self.db.many("INSERT INTO stock_moves (doc_id, doc_type, doc_date, loc_type, loc_no, prod_no, color, size, "
                         "qty) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", batch)
            self.db.run("INSERT INTO stock (loc_type, loc_no, prod_no, color, size, qty) SELECT loc_type, loc_no, "
                        "prod_no, color, size, SUM(qty) FROM stock_moves GROUP BY loc_type, loc_no, prod_no, color, size")
        after = {(r["loc_type"], r["loc_no"], r["prod_no"], r["color"], r["size"]): r["qty"]
                 for r in self.db.all("SELECT * FROM stock")}
        diff = sum(1 for k in set(before) | set(after) if before.get(k, 0) != after.get(k, 0))
        self.log("rebuild_stock", len(ids), diff)
        return len(ids), diff

    # ------------------------------------------------ 查詢
    def stock_query(self, loc_type="W", loc_no="", q="", brand="", nonzero=True, limit=2000):
        where, args = ["s.loc_type=%s"], [loc_type]
        if loc_no:
            where.append("s.loc_no=%s"); args.append(loc_no)
        if q:
            where.append("(s.prod_no LIKE %s OR p.name LIKE %s)"); args += [q + "%", "%" + q + "%"]
        if brand:
            where.append("p.brand=%s"); args.append(brand)
        if nonzero:
            where.append("s.qty<>0")
        name_join = ("LEFT JOIN warehouses l ON l.wh_no=s.loc_no" if loc_type == "W"
                     else "LEFT JOIN shops l ON l.sh_no=s.loc_no")
        lname = "l.name" if loc_type == "W" else "l.short_name"
        return self.db.all(
            "SELECT s.loc_no, %s loc_name, s.prod_no, s.color, s.size, p.name, s.qty, p.price1, p.cost, "
            "s.qty*p.cost cost_amt, s.qty*p.price1 sale_amt FROM stock s "
            "LEFT JOIN products p ON p.prod_no=s.prod_no AND p.color=s.color AND p.size=s.size %s "
            "WHERE %s ORDER BY s.loc_no, s.prod_no, s.color, s.size LIMIT %d"
            % (lname, name_join, " AND ".join(where), limit), args)

    def period_summary(self, loc_type, loc_no, d1, d2, q=""):
        """進銷存：期初、各單據加減、期末（依產品）。"""
        d1, d2 = dates.parse(d1), dates.parse(d2)
        cond, args = "loc_type=%s", [loc_type]
        if loc_no:
            cond += " AND loc_no=%s"; args.append(loc_no)
        if q:
            cond += " AND prod_no LIKE %s"; args.append(q + "%")
        types = [d.code for d in DOC_TYPES if d.effects]
        cols = ",".join("SUM(CASE WHEN doc_date BETWEEN %%s AND %%s AND doc_type='%s' THEN qty ELSE 0 END) `%s`"
                        % (t, t) for t in types)
        rows = self.db.all(
            "SELECT m.prod_no, m.color, m.size, MAX(p.name) name, "
            "SUM(CASE WHEN doc_date<%s THEN qty ELSE 0 END) opening, " + cols + ", "
            "SUM(CASE WHEN doc_date<=%s THEN qty ELSE 0 END) closing "
            "FROM stock_moves m LEFT JOIN products p ON p.prod_no=m.prod_no AND p.color=m.color AND p.size=m.size "
            "WHERE " + cond.replace("loc_", "m.loc_").replace("prod_no LIKE", "m.prod_no LIKE") +
            " AND doc_date<=%s GROUP BY m.prod_no, m.color, m.size ORDER BY m.prod_no, m.color, m.size",
            [d1] + [d1, d2] * len(types) + [d2] + args + [d2])
        used = [t for t in types if any(r[t] for r in rows)]
        return rows, used

    def sales_analysis(self, d1, d2, by="product", sh_no="", top=200):
        d1, d2 = dates.parse(d1), dates.parse(d2)
        cond, args = "d.doc_type='TA' AND d.doc_date BETWEEN %s AND %s", [d1, d2]
        if sh_no:
            cond += " AND d.sh_no=%s"; args.append(sh_no)
        if by == "product":
            sql = ("SELECT l.prod_no k, MAX(p.name) n, SUM(l.qty) qty, SUM(l.amount) amt, SUM(l.qty*l.cost) cost "
                   "FROM docs d JOIN doc_lines l ON l.doc_id=d.id LEFT JOIN products p ON p.prod_no=l.prod_no "
                   "AND p.color=l.color AND p.size=l.size WHERE %s GROUP BY l.prod_no ORDER BY qty DESC LIMIT %d")
        elif by == "shop":
            sql = ("SELECT d.sh_no k, MAX(s.short_name) n, SUM(l.qty) qty, SUM(l.amount) amt, SUM(l.qty*l.cost) cost "
                   "FROM docs d JOIN doc_lines l ON l.doc_id=d.id LEFT JOIN shops s ON s.sh_no=d.sh_no "
                   "WHERE %s GROUP BY d.sh_no ORDER BY amt DESC LIMIT %d")
        elif by == "brand":
            sql = ("SELECT IFNULL(p.brand,'') k, MAX(c.name) n, SUM(l.qty) qty, SUM(l.amount) amt, "
                   "SUM(l.qty*l.cost) cost FROM docs d JOIN doc_lines l ON l.doc_id=d.id LEFT JOIN products p "
                   "ON p.prod_no=l.prod_no AND p.color=l.color AND p.size=l.size LEFT JOIN codes c ON "
                   "c.kind='brand' AND c.code=p.brand WHERE %s GROUP BY p.brand ORDER BY amt DESC LIMIT %d")
        elif by in ("season", "style", "fabric"):
            sql = ("SELECT CONCAT(IFNULL(p.year,''),' ',IFNULL(p.{f},'')) k, MAX(c.name) n, SUM(l.qty) qty, "
                   "SUM(l.amount) amt, SUM(l.qty*l.cost) cost FROM docs d JOIN doc_lines l ON l.doc_id=d.id "
                   "LEFT JOIN products p ON p.prod_no=l.prod_no AND p.color=l.color AND p.size=l.size "
                   "LEFT JOIN codes c ON c.kind='{f}' AND c.code=p.{f} WHERE %s GROUP BY k ORDER BY amt DESC LIMIT %d"
                   ).format(f=by)
            if by != "season":
                sql = sql.replace("CONCAT(IFNULL(p.year,''),' ',IFNULL(p.%s,''))" % by, "IFNULL(p.%s,'')" % by)
        elif by == "size":
            sql = ("SELECT l.size k, '' n, SUM(l.qty) qty, SUM(l.amount) amt, SUM(l.qty*l.cost) cost FROM docs d "
                   "JOIN doc_lines l ON l.doc_id=d.id WHERE %s GROUP BY l.size ORDER BY qty DESC LIMIT %d")
        elif by == "month":
            sql = ("SELECT DATE_FORMAT(d.doc_date,'%%%%Y-%%%%m') k, '' n, SUM(l.qty) qty, SUM(l.amount) amt, "
                   "SUM(l.qty*l.cost) cost FROM docs d JOIN doc_lines l ON l.doc_id=d.id WHERE %s "
                   "GROUP BY k ORDER BY k LIMIT %d")
        else:  # person
            sql = ("SELECT d.per_no k, MAX(e.name) n, SUM(l.qty) qty, SUM(l.amount) amt, SUM(l.qty*l.cost) cost "
                   "FROM docs d JOIN doc_lines l ON l.doc_id=d.id LEFT JOIN employees e ON e.per_no=d.per_no "
                   "WHERE %s GROUP BY d.per_no ORDER BY amt DESC LIMIT %d")
        rows = self.db.all(sql % (cond, top), args)
        for r in rows:
            r["profit"] = D(r["amt"]) - D(r["cost"])
            r["rate"] = (r["profit"] / D(r["amt"]) * 100).quantize(Decimal("0.1")) if r["amt"] else Decimal(0)
        return rows

    def tracking(self, kind="GE"):
        """公司已訂未進（GE→PI）或店家訂單出貨狀況（OR→GR），以參考單號對應。"""
        follow = "PI" if kind == "GE" else "GR"
        return self.db.all(
            "SELECT d.doc_no, d.doc_date, d.sh_no, d.ma_no, l.prod_no, l.color, l.size, SUM(l.qty) ordered, "
            "IFNULL((SELECT SUM(l2.qty) FROM docs d2 JOIN doc_lines l2 ON l2.doc_id=d2.id WHERE d2.doc_type=%s "
            "AND d2.ref_no=d.doc_no AND l2.prod_no=l.prod_no AND l2.color=l.color AND l2.size=l.size),0) done "
            "FROM docs d JOIN doc_lines l ON l.doc_id=d.id WHERE d.doc_type=%s "
            "GROUP BY d.id, l.prod_no, l.color, l.size ORDER BY d.doc_date DESC, d.doc_no LIMIT 2000",
            (follow, kind))

    def product_history(self, prod_no, color="", size="", d1=None, d2=None):
        where, args = ["m.prod_no=%s"], [prod_no]
        if color:
            where.append("m.color=%s"); args.append(color)
        if size:
            where.append("m.size=%s"); args.append(size)
        if d1:
            where.append("m.doc_date>=%s"); args.append(dates.parse(d1))
        if d2:
            where.append("m.doc_date<=%s"); args.append(dates.parse(d2))
        return self.db.all("SELECT m.doc_date, m.doc_type, d.doc_no, m.loc_type, m.loc_no, m.color, m.size, m.qty, "
                           "d.memo FROM stock_moves m JOIN docs d ON d.id=m.doc_id WHERE " + " AND ".join(where) +
                           " ORDER BY m.doc_date, d.doc_no", args)

    # ------------------------------------------------ 盤點
    def stocktake_diff(self, doc_id):
        h, lines = self.get_doc(doc_id)
        if h["doc_type"] not in ("ST", "CK"):
            raise BizError("只有盤點單可以計算盤差")
        loc_type, loc = ("W", h["wh_no"]) if h["doc_type"] == "ST" else ("S", h["sh_no"])
        counted = {}
        for ln in lines:
            k = (ln["prod_no"], ln["color"], ln["size"])
            counted[k] = counted.get(k, 0) + ln["qty"]
        # 帳面量＝盤點日（含）為止的異動合計
        book = {(r["prod_no"], r["color"], r["size"]): int(r["q"]) for r in self.db.all(
            "SELECT prod_no, color, size, SUM(qty) q FROM stock_moves WHERE loc_type=%s AND loc_no=%s "
            "AND doc_date<=%s GROUP BY prod_no, color, size", (loc_type, loc, h["doc_date"]))}
        out = []
        for k in sorted(set(counted) | set(book)):
            c, b = counted.get(k, 0), book.get(k, 0)
            if c != b:
                out.append(dict(prod_no=k[0], color=k[1], size=k[2], book=b, counted=c, diff=c - b))
        return h, out

    def post_stocktake(self, doc_id, only_counted=True):
        """依盤差產生調整單（公司 MA／店家 TR），回傳新單 id。"""
        h, diff = self.stocktake_diff(doc_id)
        if only_counted:
            diff = [x for x in diff if x["counted"] != 0 or x["book"] == 0]
        if not diff:
            raise BizError("沒有盤差")
        code = "MA" if h["doc_type"] == "ST" else "TR"
        header = dict(doc_date=h["doc_date"], wh_no=h["wh_no"], sh_no=h["sh_no"], reason="",
                      memo="盤差 %s" % h["doc_no"], ref_no=h["doc_no"])
        lines = [dict(prod_no=x["prod_no"], color=x["color"], size=x["size"], qty=x["diff"]) for x in diff]
        return self.save_doc(code, header, lines)

    # ------------------------------------------------ 應收帳款
    def ar_compute(self, sh_no, period):
        d1, d2 = dates.month_range(period)
        shop = self.db.one("SELECT * FROM shops WHERE sh_no=%s", (sh_no,))
        if not shop:
            raise BizError("店家不存在")

        def amt(code):
            return D(self.db.scalar("SELECT IFNULL(SUM(total_amt),0) FROM docs WHERE doc_type=%s AND sh_no=%s "
                                    "AND doc_date BETWEEN %s AND %s", (code, sh_no, d1, d2)))
        ship, ret, sales = amt("GR"), amt("DR"), amt("TA")
        fee = D(self.db.scalar("SELECT IFNULL(SUM(amount),0) FROM ar_fees WHERE sh_no=%s AND fee_date BETWEEN %s AND %s",
                               (sh_no, d1, d2)))
        if shop["settle_mode"] == "C":
            comm = money(sales * D(shop["commission"]) / 100)
            amount = sales - comm - fee
        else:
            comm = Decimal(0)
            amount = ship - ret - fee
        return dict(sh_no=sh_no, short_name=shop["short_name"], period=period, settle_mode=shop["settle_mode"],
                    ship_amt=ship, return_amt=ret, sales_amt=sales, commission_amt=comm, fee_amt=fee,
                    amount=money(amount))

    def ar_close(self, period, sh_list=None):
        shops = sh_list or [r["sh_no"] for r in self.db.all("SELECT sh_no FROM shops WHERE active=1")]
        out = []
        with self.db.tx():
            for sh in shops:
                r = self.ar_compute(sh, period)
                if not any([r["ship_amt"], r["return_amt"], r["sales_amt"], r["fee_amt"]]):
                    continue
                self.db.run("REPLACE INTO ar_closings (sh_no, period, ship_amt, return_amt, sales_amt, commission_amt, "
                            "fee_amt, amount, closed_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (sh, period, r["ship_amt"], r["return_amt"], r["sales_amt"], r["commission_amt"],
                             r["fee_amt"], r["amount"], self.uid))
                out.append(r)
        self.log("ar_close", period, len(out))
        return out

    def ar_balances(self, q=""):
        return self.db.all(
            "SELECT s.sh_no, s.short_name, s.settle_mode, "
            "IFNULL((SELECT SUM(amount) FROM ar_closings c WHERE c.sh_no=s.sh_no),0) billed, "
            "IFNULL((SELECT SUM(amount+allowance) FROM ar_payments p WHERE p.sh_no=s.sh_no),0) paid, "
            "(SELECT MAX(period) FROM ar_closings c WHERE c.sh_no=s.sh_no) last_period "
            "FROM shops s WHERE (s.sh_no LIKE %s OR s.short_name LIKE %s) ORDER BY s.sh_no",
            ("%" + q + "%", "%" + q + "%"))

    def ar_history(self, sh_no):
        rows = [dict(date=dates.month_range(r["period"])[1], kind="結帳", ref=r["period"], debit=r["amount"],
                     credit=Decimal(0), memo="出%s 退%s 銷%s 抽成%s 費用%s" % (
                         r["ship_amt"], r["return_amt"], r["sales_amt"], r["commission_amt"], r["fee_amt"]))
                for r in self.db.all("SELECT * FROM ar_closings WHERE sh_no=%s", (sh_no,))]
        rows += [dict(date=r["pay_date"], kind="收款", ref=r["bill_no"] or r["method"], debit=Decimal(0),
                      credit=D(r["amount"]) + D(r["allowance"]), memo=r["memo"] or "", id=r["id"])
                 for r in self.db.all("SELECT * FROM ar_payments WHERE sh_no=%s", (sh_no,))]
        rows.sort(key=lambda x: (x["date"], x["kind"]))
        bal = Decimal(0)
        for r in rows:
            bal += D(r["debit"]) - D(r["credit"])
            r["balance"] = bal
        return rows

    def add_payment(self, sh_no, pay_date, amount, allowance=0, method="現金", bill_no="", memo=""):
        if not self.db.one("SELECT 1 FROM shops WHERE sh_no=%s", (sh_no,)):
            raise BizError("店家不存在")
        if D(amount) == 0 and D(allowance) == 0:
            raise BizError("請輸入收款金額")
        self.db.run("INSERT INTO ar_payments (sh_no, pay_date, amount, allowance, method, bill_no, memo, created_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (sh_no, dates.parse(pay_date), D(amount), D(allowance),
                                                       method, bill_no, memo, self.uid))

    def delete_payment(self, pid):
        self.db.run("DELETE FROM ar_payments WHERE id=%s", (pid,))

    def list_fees(self, sh_no="", period=""):
        where, args = [], []
        if sh_no:
            where.append("f.sh_no=%s"); args.append(sh_no)
        if period:
            d1, d2 = dates.month_range(period)
            where.append("f.fee_date BETWEEN %s AND %s"); args += [d1, d2]
        return self.db.all("SELECT f.*, s.short_name, c.name subject_name FROM ar_fees f LEFT JOIN shops s ON "
                           "s.sh_no=f.sh_no LEFT JOIN codes c ON c.kind='subject' AND c.code=f.subject" +
                           (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY f.fee_date DESC LIMIT 500",
                           args)

    def add_fee(self, sh_no, fee_date, subject, amount, memo=""):
        if not self.db.one("SELECT 1 FROM shops WHERE sh_no=%s", (sh_no,)):
            raise BizError("店家不存在")
        self.db.run("INSERT INTO ar_fees (sh_no, fee_date, subject, amount, memo, created_by) VALUES "
                    "(%s,%s,%s,%s,%s,%s)", (sh_no, dates.parse(fee_date), subject, D(amount), memo, self.uid))

    def delete_fee(self, fid):
        self.db.run("DELETE FROM ar_fees WHERE id=%s", (fid,))

    # ------------------------------------------------ 首頁統計
    def dashboard(self):
        t = dates.today()
        m1 = t.replace(day=1)
        g = lambda sql, a=(): self.db.scalar(sql, a) or 0
        return dict(
            products=g("SELECT COUNT(*) FROM products WHERE active=1"),
            shops=g("SELECT COUNT(*) FROM shops WHERE active=1"),
            wh_qty=g("SELECT IFNULL(SUM(qty),0) FROM stock WHERE loc_type='W'"),
            sh_qty=g("SELECT IFNULL(SUM(qty),0) FROM stock WHERE loc_type='S'"),
            month_sales=g("SELECT IFNULL(SUM(total_amt),0) FROM docs WHERE doc_type='TA' AND doc_date>=%s", (m1,)),
            month_ship=g("SELECT IFNULL(SUM(total_amt),0) FROM docs WHERE doc_type='GR' AND doc_date>=%s", (m1,)),
            today_docs=g("SELECT COUNT(*) FROM docs WHERE doc_date=%s", (t,)),
            recent=self.db.all("SELECT doc_type, doc_no, doc_date, sh_no, wh_no, total_qty, total_amt FROM docs "
                               "ORDER BY id DESC LIMIT 12"),
        )
