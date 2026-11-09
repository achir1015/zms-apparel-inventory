@echo off
rem 資料助秘工具之服飾業進銷存系統（Windows 桌面版）
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo 第一次使用：建立 Python 環境中...
  python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" -X utf8 main.py
