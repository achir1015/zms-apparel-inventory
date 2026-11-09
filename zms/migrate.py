"""把進銷存資料複製到另一台 MariaDB（例如筆電上另外安裝的 MariaDB 11.8）。

原本的資料庫不刪除、不清空（只讀取），之後隨時可以切回。
"""
from .config import Config
from .db import Database

ORDER_FIRST = ["docs"]          # 先複製表頭，再複製有外鍵的明細
BATCH = 1000


def table_counts(db: Database):
    return {r["t"]: int(r["n"]) for r in db.all(
        "SELECT table_name t, table_rows n FROM information_schema.tables WHERE table_schema=%s", (db.cfg.database,))}


def exact_counts(db: Database, tables):
    return {t: int(db.scalar("SELECT COUNT(*) FROM `%s`" % t)) for t in tables}


def target_has_data(target: Config) -> bool:
    db = Database(target)
    try:
        exists = db._connect(with_db=False)
        with exists.cursor() as cur:
            cur.execute("SHOW DATABASES LIKE %s", (target.database,))
            found = cur.fetchone() is not None
        exists.close()
        if not found:
            return False
        return bool(db.scalar("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s AND "
                              "table_name='products'", (target.database,))) and bool(
            db.scalar("SELECT (SELECT COUNT(*) FROM products)+(SELECT COUNT(*) FROM docs)"))
    finally:
        db.close()


def migrate(src: Database, target: Config, log=print):
    """複製全部資料表到 target（target 的同名資料表會先清空）。回傳 {資料表: 筆數}。"""
    dst = Database(target)
    dst.ensure_database()          # 在目標建立資料庫與最新結構
    tables = [r["t"] for r in src.all(
        "SELECT table_name t FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'",
        (src.cfg.database,))]
    tables.sort(key=lambda t: (t not in ORDER_FIRST, t))
    dst_cols = {}
    for r in dst.all("SELECT table_name t, column_name c FROM information_schema.columns WHERE table_schema=%s",
                     (target.database,)):
        dst_cols.setdefault(r["t"], set()).add(r["c"])
    copied = {}
    conn = dst.conn
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        cur.execute("SET UNIQUE_CHECKS=0")
    try:
        for t in tables:
            if t not in dst_cols:
                log("略過 %s（目標沒有這個資料表）" % t)
                continue
            cols = [r["c"] for r in src.all(
                "SELECT column_name c FROM information_schema.columns WHERE table_schema=%s AND table_name=%s "
                "ORDER BY ordinal_position", (src.cfg.database, t)) if r["c"] in dst_cols[t]]
            collist = ",".join("`%s`" % c for c in cols)
            pk = [r["c"] for r in src.all(
                "SELECT column_name c FROM information_schema.key_column_usage WHERE table_schema=%s AND table_name=%s "
                "AND constraint_name='PRIMARY' ORDER BY ordinal_position", (src.cfg.database, t))]
            order = (" ORDER BY " + ",".join("`%s`" % c for c in pk)) if pk else ""
            with conn.cursor() as cur:
                cur.execute("DELETE FROM `%s`" % t)
            n, offset = 0, 0
            while True:
                rows = src.all("SELECT %s FROM `%s`%s LIMIT %d OFFSET %d" % (collist, t, order, BATCH, offset))
                if not rows:
                    break
                with conn.cursor() as cur:
                    cur.executemany("INSERT INTO `%s` (%s) VALUES (%s)" % (t, collist, ",".join(["%s"] * len(cols))),
                                    [tuple(r[c] for c in cols) for r in rows])
                n += len(rows)
                offset += BATCH
            copied[t] = n
            log("%s：%d 筆" % (t, n))
    finally:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
            cur.execute("SET UNIQUE_CHECKS=1")
    # 驗證筆數一致
    after = exact_counts(dst, list(copied))
    bad = {t: (copied[t], after[t]) for t in copied if copied[t] != after[t]}
    dst.close()
    if bad:
        raise RuntimeError("搬移後筆數不一致：%s" % bad)
    return copied
