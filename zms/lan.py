"""讓手機透過區網連到這台電腦的資料庫：手機專用 MariaDB 帳號與本機 IP。"""
import secrets
import socket

MOBILE_USER = "zms_mobile"


def lan_ips():
    """本機區網 IPv4（優先 192.168.x.x／10.x）。"""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.255.255", 1))   # 不會真的送出封包，只用來挑出對外網卡
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    ips.sort(key=lambda ip: (not ip.startswith("192.168."), not ip.startswith("10."), ip))
    return ips


def ensure_mobile_user(db, cfg):
    """建立（或重設）手機專用帳號 zms_mobile@'%'，只能用本系統的資料庫。回傳密碼。"""
    pw = cfg.extra.get("mobile_password") or secrets.token_urlsafe(9)
    name = cfg.database.replace("`", "")
    # 主機 '%' 要寫成 '%%'，因為帶參數時 PyMySQL 會再做一次 % 格式化
    db.run("CREATE USER IF NOT EXISTS '%s'@'%%%%' IDENTIFIED BY %%s" % MOBILE_USER, (pw,))
    db.run("ALTER USER '%s'@'%%%%' IDENTIFIED BY %%s" % MOBILE_USER, (pw,))
    db.run("GRANT SELECT, INSERT, UPDATE, DELETE ON `%s`.* TO '%s'@'%%'" % (name, MOBILE_USER))
    try:
        db.run("FLUSH PRIVILEGES")   # CREATE USER／GRANT 已即時生效；專用帳號沒有 RELOAD 權限時略過
    except Exception:
        pass
    cfg.extra["mobile_password"] = pw
    return pw


def drop_mobile_user(db):
    db.run("DROP USER IF EXISTS '%s'@'%%'" % MOBILE_USER)
