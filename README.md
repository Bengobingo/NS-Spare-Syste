# NS Spare System

Flask 與 SQLite 備品管理工具，提供備品箱、設備庫存、領料紀錄與設備借用管理，支援繁體中文與英文介面。

## 功能

- 備品箱與箱內設備查找、照片預覽及領料。
- 後台管理備品箱與設備，支援入庫、盤點及低庫存篩選。
- 設備借用登記、歸還與逾期查找。
- 借用表與領取紀錄依目前篩選條件下載 Excel。
- 依箱別產生 QR Code。
- 桌機及手機響應式介面。

## Windows 本機安裝

建議使用 Python 3.12。於專案目錄開啟 PowerShell，執行下列指令。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_local.py
.\.venv\Scripts\python.exe app.py
```

`setup_local.py` 會要求輸入管理員帳號與密碼，並在本機建立 `local_settings.json`，儲存密碼雜湊與工作階段金鑰。再次執行可新增管理員或更新同一帳號的密碼。

啟動後開啟 [本機系統](http://127.0.0.1:5000)。資料庫與照片目錄會在首次執行時建立。

若需同時更換工作階段金鑰，執行 `setup_local.py --rotate-session-key`，將同時登出現有工作階段。

## Cloudflare Tunnel

需要使用既有的一鍵啟動流程時，可從 [Cloudflare 官方發行頁](https://github.com/cloudflare/cloudflared/releases) 取得 Windows 版執行檔，放在專案根目錄並命名為 `cloudflared.exe`，再執行 `2.start.bat`。該啟動檔會在找得到執行檔時建立 Tunnel。

## 本機資料

下列項目由 `.gitignore` 排除，請依需要自行備份。

- `local_settings.json`、環境變數檔及金鑰。
- SQLite 資料庫與 `static/uploads/` 設備照片。
- `.venv/`、執行日誌與本機交接紀錄。
- `cloudflared.exe` 等執行檔。

## 程式結構

| 路徑 | 用途 |
| --- | --- |
| `app.py` | Flask 路由、資料模型與操作流程 |
| `reporting.py` | Excel 匯出及篩選 |
| `setup_local.py` | 本機管理員設定 |
| `templates/` | 頁面樣板 |
| `static/ui.css`、`static/ui.js` | 共用介面樣式與中英文切換 |
| `static/admin.js` | 後台管理互動 |
| `static/circulation.js` | 借用及領取紀錄互動 |
| `static/vendor/` | 本機提供的 Bootstrap 與其授權檔 |
