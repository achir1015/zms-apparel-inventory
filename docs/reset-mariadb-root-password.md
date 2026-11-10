# 忘記 MariaDB root 密碼：用 skip-grant-tables 重設（Windows）

適用：Windows 上以服務方式安裝的 MariaDB（例如 MariaDB 11.8，服務名稱 `MariaDB11`，port 3307），
root 密碼忘記、而且勾「使用 Windows 驗證」也登不進去時。

> 進銷存系統平常用專用帳號 `zms`／`zms_mobile` 連線，不是 root，所以重設 root 密碼**不會影響**進銷存資料與連線。

以下路徑以 `C:\Program Files\MariaDB 11.8` 為例，請依實際安裝的版本資料夾修改。
服務名稱可在「服務」（services.msc）裡查到。

## 步驟

### 1. 停止 MariaDB 服務

用「**以系統管理員身分執行**」開啟 PowerShell（視窗 A）：

```powershell
net stop MariaDB11
```

### 2. 以「略過權限檢查」模式啟動

仍在視窗 A：

```powershell
& "C:\Program Files\MariaDB 11.8\bin\mariadbd.exe" --defaults-file="C:\Program Files\MariaDB 11.8\data\my.ini" --skip-grant-tables --console
```

視窗會停住不動，這是正常的，**不要關掉**。

### 3. 不用密碼登入

另開一個 PowerShell（視窗 B）：

```powershell
& "C:\Program Files\MariaDB 11.8\bin\mariadb.exe" -u root "--port=3307" "--host=127.0.0.1"
```

> ⚠️ PowerShell 參數要加引號。寫成 `-h127.0.0.1` 時，PowerShell 會從小數點把參數切開，
> 出現 `ERROR 2005 (HY000): Unknown server host '127' (11001)`。

看到 `MariaDB [(none)]>` 就表示進入了。

### 4. 設定新密碼

逐行輸入（把 `新密碼` 換成你要的密碼）：

```sql
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('新密碼') OR gssapi;
exit
```

- `FLUSH PRIVILEGES` 會重新載入權限表，之後才能執行 `ALTER USER`。
- 結尾的 `OR gssapi` 保留 Windows 驗證，之後密碼與 Windows 驗證兩種方式都能登入。
  若出現 gssapi 相關錯誤，可改成不含 `OR gssapi` 的版本：
  `ALTER USER 'root'@'localhost' IDENTIFIED BY '新密碼';`
- 若 root 還有其他主機（例如 `127.0.0.1`、`::1`），可用
  `SELECT user, host FROM mysql.user WHERE user='root';` 查出後逐一 `ALTER USER`。

### 5. 恢復正常服務

回到視窗 A 按 `Ctrl+C` 停止，然後：

```powershell
net start MariaDB11
```

服務剛啟動的幾秒內連線可能被拒絕（`Can't connect … 10061`），稍等再試即可。

### 6. 確認

在 HeidiSQL 的工作階段管理員把密碼改成新密碼 → 儲存 → 開啟，能登入即完成。

## 注意

- `--skip-grant-tables` 模式下**任何人都不需要密碼**就能連進資料庫，改完密碼要立刻用步驟 5 恢復正常服務，不要讓它一直開著。
- 如果只是忘記進銷存專用帳號 `zms` 的密碼，不必走這個流程：用 root 登入 HeidiSQL 後執行
  `ALTER USER 'zms'@'localhost' IDENTIFIED BY '新密碼';`，再到進銷存「資料庫連線設定」填入新密碼。
