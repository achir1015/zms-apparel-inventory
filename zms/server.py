"""內建 MariaDB 實例：第一次自動建立資料夾，開程式時啟動，關程式時停止。"""
import os
import socket
import subprocess
import time

from .config import Config, save

MY_INI = """[mysqld]
datadir={datadir}
port={port}
{extra}bind-address={bind}
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
default-time-zone=+08:00
innodb_buffer_pool_size=128M
max_connections=60
[client]
port={port}
default-character-set=utf8mb4
"""


def _exe(cfg: Config, name: str) -> str:
    return os.path.join(cfg.mariadb_bin, name + (".exe" if os.name == "nt" else ""))


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


class EmbeddedServer:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.proc = None
        self.log_path = os.path.join(os.path.dirname(cfg.datadir), "mariadbd.log")

    @property
    def ini(self) -> str:
        return os.path.join(self.cfg.datadir, "my.ini")

    def initialized(self) -> bool:
        return os.path.isdir(os.path.join(self.cfg.datadir, "mysql"))

    @property
    def basedir(self) -> str:
        return os.path.dirname(self.cfg.mariadb_bin.rstrip("/\\"))

    def write_ini(self):
        extra = ""
        if os.name != "nt":
            # macOS／Linux：socket 放資料夾內，避免和系統上其他 MariaDB 搶 /tmp/mysql.sock
            extra = "basedir=%s\nsocket=%s\npid-file=%s\n" % (
                self.basedir, os.path.join(self.cfg.datadir, "mysql.sock"), os.path.join(self.cfg.datadir, "mariadbd.pid"))
            for sub in ("mariadb", "mysql"):
                share = os.path.join(self.basedir, "share", sub)
                if os.path.isdir(os.path.join(share, "english")):
                    extra += "lc-messages-dir=%s\n" % share
                    break
        with open(self.ini, "w", encoding="utf-8") as f:
            f.write(MY_INI.format(datadir=self.cfg.datadir.replace("\\", "/"), port=self.cfg.port, extra=extra,
                                  bind="0.0.0.0" if self.cfg.extra.get("lan") else "127.0.0.1"))

    def initialize(self):
        if not self.cfg.mariadb_bin:
            raise RuntimeError("找不到 MariaDB 程式（mariadbd）。請安裝 MariaDB，或在設定改連既有伺服器。")
        os.makedirs(os.path.dirname(self.cfg.datadir), exist_ok=True)
        if os.name == "nt":
            cmd = [_exe(self.cfg, "mariadb-install-db"), "--datadir=" + self.cfg.datadir,
                   "--port=%d" % self.cfg.port, "--password=" + self.cfg.password]
        else:
            # macOS／Linux：install-db 是 shell 腳本，要指定 basedir；root 先用空密碼，啟動後再設密碼
            cmd = [_exe(self.cfg, "mariadb-install-db"), "--no-defaults", "--basedir=" + self.basedir,
                   "--datadir=" + self.cfg.datadir, "--auth-root-authentication-method=normal", "--skip-test-db"]
            self._set_pw_after_start = True
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=_NOWIN)
        if r.returncode != 0:
            raise RuntimeError("建立資料庫資料夾失敗：\n" + (r.stdout or "") + (r.stderr or ""))
        self.write_ini()
        save(self.cfg)

    def _set_root_password(self):
        import pymysql
        c = pymysql.connect(host=self.cfg.host, port=int(self.cfg.port), user="root", password="", connect_timeout=5)
        try:
            with c.cursor() as cur:
                cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (self.cfg.password,))
                cur.execute("FLUSH PRIVILEGES")
        finally:
            c.close()

    def _ours_running(self) -> bool:
        """連接埠上已有服務：是不是我們的實例（帳密能登入）？"""
        try:
            import pymysql
            pymysql.connect(host=self.cfg.host, port=int(self.cfg.port), user=self.cfg.user,
                            password=self.cfg.password, connect_timeout=3).close()
            return True
        except Exception:
            return False

    def _datadir_in_use(self) -> bool:
        """有沒有 mariadbd 正在用我們的設定檔（同一個資料夾）在跑？"""
        try:
            if os.name == "nt":
                out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                      "Get-CimInstance Win32_Process -Filter \"Name='mariadbd.exe'\" | "
                                      "ForEach-Object { $_.CommandLine }"],
                                     capture_output=True, text=True, timeout=20, creationflags=_NOWIN,
                                     encoding="utf-8", errors="replace").stdout
            else:
                out = subprocess.run(["ps", "-Ao", "command"], capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return False
        return os.path.normcase(self.ini) in os.path.normcase(out)

    def start(self, timeout: float = 30):
        if port_open(self.cfg.host, self.cfg.port):
            if self._ours_running():
                return  # 已在執行（可能是上次沒關乾淨，或另一個視窗）
            if self._datadir_in_use():
                # 同一個資料夾已有資料庫在跑，只是密碼對不上 → 絕不能再開第二份（會毀損資料）
                raise RuntimeError("資料庫已在執行，但目前設定檔的密碼無法登入。請關閉所有進銷存視窗後再開啟；"
                                   "若仍失敗，請聯絡系統管理員。")
            # 連接埠被別的程式佔用 → 換一個空的
            for p in range(3318, 3400):
                if not port_open(self.cfg.host, p):
                    self.cfg.port = p
                    break
            save(self.cfg)
        if not self.initialized():
            self.initialize()
        else:
            self.write_ini()
        log = open(self.log_path, "ab")
        self.proc = subprocess.Popen([_exe(self.cfg, "mariadbd"), "--defaults-file=" + self.ini, "--console"],
                                     stdout=log, stderr=subprocess.STDOUT, creationflags=_NOWIN)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError("MariaDB 啟動失敗，請看 " + self.log_path)
            if port_open(self.cfg.host, self.cfg.port):
                if getattr(self, "_set_pw_after_start", False):
                    time.sleep(0.5)
                    self._set_root_password()
                    self._set_pw_after_start = False
                return
            time.sleep(0.3)
        raise RuntimeError("MariaDB 啟動逾時，請看 " + self.log_path)

    def stop(self):
        if not self.proc:
            return
        try:
            subprocess.run([_exe(self.cfg, "mariadb-admin"), "-h127.0.0.1", "-P%d" % self.cfg.port, "-uroot",
                            "-p" + self.cfg.password, "shutdown"], capture_output=True, timeout=20,
                           creationflags=_NOWIN)
            self.proc.wait(timeout=20)
        except Exception:
            self.proc.kill()
        self.proc = None


_NOWIN = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
