"""介面共用元件。"""
import csv
import datetime as _dt
import os
from decimal import Decimal

import flet as ft

from .. import dates
from ..services import BizError

PRIMARY = "#1F5FA8"


def fmt(v, typ=None):
    if v is None:
        return ""
    if isinstance(v, (_dt.date, _dt.datetime)) and not isinstance(v, _dt.datetime):
        return dates.roc(v)
    if isinstance(v, _dt.datetime):
        return dates.roc(v.date()) + v.strftime(" %H:%M")
    if isinstance(v, Decimal):
        if v == v.to_integral_value():
            return "{:,}".format(int(v))
        return "{:,.2f}".format(v)
    if isinstance(v, float):
        return "{:,.2f}".format(v)
    if isinstance(v, int) and typ == "n":
        return "{:,}".format(v)
    return str(v)


class Ctx:
    """傳給各畫面：page、service、提示方法。"""

    def __init__(self, page: ft.Page, svc):
        self.page = page
        self.svc = svc

    def toast(self, msg, error=False):
        self.page.show_dialog(ft.SnackBar(ft.Text(msg, color=ft.Colors.WHITE),
                                          bgcolor=ft.Colors.RED_700 if error else ft.Colors.GREEN_700,
                                          duration=3500 if error else 2000))

    def guard(self, fn, *a, ok=None, **kw):
        """執行並把錯誤顯示出來；成功回傳結果（結果為 None 時回傳 True），失敗回傳 None。"""
        try:
            r = fn(*a, **kw)
            if ok:
                self.toast(ok)
            return True if r is None else r
        except BizError as e:
            self.toast(str(e), True)
        except ValueError as e:
            self.toast(str(e), True)
        except Exception as e:  # 未預期錯誤也要讓使用者看到
            self.toast("發生錯誤：%s" % e, True)
        return None

    def confirm(self, title, msg, on_yes, yes_text="確定"):
        def yes(e):
            self.page.pop_dialog()
            on_yes()

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text(title), content=ft.Text(msg),
            actions=[ft.TextButton("取消", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton(yes_text, on_click=yes, bgcolor=ft.Colors.RED_600)]))


def tf(label, value="", width=None, **kw):
    return ft.TextField(label=label, value="" if value is None else str(value), width=width, dense=True, **kw)


def dd(label, options, value=None, width=None, on_select=None, blank=True, **kw):
    opts = ([ft.DropdownOption(key="", text="（全部）" if blank == "all" else "")] if blank else [])
    opts += [ft.DropdownOption(key=str(k), text=t) for k, t in options]
    return ft.Dropdown(label=label, options=opts, value=None if value in (None, "") and not blank else str(value or ""),
                       width=width, dense=True, on_select=on_select, enable_filter=True, editable=True,
                       menu_height=360, **kw)


def date_field(label="日期", value=None, width=130):
    return tf(label, dates.roc(value or dates.today()), width=width, hint_text="115/11/09")


def section(title, *controls):
    return ft.Column([ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=PRIMARY), *controls],
                     spacing=10, expand=True)


class Grid(ft.Column):
    """可捲動的資料表：columns=[(key, 標題, 型別, 寬度)]，點列觸發 on_pick(row)。"""

    def __init__(self, columns, on_pick=None, height=None, total_keys=()):
        self.columns_def = columns
        self.on_pick = on_pick
        self.total_keys = total_keys
        self.rows_data = []
        self.table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(c[1], weight=ft.FontWeight.BOLD), numeric=c[2] == "n") for c in columns],
            rows=[], heading_row_height=36, data_row_min_height=32, data_row_max_height=40, column_spacing=18,
            heading_row_color=ft.Colors.BLUE_50, border=ft.Border.all(1, ft.Colors.GREY_300),
            horizontal_lines=ft.BorderSide(0.5, ft.Colors.GREY_200), show_checkbox_column=False)
        self.info = ft.Text("", size=12, color=ft.Colors.GREY_700)
        inner = ft.Column([ft.Row([self.table], scroll=ft.ScrollMode.AUTO)], scroll=ft.ScrollMode.AUTO, expand=True)
        super().__init__([inner, self.info], expand=height is None, height=height, spacing=4)

    def set_rows(self, rows):
        self.rows_data = rows
        out = []
        for r in rows:
            cells = []
            for key, title, typ, width in self.columns_def:
                v = r.get(key)
                if typ == "b":
                    s = "✔" if v else ""
                else:
                    s = fmt(v, typ)
                cells.append(ft.DataCell(ft.Text(s, width=width, no_wrap=True, max_lines=1,
                                                 text_align=ft.TextAlign.RIGHT if typ == "n" else ft.TextAlign.LEFT,
                                                 tooltip=s if len(s) > 12 else None)))
            out.append(ft.DataRow(cells=cells, on_select_change=(lambda e, rr=r: self.on_pick(rr)) if self.on_pick else None))
        self.table.rows = out
        info = "共 %d 筆" % len(rows)
        for k in self.total_keys:
            tot = sum(Decimal(str(r.get(k) or 0)) for r in rows)
            title = next(c[1] for c in self.columns_def if c[0] == k)
            info += "　%s合計 %s" % (title, fmt(tot))
        self.info.value = info

    def export_csv(self, path):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow([c[1] for c in self.columns_def])
            for r in self.rows_data:
                w.writerow([fmt(r.get(c[0]), c[2]).replace(",", "") if c[2] == "n" else fmt(r.get(c[0]), c[2])
                            for c in self.columns_def])
        return path


async def export_grid(ctx, grid, name):
    if not grid.rows_data:
        ctx.toast("沒有資料可匯出", True)
        return
    path = await ft.FilePicker().save_file(dialog_title="匯出 Excel（CSV）",
                                           file_name="%s_%s.csv" % (name, dates.today().strftime("%Y%m%d")),
                                           allowed_extensions=["csv"])
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"
    grid.export_csv(path)
    ctx.toast("已匯出：%s" % os.path.basename(path))


def export_button(ctx, grid, name):
    async def go(e):
        await export_grid(ctx, grid, name)
    return ft.OutlinedButton("匯出 Excel", icon=ft.Icons.DOWNLOAD, on_click=go)
