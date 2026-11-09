"""一鍵建置 Windows 安裝檔：
1. 準備內附的 MariaDB 最小檔案（packaging/mariadb）
2. flet pack（PyInstaller）打包程式到 dist/ZMSInventory
3. Inno Setup 產生 dist-installer/ZMSInventory-Setup-<版本>.exe

用法：.venv\\Scripts\\python tools\\build_windows.py
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from zms import APP_NAME, APP_VERSION  # noqa: E402

MARIADB_SRC = os.environ.get("ZMS_MARIADB_SRC", r"C:\mariadb")
BIN_FILES = ["mariadbd.exe", "mysqld.exe", "server.dll", "mariadb-install-db.exe", "mariadb-admin.exe",
             "mariadb-dump.exe", "mariadb.exe", "concrt140.dll", "msvcp140.dll", "msvcp140_1.dll",
             "msvcp140_2.dll", "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll", "vcruntime140.dll",
             "vcruntime140_1.dll"]
ISCC_CANDIDATES = [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
                   r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe"]


def prepare_mariadb():
    dst = os.path.join(HERE, "packaging", "mariadb")
    if os.path.isfile(os.path.join(dst, "bin", "mariadbd.exe")):
        return
    os.makedirs(os.path.join(dst, "bin"), exist_ok=True)
    for f in BIN_FILES:
        shutil.copy2(os.path.join(MARIADB_SRC, "bin", f), os.path.join(dst, "bin", f))
    share = os.path.join(dst, "share")
    os.makedirs(share, exist_ok=True)
    for d in ("charsets", "english", "chinese"):
        shutil.copytree(os.path.join(MARIADB_SRC, "share", d), os.path.join(share, d), dirs_exist_ok=True)
    for f in os.listdir(os.path.join(MARIADB_SRC, "share")):
        if f.endswith(".sql"):
            shutil.copy2(os.path.join(MARIADB_SRC, "share", f), share)
    for f in ("COPYING", "README.md", "THIRDPARTY"):
        if os.path.isfile(os.path.join(MARIADB_SRC, f)):
            shutil.copy2(os.path.join(MARIADB_SRC, f), dst)


def pack():
    flet = os.path.join(HERE, ".venv", "Scripts", "flet.exe")
    shutil.rmtree(os.path.join(HERE, "dist"), ignore_errors=True)
    cmd = [flet, "pack", "main.py", "-D", "-y", "-n", "ZMSInventory", "-i", "packaging/icon.ico",
           "--distpath", "dist", "--add-data", "assets:assets", "zms/schema.sql:zms",
           "--product-name", APP_NAME, "--file-description", APP_NAME, "--product-version", APP_VERSION,
           "--file-version", APP_VERSION + ".0", "--company-name", "吳玉柱", "--copyright", "© 2026 吳玉柱"]
    subprocess.run(cmd, cwd=HERE, check=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))


def installer():
    iscc = next((p for p in ISCC_CANDIDATES if os.path.isfile(p)), None)
    if not iscc:
        raise SystemExit("找不到 Inno Setup 6（ISCC.exe）")
    subprocess.run([iscc, "/DAppVer=" + APP_VERSION, os.path.join(HERE, "packaging", "installer.iss")], check=True)
    out = os.path.join(HERE, "dist-installer", "ZMSInventory-Setup-%s.exe" % APP_VERSION)
    print("完成：", out, "%.1f MB" % (os.path.getsize(out) / 1e6))


if __name__ == "__main__":
    prepare_mariadb()
    pack()
    installer()
