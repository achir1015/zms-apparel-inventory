"""單據種類定義（對照舊系統 P_xxx 主檔／明細檔）。

effects：每筆明細對庫存的影響，(位置欄位, 正負號)。
  位置欄位 wh_no/wh_no2 → 倉庫；sh_no/sh_no2 → 店家。
  正負號 0 代表數量本身帶正負（調整、異動）。
price：明細預設單價來源 'cost' 成本 / 'sale' 依店家售價等級。
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocType:
    code: str
    name: str
    group: str                 # 倉庫 / 店家
    old: str                   # 舊表
    fields: tuple              # 表頭要填的欄位
    effects: tuple = ()
    price: str = "sale"
    signed: bool = False       # 數量可為負
    labels: dict = field(default_factory=dict)


H = dict(wh_no="倉庫", wh_no2="調入倉庫", sh_no="店家", sh_no2="調入店家", ma_no="廠商",
         per_no="經手人", reason="原因", ref_no="參考單號", bill_no="發票號碼", discount="折數%")

DOC_TYPES = [
    DocType("PI", "倉庫進貨", "倉庫", "P_PURI", ("wh_no", "ma_no", "ref_no", "bill_no"), (("wh_no", +1),), "cost",
            labels={"ref_no": "採購單號"}),
    DocType("PO", "倉庫退廠", "倉庫", "P_PURO", ("wh_no", "ma_no", "bill_no"), (("wh_no", -1),), "cost"),
    DocType("CH", "倉庫調撥", "倉庫", "P_CHANG", ("wh_no", "wh_no2"), (("wh_no", -1), ("wh_no2", +1)), "cost",
            labels={"wh_no": "調出倉庫"}),
    DocType("NU", "倉庫壞品", "倉庫", "P_NUL", ("wh_no", "reason"), (("wh_no", -1),), "cost"),
    DocType("GE", "公司採購", "倉庫", "P_GET", ("wh_no", "ma_no"), (), "cost"),
    DocType("MA", "公司調整", "倉庫", "P_MATATE", ("wh_no", "reason"), (("wh_no", 0),), "cost", signed=True),
    DocType("ST", "公司盤點", "倉庫", "P_STK", ("wh_no",), (), "cost"),
    DocType("GR", "店家出貨", "店家", "P_GRES", ("wh_no", "sh_no", "per_no", "discount", "ref_no"),
            (("wh_no", -1), ("sh_no", +1)), labels={"ref_no": "訂單號碼"}),
    DocType("DR", "店家退貨", "店家", "P_DREW", ("sh_no", "wh_no", "per_no", "discount"),
            (("sh_no", -1), ("wh_no", +1)), labels={"wh_no": "退回倉庫"}),
    DocType("TA", "店家銷貨", "店家", "P_TAKE", ("sh_no", "per_no"), (("sh_no", -1),), labels={"per_no": "專櫃人員"}),
    DocType("MO", "店家調撥", "店家", "P_MOVE", ("sh_no", "sh_no2", "per_no"), (("sh_no", -1), ("sh_no2", +1)),
            labels={"sh_no": "調出店家"}),
    DocType("OR", "店家訂單", "店家", "P_ORDER", ("sh_no", "per_no", "discount"), ()),
    DocType("TR", "店家異動", "店家", "P_TRANS", ("sh_no", "reason"), (("sh_no", 0),), signed=True),
    DocType("CK", "店家盤點", "店家", "P_CHECK", ("sh_no", "per_no"), ()),
]

BY_CODE = {d.code: d for d in DOC_TYPES}


def label(dt: DocType, f: str) -> str:
    return dt.labels.get(f, H.get(f, f))
