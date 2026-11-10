"""Unit conversion and formatting helpers for the BJT DC Bias web app.

หลักการ: ภายในระบบคำนวณทุกอย่างอยู่ในหน่วย SI (V, Ω, A) เสมอ
โมดูลนี้มีหน้าที่แปลงค่าจากหน่วยที่ผู้ใช้เลือกเข้ามา และจัดรูปแบบผลลัพธ์
ให้แสดงผลตามหน่วยที่เลือกได้
"""

from __future__ import annotations

# --- ตารางแปลงหน่วย (ค่าคูณเพื่อแปลง SI -> หน่วยที่แสดง) ---
RESISTANCE_UNITS: dict[str, float] = {
    "Ω": 1.0,
    "kΩ": 1e3,
    "MΩ": 1e6,
}

VOLTAGE_UNITS: dict[str, float] = {
    "V": 1.0,
    "mV": 1e-3,
}

CURRENT_UNITS: dict[str, float] = {
    "A": 1.0,
    "mA": 1e-3,
    "µA": 1e-6,
}

# ตัวเลือกหน่วยที่ให้ผู้ใช้เลือกได้ในหน้าเว็บ
RESISTANCE_CHOICES = ("Ω", "kΩ", "MΩ")
VOLTAGE_CHOICES = ("V", "mV")
CURRENT_DISPLAY_CHOICES = ("auto", "A", "mA", "µA")
VOLTAGE_DISPLAY_CHOICES = ("auto", "V", "mV")

AUTO = "auto"

_UNIT_TABLES = {
    "voltage": VOLTAGE_UNITS,
    "current": CURRENT_UNITS,
    "resistance": RESISTANCE_UNITS,
}

# ลำดับหน่วยจากใหญ่ไปเล็ก สำหรับเลือกหน่วยอัตโนมัติ
_AUTO_ORDER = {
    "voltage": ("V", "mV"),
    "current": ("A", "mA", "µA"),
    "resistance": ("MΩ", "kΩ", "Ω"),
}

# จำนวนทศนิยมที่ต้องการเมื่อแสดงผลแบบอัตโนมัติ
_AUTO_DECIMALS = {
    "voltage": 3,
    "current": 2,
    "resistance": 3,
}


def to_si(value: float, kind: str, unit: str) -> float:
    """แปลงค่าจากหน่วยที่ผู้ใช้เลือกเป็นหน่วย SI

    Args:
        value: ค่าตัวเลขตามหน่วยที่ผู้ใช้กรอก
        kind: "voltage" | "current" | "resistance"
        unit: สัญลักษณ์หน่วย เช่น "kΩ", "mV"

    Returns:
        ค่าในหน่วย SI (V / A / Ω)
    """
    table = _UNIT_TABLES[kind]
    factor = table.get(unit)
    if factor is None:
        raise ValueError(f"ไม่รู้จักหน่วย '{unit}' สำหรับ {kind}")
    return value * factor


def auto_unit(value: float, kind: str) -> str:
    """เลือกหน่วยที่เหมาะสมที่สุดให้ค่าหนึ่ง ๆ (เช่น 0.0012 A -> mA)"""
    table = _UNIT_TABLES[kind]
    magnitude = abs(value)
    for unit in _AUTO_ORDER[kind]:
        if magnitude >= table[unit] or unit == _AUTO_ORDER[kind][-1]:
            return unit
    return _AUTO_ORDER[kind][-1]


def split_value(value: float, kind: str, preference: str = AUTO) -> tuple[str, str]:
    """จัดรูปแบบค่าพร้อมหน่วย โดยแยกส่วนตัวเลขกับหน่วยออกจากกัน

    Returns:
        (ข้อความตัวเลข, สัญลักษณ์หน่วย) เช่น ("1.23", "mA")
    """
    table = _UNIT_TABLES[kind]

    if preference and preference != AUTO and preference in table:
        unit = preference
    else:
        unit = auto_unit(value, kind)

    scaled = value / table[unit]
    decimals = _AUTO_DECIMALS[kind] if (preference in (AUTO, "", None)) else 3

    text = f"{scaled:.{decimals}f}".rstrip("0").rstrip(".")
    if text in ("", "-"):
        text = "0"
    return text, unit


def format_value(value: float, kind: str, preference: str = AUTO) -> str:
    """จัดรูปแบบค่าพร้อมหน่วยตามที่เลือก

    Args:
        value: ค่าในหน่วย SI
        kind: "voltage" | "current" | "resistance"
        preference: "auto" หรือสัญลักษณ์หน่วยที่ต้องการให้ใช้

    Returns:
        ข้อความ เช่น "1.942 V", "1.23 mA", "100 kΩ"
    """
    text, unit = split_value(value, kind, preference)
    return f"{text} {unit}"


def format_number(value: float, decimals: int = 3) -> str:
    """จัดรูปแบบตัวเลขล้วน (ไม่มีหน่วย) พร้อมตัดเลขศูนย์ท้ายที่ไม่จำเป็น"""
    text = f"{value:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
