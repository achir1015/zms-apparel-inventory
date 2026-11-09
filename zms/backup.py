"""備份／回存：呼叫 MariaDB 的 dump 與 client 程式，壓縮成 .sql.gz。"""
import gzip
import os
import shutil
import subprocess

from .config import Config

_NOWIN = 0x08000000 if os.name == "nt" else 0


def _tool(cfg: Config, names):
    ext = ".exe" if os.name == "nt" else ""
    dirs = [cfg.mariadb_bin] if cfg.mariadb_bin else []
    for d in dirs:
        for n in names:
            p = os.path.join(d, n + ext)
            if os.path.isfile(p):
                return p
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    raise RuntimeError("找不到 MariaDB 工具：%s" % "/".join(names))


def _args(cfg):
    return ["-h", cfg.host, "-P", str(cfg.port), "-u", cfg.user, "--default-character-set=utf8mb4"]


def backup(cfg: Config, path: str) -> str:
    exe = _tool(cfg, ["mariadb-dump", "mysqldump"])
    env = dict(os.environ, MYSQL_PWD=cfg.password)
    p = subprocess.Popen([exe] + _args(cfg) + ["--single-transaction", "--routines", "--triggers", cfg.database],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, creationflags=_NOWIN)
    with gzip.open(path, "wb") as f:
        shutil.copyfileobj(p.stdout, f)
    err = p.stderr.read().decode("utf-8", "replace")
    if p.wait() != 0:
        os.remove(path)
        raise RuntimeError("備份失敗：" + err)
    return path


def restore(cfg: Config, path: str):
    exe = _tool(cfg, ["mariadb", "mysql"])
    env = dict(os.environ, MYSQL_PWD=cfg.password)
    p = subprocess.Popen([exe] + _args(cfg) + [cfg.database], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=env, creationflags=_NOWIN)
    opener = gzip.open if path.lower().endswith(".gz") else open
    with opener(path, "rb") as f:
        shutil.copyfileobj(f, p.stdin)
    p.stdin.close()
    err = p.stderr.read().decode("utf-8", "replace")
    if p.wait() != 0:
        raise RuntimeError("回存失敗：" + err)
