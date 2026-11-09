"""以網頁模式模擬手機版（測試用）：http://127.0.0.1:8551
資料夾 data_mobile/ 存手機版設定（連線到電腦版的資料庫）。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["ZMS_MOBILE"] = "1"
os.environ["ZMS_DATA_DIR"] = os.path.join(HERE, "data_mobile")
os.environ["ZMS_WEB_PORT"] = "8551"
sys.path.insert(0, HERE)
os.chdir(HERE)

import run_web  # noqa: E402,F401
import flet as ft  # noqa: E402

from zms.ui.app import main  # noqa: E402

if __name__ == "__main__":
    os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8551, host="127.0.0.1", assets_dir=os.path.join(HERE, "assets"))
