@echo off
chcp 65001 >nul
echo ========================================================
echo  正在啟動 MiTAC 備品管理系統 (含 Cloudflare 穿透)...
echo ========================================================

:: 1. 刪除舊的 log 檔案，避免讀取到上次的過期網址
if exist tunnel.log del /f /q tunnel.log

:: 2. 啟動 Cloudflare 穿透，並將即時網址 Log 寫入 tunnel.log
echo [1/2] 正在建立 Cloudflare 安全通道...
if exist cloudflared.exe (
    start "Cloudflare Tunnel" cmd /c "cloudflared.exe tunnel --protocol http2 --url http://127.0.0.1:5000 > tunnel.log 2>&1"
)

:: 等待 3 秒讓 Cloudflare 生成網址
timeout /t 3 >nul

:: 3. 啟動 Python 後端系統
echo [2/2] 正在啟動 Python Flask 伺服器...
start "Spare Parts Server" cmd /k "call .venv\Scripts\activate && python app.py"

echo ========================================================
echo  系統已成功啟動！
echo  本機網址：http://127.0.0.1:5000
echo ========================================================
timeout /t 2 >nul
start http://127.0.0.1:5000