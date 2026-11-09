"""資料助秘工具之服飾業進銷存系統 — 程式進入點。

桌面版：python main.py
網頁模式（測試／區網使用）：設定環境變數 ZMS_WEB_PORT=8550 再執行。
"""
import os

import flet as ft

from zms.ui.app import main

if __name__ == "__main__":
    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    port = os.environ.get("ZMS_WEB_PORT")
    if port:
        ft.run(main, view=ft.AppView.WEB_BROWSER, port=int(port), host="127.0.0.1", assets_dir=assets)
    else:
        ft.run(main, assets_dir=assets)
