"""以網頁模式啟動（測試用）：http://127.0.0.1:8550"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import flet as ft  # noqa: E402

from zms.ui.app import main  # noqa: E402

if __name__ == "__main__":
    os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")  # 只開伺服器，不自動開使用者的瀏覽器
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=int(os.environ.get("ZMS_WEB_PORT", "8550")), host="127.0.0.1",
           assets_dir=os.path.join(HERE, "assets"))
