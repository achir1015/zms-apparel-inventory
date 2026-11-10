# 資料助秘工具之服飾業進銷存系統
<img width="1345" height="856" alt="image" src="https://github.com/user-attachments/assets/cccc26bc-223a-4a86-9732-33c7895e2f1e" />
<img width="1348" height="853" alt="image" src="https://github.com/user-attachments/assets/6bcd876f-0da4-442f-98cf-99e8d31ea7ab" />
<img width="1349" height="855" alt="image" src="https://github.com/user-attachments/assets/50a99a1b-dc75-457b-bdab-e8b7fe060d90" />

舊「服飾業VD20 進銷存」的 Python 重寫版。資料庫 MariaDB，介面 Flet（同一份程式可出 Windows、macOS、Android、iPhone）。目前完成 **Windows 11 桌面版、macOS 版、Android 手機版**。

## 下載
到 [Releases 最新版](https://github.com/achir1015/zms-apparel-inventory/releases/latest) 下載 `ZMSInventory-Setup-<版本>.exe`（Windows）、`ZMSInventory-<版本>-mac-x86_64.dmg`（macOS）或 `ZMSInventory-<版本>-android.apk`（Android 手機）。iPhone 版製作中。

## 安裝（Windows 10/11 64 位元）
- 執行 `ZMSInventory-Setup-0.6.1.exe`（不需系統管理員權限，預設裝在 `%LOCALAPPDATA%\Programs\ZMSInventory`）。
- 安裝檔內附 MariaDB 10.11，別台電腦不必另外安裝。
- 安裝版的資料與設定在 `%LOCALAPPDATA%\ZMSInventory`（`config.json`、`mariadb\`、`zms.log`）；解除安裝不會刪除資料。
- 重新建置：`.venv\Scripts\python tools\build_windows.py`（flet pack ＋ Inno Setup 6）。

## 安裝（macOS）
- 打開 DMG，把 App 拖到「應用程式」。Intel Mac、macOS 11 以上；Apple 晶片 Mac 可透過 Rosetta 2 執行。
- 第一次開啟出現「無法驗證開發者」：「系統設定 → 隱私權與安全性」下方按「仍要打開」。
- Mac 版**不內附資料庫**，第一次開啟按「設定連線」，連到放資料的電腦（例如 Windows 筆電上的 MariaDB，填該電腦「手機連線」卡片上的 IP、連接埠、帳號與密碼）。
- macOS 詢問「區域網路」權限時請按「允許」，否則會出現 No route to host。
- 資料與設定在 `~/Library/Application Support/ZMSInventory`。重新建置（在 Mac 上）：`bash tools/build_macos.sh`。

## 資料庫
- 預設「內建 MariaDB」：程式開啟時自動啟動（port 3318，只聽本機），關閉視窗時自動停止。資料庫名稱 `zms_inventory`。
- 也可在登入畫面或「系統維護 → 工具」按「資料庫連線設定」，改連既有的 MariaDB（例如筆電上 port 3306 的那套），有「測試連線」按鈕。
- Windows 版 MariaDB 的 root 若只允許 Windows 驗證（GSSAPI），請先用 HeidiSQL 建專用帳號：
  `CREATE USER 'zms'@'localhost' IDENTIFIED BY '密碼'; GRANT ALL ON zms_inventory.* TO 'zms'@'localhost';`
- 忘記 MariaDB root 密碼：見 [忘記 MariaDB root 密碼的重設方法](docs/reset-mariadb-root-password.md)。

## 手機版（iPhone／Android）
- 筆電版開啟「系統維護 → 工具 → 手機連線 → 允許手機連線」，畫面會顯示伺服器 IP、連接埠、帳號與密碼。
- 手機和筆電連同一個 Wi-Fi，手機 App 第一次開啟時輸入這些資料即可（筆電的進銷存要開著）。
- 手機版功能：營運總覽、庫存查詢（顏色×尺寸）、門市銷貨（掃吊牌、自動套特價、現金／刷卡／禮券）、盤點（每掃一次＋1，可看盤差）。
- 手機用專用帳號 `zms_mobile`，只能讀寫資料、不能改資料表結構。

## 開發版執行
- 雙擊 `啟動進銷存系統.bat`（資料在 `data\`）。
- 第一次開啟、資料庫沒有任何帳號時，會請你建立系統管理員帳號。
- 舊資料：「系統維護 → 工具 → 舊系統資料匯入」選 `E:\進銷存系統\KS`。

## 功能
| 群組 | 內容 |
|---|---|
| 服飾業專用 | 整款建檔（一個貨號勾選顏色、選尺寸組，一次產生全部顏色尺寸）、開單「尺寸矩陣」輸入（顏色×尺寸表格，附目前庫存）、庫存尺寸分布表、銷售分析依年度季別／款式／尺寸、吊牌條碼標籤（Code 128；40×60／35×50 吊牌、50×30 貼紙、A4 24 格；可依單據數量列印；有特價時印原價劃線＋特價）、特價品（依貨號／依客戶，指定期間的特價或折數，開單自動套用並標示「特價」）、裝箱標籤（出貨／退貨／調撥／退廠單，第 i / N 箱） |
| 基本資料 | 產品（貨號＋顏色＋尺寸、年度、季別、款式、布料、性別、售價一～三、成本、條碼）、店家、廠商、人員、倉庫、代碼（顏色／尺寸／類別／品牌／系列／季別／款式／布料／單位／原因／費用科目） |
| 倉庫單據 | 進貨、退廠、調撥、壞品、採購、調整、盤點（盤差自動產生調整單） |
| 店家單據 | 出貨、退貨、銷貨（現金／刷卡／禮券）、調撥、訂單、異動、盤點 |
| 查詢報表 | 庫存、進銷存（期初／各單據／期末）、銷售分析（貨號／店家／品牌／月份／人員，含毛利）、採購與訂單追蹤、產品異動明細；全部可匯出 Excel（CSV） |
| 補貨調度 | 補貨建議（依銷售／依庫存量／依安全存量，倉庫不足時銷量高的店先配，一鍵產生出貨單）、轉貨建議（店與店之間多的調給缺的，一鍵產生調撥單）、追加採購／追裁建議（扣除已訂未進，一鍵產生採購單） |
| 應收帳款 | 月結（批發依出退貨、專櫃依銷售扣抽成）、收款沖帳、店家費用、應收餘額 |
| 系統維護 | 使用者與功能權限、公司設定（尺寸組）、庫存校帳、備份／回存（.sql.gz）、舊資料匯入 |

單據存檔、修改、刪除時，倉庫與店家庫存在同一個資料庫交易內自動加減；「庫存校帳」可由全部單據重算。

## 開發
```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q tests      # 核心邏輯＋畫面煙霧測試
.venv\Scripts\python main.py                 # 桌面版
.venv\Scripts\python run_web.py              # 網頁模式 http://127.0.0.1:8550
```

| 檔案 | 用途 |
|---|---|
| `zms/schema.sql` | 資料表結構 |
| `zms/doctypes.py` | 14 種單據與庫存影響 |
| `zms/services.py` | 業務邏輯 |
| `zms/importer.py`、`zms/dbf.py` | 舊 DBF 匯入 |
| `zms/server.py` | 內建 MariaDB 自動啟停 |
| `zms/ui/` | Flet 介面 |

舊系統解析報告與解出的原始碼：`..\analysis\`。
