"""設定檔：資料庫連線與內建 MariaDB 實例。

設定存在 <資料夾>/config.json；資料夾預設為程式旁的 data/，
打包後（或程式目錄不可寫）改用使用者目錄。
"""
import json
import os
import secrets
import sys
from dataclasses import dataclass, asdict, field


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir() -> str:
    env = os.environ.get("ZMS_DATA_DIR")
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    if getattr(sys, "frozen", False):
        # 安裝版：資料放使用者目錄（不受程式更新／解除安裝影響）
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.path.expanduser("~/.local/share")
        d = os.path.join(base, "ZMSInventory")
        os.makedirs(d, exist_ok=True)
        return d
    d = os.path.join(app_dir(), "data")
    try:
        os.makedirs(d, exist_ok=True)
        test = os.path.join(d, ".w")
        open(test, "w").close()
        os.remove(test)
        return d
    except OSError:
        base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
        d = os.path.join(base, "ZMSInventory")
        os.makedirs(d, exist_ok=True)
        return d


def bundled_mariadb_bin() -> str:
    """安裝版附帶的 MariaDB：Windows 在程式旁 mariadb/bin；macOS 在 .app/Contents/Resources/mariadb/bin。"""
    exe = "mariadbd.exe" if os.name == "nt" else "mariadbd"
    for c in (os.path.join(app_dir(), "mariadb", "bin"),
              os.path.normpath(os.path.join(app_dir(), "..", "Resources", "mariadb", "bin"))):
        if os.path.isfile(os.path.join(c, exe)):
            return c
    return ""


def find_mariadb_bin() -> str:
    """找 MariaDB 程式資料夾（內建模式用）。"""
    cands = [os.environ.get("ZMS_MARIADB_BIN", ""), bundled_mariadb_bin(), r"C:\mariadb\bin"]
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    if os.path.isdir(pf):
        for n in sorted(os.listdir(pf), reverse=True):
            if n.lower().startswith("mariadb"):
                cands.append(os.path.join(pf, n, "bin"))
    cands += ["/opt/homebrew/opt/mariadb/bin", "/usr/local/opt/mariadb/bin", "/opt/homebrew/bin", "/usr/local/bin",
              "/usr/bin", "/usr/sbin"]
    exe = "mariadbd.exe" if os.name == "nt" else "mariadbd"
    for c in cands:
        if c and os.path.isfile(os.path.join(c, exe)):
            return c
    return ""


@dataclass
class Config:
    mode: str = "embedded"          # embedded＝程式自動啟停內建實例；external＝連既有伺服器
    host: str = "127.0.0.1"
    port: int = 3318
    user: str = "root"
    password: str = ""
    database: str = "zms_inventory"
    mariadb_bin: str = ""
    datadir: str = ""
    last_user: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def path(self) -> str:
        return os.path.join(data_dir(), "config.json")


def load() -> Config:
    p = os.path.join(data_dir(), "config.json")
    cfg = Config()
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        for k, v in raw.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
    if not cfg.datadir:
        cfg.datadir = os.path.join(data_dir(), "mariadb")
    exe = "mariadbd.exe" if os.name == "nt" else "mariadbd"
    bundled = bundled_mariadb_bin()
    if bundled:
        cfg.mariadb_bin = bundled  # 安裝版一律用附帶的 MariaDB（程式搬家或更新後路徑也對）
    elif not cfg.mariadb_bin or not os.path.isfile(os.path.join(cfg.mariadb_bin, exe)):
        cfg.mariadb_bin = find_mariadb_bin()
    if cfg.mode == "embedded" and not cfg.password:
        cfg.password = secrets.token_urlsafe(18)
    return cfg


def save(cfg: Config) -> None:
    with open(cfg.path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
