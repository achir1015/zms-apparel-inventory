"""MariaDB 連線（PyMySQL）與結構建立。"""
import os
import threading
from contextlib import contextmanager

import pymysql
import pymysql.cursors

from .config import Config

SCHEMA_VERSION = "2"

# v2（服飾業）：產品加年度／季別／款式／布料／性別
MIGRATIONS = [
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS year VARCHAR(4) NOT NULL DEFAULT '' AFTER series",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS season VARCHAR(10) NOT NULL DEFAULT '' AFTER year",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS style VARCHAR(10) NOT NULL DEFAULT '' AFTER season",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS fabric VARCHAR(10) NOT NULL DEFAULT '' AFTER style",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS gender VARCHAR(2) NOT NULL DEFAULT '' AFTER fabric",
    "ALTER TABLE products ADD INDEX IF NOT EXISTS idx_prod_season (year, season)",
]


class Database:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._local = threading.local()

    def _connect(self, with_db=True):
        return pymysql.connect(host=self.cfg.host, port=int(self.cfg.port), user=self.cfg.user,
                               password=self.cfg.password, database=self.cfg.database if with_db else None,
                               charset="utf8mb4", autocommit=True, connect_timeout=8,
                               cursorclass=pymysql.cursors.DictCursor)

    @property
    def conn(self):
        c = getattr(self._local, "conn", None)
        if c is None or not c.open:
            c = self._connect()
            self._local.conn = c
        else:
            try:
                c.ping(reconnect=False)
            except Exception:
                c = self._connect()
                self._local.conn = c
        return c

    def close(self):
        c = getattr(self._local, "conn", None)
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
            self._local.conn = None

    # ---- 查詢輔助 ----
    def all(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())

    def one(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()

    def scalar(self, sql, args=None):
        r = self.one(sql, args)
        return None if r is None else next(iter(r.values()))

    def run(self, sql, args=None):
        with self.conn.cursor() as cur:
            n = cur.execute(sql, args)
            return cur.lastrowid if sql.lstrip().upper().startswith("INSERT") else n

    def many(self, sql, rows):
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            return cur.executemany(sql, rows)

    @contextmanager
    def tx(self):
        c = self.conn
        c.begin()
        try:
            yield self
            c.commit()
        except Exception:
            c.rollback()
            raise

    # ---- 建立資料庫 ----
    def ensure_database(self):
        c = self._connect(with_db=False)
        try:
            with c.cursor() as cur:
                try:
                    cur.execute("CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                                % self.cfg.database.replace("`", ""))
                except pymysql.err.OperationalError:
                    pass  # 帳號沒有建庫權限時，資料庫須由管理員先建好；下面連線時會再檢查
        finally:
            c.close()
        sql = open(os.path.join(os.path.dirname(__file__), "schema.sql"), encoding="utf-8").read()
        for stmt in _split_sql(sql):
            self.run(stmt)
        for stmt in MIGRATIONS:  # 舊版資料庫自動補欄位（可重複執行）
            self.run(stmt)
        self.run("INSERT IGNORE INTO company (id, name) VALUES (1, '我的公司')")
        self.run("REPLACE INTO meta (k, v) VALUES ('schema_version', %s)", (SCHEMA_VERSION,))


GSSAPI_HINT = ("帳號或密碼錯誤（Windows 版 MariaDB 在密碼不對時會改要 Windows 驗證，所以出現 GSSAPI 訊息）。\n"
               "若確定密碼正確仍失敗，代表此帳號只允許 Windows 驗證，請用 HeidiSQL 登入後建立專用帳號：\n"
               "CREATE USER 'zms'@'localhost' IDENTIFIED BY '自訂密碼';\n"
               "GRANT ALL ON zms_inventory.* TO 'zms'@'localhost';")


def friendly_error(e) -> str:
    s = str(e.args[1] if len(getattr(e, "args", ())) > 1 else e)
    if "auth_gssapi" in s:
        return "連不上：" + GSSAPI_HINT
    if "Access denied" in s:
        return "連不上：帳號或密碼錯誤（%s）" % s
    if "Can't connect" in s or "10061" in s or "timed out" in s:
        return "連不上：伺服器沒有回應，請確認 MariaDB 服務已啟動、伺服器位址與連接埠正確（%s）" % s
    return "連不上：%s" % s


def test_connection(host, port, user, password, database):
    """測試連線，回傳 (成功?, 說明)。"""
    try:
        c = pymysql.connect(host=host, port=int(port), user=user, password=password, charset="utf8mb4",
                            connect_timeout=5)
    except Exception as e:
        return False, friendly_error(e)
    try:
        with c.cursor() as cur:
            cur.execute("SELECT VERSION()")
            ver = cur.fetchone()[0]
            cur.execute("SHOW DATABASES LIKE %s", (database,))
            exists = cur.fetchone() is not None
        return True, "連線成功（MariaDB %s）；資料庫 %s %s" % (ver, database, "已存在" if exists else "不存在，儲存後會自動建立")
    finally:
        c.close()


def _split_sql(sql):
    out, buf = [], []
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--") or not s:
            continue
        buf.append(line)
        if s.endswith(";"):
            out.append("\n".join(buf).rstrip(";"))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out
