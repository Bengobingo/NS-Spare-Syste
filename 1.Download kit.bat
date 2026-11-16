@echo off
chcp 65001 >nul
echo 正在建立 Python 虛擬環境與安裝依賴套件...
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
echo.
echo ========================================
echo 環境安裝完成！請點擊 [2.start.bat] 啟動。
echo ========================================
pause