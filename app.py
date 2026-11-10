"""Flask Web Application สำหรับ BJT DC Bias Calculator (Voltage-Divider Bias)."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from circuit import load_line_svg, schematic_svg, voltage_levels_svg
from dc_bias import calculate_dc_bias
from units import (
    AUTO,
    CURRENT_DISPLAY_CHOICES,
    RESISTANCE_CHOICES,
    VOLTAGE_CHOICES,
    VOLTAGE_DISPLAY_CHOICES,
    split_value,
    to_si,
)

app = Flask(__name__)


@app.context_processor
def inject_unit_choices():
    """ให้เทมเพลตเข้าถึงรายการหน่วยที่ผู้ใช้เลือกได้"""
    return {
        "resistance_choices": RESISTANCE_CHOICES,
        "voltage_choices": VOLTAGE_CHOICES,
        "voltage_display_choices": VOLTAGE_DISPLAY_CHOICES,
        "current_display_choices": CURRENT_DISPLAY_CHOICES,
    }

REQUIRED_FIELDS = ("vcc", "r1", "r2", "rc", "re", "beta")

# ชนิดข้อมูลและหน่วยเริ่มต้นของแต่ละช่อง (ช่องความต้านทานรับเป็น kΩ ตามแบบเดิม)
FIELD_UNITS = {
    "vcc": ("voltage", "V"),
    "vbe": ("voltage", "V"),
    "r1": ("resistance", "kΩ"),
    "r2": ("resistance", "kΩ"),
    "rc": ("resistance", "kΩ"),
    "re": ("resistance", "kΩ"),
}

# หน่วยที่อนุญาตให้เลือกได้ของแต่ละชนิด
ALLOWED_UNITS = {
    "voltage": VOLTAGE_CHOICES,
    "resistance": RESISTANCE_CHOICES,
}

# ค่าตัวอย่างสำหรับแสดงภาพวงจรตอนเปิดหน้าเว็บครั้งแรก
EXAMPLE = {
    "vcc": 12.0,
    "r1": 100_000.0,
    "r2": 22_000.0,
    "rc": 2_200.0,
    "re": 1_000.0,
    "beta": 100.0,
    "vbe": 0.70,
}

EXAMPLE_SELECTIONS = {
    "vcc_unit": "V",
    "vbe_unit": "V",
    "r1_unit": "kΩ",
    "r2_unit": "kΩ",
    "rc_unit": "kΩ",
    "re_unit": "kΩ",
    "voltage_display": AUTO,
    "current_display": AUTO,
}


def _clean(data, field: str) -> str:
    """อ่านค่าจาก form/JSON เป็นข้อความที่ตัดช่องว่างออก"""
    raw = data.get(field)
    return "" if raw is None else str(raw).strip()


def _unit_of(data, field: str) -> str:
    """อ่านหน่วยที่ผู้ใช้เลือก ถ้าไม่ถูกต้องให้ใช้ค่าเริ่มต้นของช่องนั้น"""
    kind, default_unit = FIELD_UNITS[field]
    unit = _clean(data, f"{field}_unit")
    if unit and unit in ALLOWED_UNITS[kind]:
        return unit
    return default_unit


def _parse_inputs(data) -> tuple[dict, dict]:
    """อ่านค่าอินพุตพร้อมหน่วย แล้วแปลงเป็นหน่วย SI (V, Ω)

    Returns:
        (params, selections)
        - params: ค่าคำนวณทั้งหมดในหน่วย SI
        - selections: หน่วยที่ผู้ใช้เลือก (ใช้แสดงผลและเตรียมฟอร์มกลับ)

    Raises:
        ValueError: เมื่อข้อมูลขาดหายหรือไม่ใช่ตัวเลข
    """
    values: dict[str, float] = {}
    missing: list[str] = []

    for field in REQUIRED_FIELDS:
        raw = _clean(data, field)
        if raw == "":
            missing.append(field.upper())
            continue
        try:
            values[field] = float(raw)
        except ValueError as exc:
            raise ValueError(f"ค่าของ {field.upper()} ต้องเป็นตัวเลข") from exc

    if missing:
        raise ValueError("กรุณากรอกค่าให้ครบ: " + ", ".join(missing))

    selections: dict[str, str] = {}

    # --- VCC ---
    selections["vcc_unit"] = _unit_of(data, "vcc")
    params_vcc = to_si(values["vcc"], "voltage", selections["vcc_unit"])

    # --- VBE ---
    vbe_raw = _clean(data, "vbe")
    try:
        vbe_value = float(vbe_raw) if vbe_raw else 0.70
    except ValueError as exc:
        raise ValueError("ค่าของ VBE ต้องเป็นตัวเลข") from exc
    selections["vbe_unit"] = _unit_of(data, "vbe")
    params_vbe = to_si(vbe_value, "voltage", selections["vbe_unit"])

    # --- ความต้านทานทั้ง 4 ตัว ---
    params_resistance = {}
    for field in ("r1", "r2", "rc", "re"):
        selections[f"{field}_unit"] = _unit_of(data, field)
        params_resistance[field] = to_si(
            values[field], "resistance", selections[f"{field}_unit"]
        )

    # --- หน่วยที่ใช้แสดงผล ---
    voltage_display = _clean(data, "voltage_display") or AUTO
    if voltage_display not in VOLTAGE_DISPLAY_CHOICES:
        voltage_display = AUTO
    current_display = _clean(data, "current_display") or AUTO
    if current_display not in CURRENT_DISPLAY_CHOICES:
        current_display = AUTO
    selections["voltage_display"] = voltage_display
    selections["current_display"] = current_display

    params = {
        "vcc": params_vcc,
        "vbe": params_vbe,
        "beta": values["beta"],
        **params_resistance,
    }
    return params, selections


def _safe_selections(data) -> dict:
    """อ่านหน่วยที่เลือกจากฟอร์มแบบไม่เข้มงวด ใช้ตอนแสดงฟอร์มครั้งถัดไป"""
    selections = dict(EXAMPLE_SELECTIONS)
    for field in FIELD_UNITS:
        unit = _clean(data, f"{field}_unit")
        kind, default_unit = FIELD_UNITS[field]
        if unit and unit in ALLOWED_UNITS[kind]:
            selections[f"{field}_unit"] = unit
    voltage_display = _clean(data, "voltage_display")
    if voltage_display in VOLTAGE_DISPLAY_CHOICES:
        selections["voltage_display"] = voltage_display
    current_display = _clean(data, "current_display")
    if current_display in CURRENT_DISPLAY_CHOICES:
        selections["current_display"] = current_display
    return selections


def _build_display(result: dict, selections: dict) -> dict:
    """สร้างข้อความผลลัพธ์พร้อมหน่วย ตามที่ผู้ใช้เลือกแสดงผล

    แต่ละรายการมีโครงสร้าง {"value": "1.942", "unit": "V", "text": "1.942 V"}
    """
    if not result or "error" in result:
        return {}

    vol = selections.get("voltage_display", AUTO)
    cur = selections.get("current_display", AUTO)

    display: dict[str, dict[str, str]] = {}

    def add(name: str, value: float, kind: str, preference: str) -> None:
        text, unit = split_value(value, kind, preference)
        display[name] = {"value": text, "unit": unit, "text": f"{text} {unit}"}

    add("vb", result["vb"], "voltage", vol)
    add("ve", result["ve"], "voltage", vol)
    add("vc", result["vc"], "voltage", vol)
    add("vce", result["vce"], "voltage", vol)
    add("vth", result["vth"], "voltage", vol)
    add("ib", result["ib"], "current", cur)
    add("ic", result["ic"], "current", cur)
    add("ie", result["ie"], "current", cur)
    add("rth", result["rth"], "resistance", AUTO)
    return display


def _build_figures(params: dict, result: dict | None, selections: dict) -> dict:
    """สร้าง SVG ทั้งหมด (ภาพวงจร, load line, ระดับแรงดัน) จากค่าที่คำนวณได้"""
    display_units = {
        "voltage": selections.get("voltage_display", AUTO),
        "current": selections.get("current_display", AUTO),
    }

    loadline = None
    levels = None

    if result and "error" not in result:
        schematic = schematic_svg(
            **params,
            vb=result["vb"],
            ve=result["ve"],
            vc=result["vc"],
            ic=result["ic"],
            display_units=display_units,
        )
        loadline = load_line_svg(
            vcc=params["vcc"],
            rc=params["rc"],
            re=params["re"],
            beta=params["beta"],
            ib=result["ib"],
            ic=result["ic"],
            vce=result["vce"],
            region=result["region"],
            display_units=display_units,
        )
        levels = voltage_levels_svg(
            vcc=params["vcc"],
            vc=result["vc"],
            vb=result["vb"],
            ve=result["ve"],
            vce=result["vce"],
            display_units=display_units,
        )
    else:
        schematic = schematic_svg(**params, display_units=display_units)

    return {"schematic": schematic, "loadline": loadline, "levels": levels}


@app.route("/", methods=["GET"])
def index():
    """แสดงหน้าฟอร์มรับค่าอินพุต พร้อมภาพวงจรตัวอย่าง"""
    figures = _build_figures(EXAMPLE, None, EXAMPLE_SELECTIONS)
    return render_template(
        "index.html",
        result=None,
        display={},
        form={},
        selections=EXAMPLE_SELECTIONS,
        **figures,
    )


@app.route("/", methods=["POST"])
def calculate():
    """รับค่าจากฟอร์ม คำนวณ DC Bias แล้วแสดงผลพร้อมภาพประกอบในหน้าเดิม"""
    try:
        params, selections = _parse_inputs(request.form)
    except ValueError as exc:
        figures = _build_figures(EXAMPLE, None, EXAMPLE_SELECTIONS)
        return render_template(
            "index.html",
            result={"error": str(exc), "region": "Error"},
            display={},
            form=request.form,
            selections=_safe_selections(request.form),
            **figures,
        )

    result = calculate_dc_bias(**params)
    display = _build_display(result, selections)
    figures = _build_figures(params, result, selections)
    return render_template(
        "index.html",
        result=result,
        display=display,
        form=request.form,
        selections=selections,
        **figures,
    )


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    """API แบบ JSON สำหรับทดสอบอัตโนมัติ.

    ค่าความต้านทานรับเป็น kΩ โดยค่าเริ่มต้น (ถ้าไม่ส่งหน่วยมา) และรับหน่วยอื่นได้
    เช่น {"r1": 100, "r1_unit": "kΩ"} หรือ {"r1": 100000, "r1_unit": "Ω"}
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "ต้องส่ง JSON object", "region": "Error"}), 400

    try:
        params, selections = _parse_inputs(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc), "region": "Error"}), 400

    result = calculate_dc_bias(**params)
    payload_out = dict(result)
    payload_out["units"] = selections
    payload_out["display"] = _build_display(result, selections)
    return jsonify(payload_out)


if __name__ == "__main__":
    print("=" * 50)
    print("Starting BJT DC Bias Web App...")
    print("=" * 50)
    print("Open: http://127.0.0.1:5000/")
    print("=" * 50)
    app.run(debug=True, host="127.0.0.1", port=5000)
