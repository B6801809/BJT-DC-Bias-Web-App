"""Flask Web Application สำหรับ BJT DC Bias Calculator (Voltage-Divider Bias)."""

from __future__ import annotations

import re

from flask import Flask, jsonify, render_template, request

import spice_engine
import spice_plots
from circuit import (
    emitter_schematic_svg,
    fixed_schematic_svg,
    load_line_svg,
    schematic_svg,
    voltage_levels_svg,
)
from dc_bias import calculate_dc_bias, calculate_emitter_bias, calculate_fixed_bias
from units import (
    AUTO,
    CURRENT_DISPLAY_CHOICES,
    FREQUENCY_CHOICES,
    RESISTANCE_CHOICES,
    VOLTAGE_CHOICES,
    VOLTAGE_DISPLAY_CHOICES,
    split_value,
    to_si,
)

app = Flask(__name__)

# โหมดที่รองรับ — ถ้าไม่ส่ง mode มาจะใช้ divider เพื่อคงผล Lab 2 เดิม
MODES = ("divider", "fixed", "emitter")
MODE_LABELS = {
    "divider": "Voltage Divider Bias",
    "fixed": "Fixed Bias",
    "emitter": "Emitter Bias",
}
MODE_FIELDS = {
    "divider": ("vcc", "r1", "r2", "rc", "re", "beta"),
    "fixed": ("vcc", "rb", "rc", "beta"),
    "emitter": ("vcc", "rb", "rc", "re", "beta"),
}


@app.context_processor
def inject_unit_choices():
    """ให้เทมเพลตเข้าถึงรายการหน่วยที่ผู้ใช้เลือกได้"""
    return {
        "resistance_choices": RESISTANCE_CHOICES,
        "voltage_choices": VOLTAGE_CHOICES,
        "voltage_display_choices": VOLTAGE_DISPLAY_CHOICES,
        "current_display_choices": CURRENT_DISPLAY_CHOICES,
        "frequency_choices": FREQUENCY_CHOICES,
    }

# ชนิดข้อมูลและหน่วยเริ่มต้นของแต่ละช่อง
# RB เริ่มต้นเป็น MΩ เพื่อให้ A2 กรอก "1 MΩ" ได้ตรงตามใบงาน
FIELD_UNITS = {
    "vcc": ("voltage", "V"),
    "vbe": ("voltage", "V"),
    "rb": ("resistance", "MΩ"),
    "r1": ("resistance", "kΩ"),
    "r2": ("resistance", "kΩ"),
    "rc": ("resistance", "kΩ"),
    "re": ("resistance", "kΩ"),
}

# หน่วยที่อนุญาตให้เลือกได้ของแต่ละชนิด
ALLOWED_UNITS = {
    "voltage": VOLTAGE_CHOICES,
    "resistance": RESISTANCE_CHOICES,
    "frequency": FREQUENCY_CHOICES,
}

SPICE_INSTALL_HINT = (
    "ติดตั้ง ngspice แล้วตั้งค่า environment variable NGSPICE_BIN ให้ชี้ไปที่ ngspice.exe "
    "หรือเพิ่มโฟลเดอร์ Spice64\\bin ลง PATH แล้วรีสตาร์ทแอป"
)


def _spice_engine_label(path: str | None) -> str | None:
    """เดารุ่นของ ngspice จากพาธที่ติดตั้ง เช่น ...\\ngspice-47\\... -> ngspice-47"""
    if not path:
        return None
    match = re.search(r"ngspice[-_ ]?(\d+)", path, re.IGNORECASE)
    return f"ngspice-{match.group(1)}" if match else "ngspice"


def _spice_entry(value: float, kind: str, preference: str) -> dict:
    text, unit = split_value(value, kind, preference)
    return {"value": text, "unit": unit, "text": f"{text} {unit}"}


def _spice_values(result: dict, selections: dict) -> dict:
    """จัดรูปแบบผล .op ให้เหมือนผล Analytical เพื่อเทียบกันได้ตรง ๆ"""
    vol = selections.get("voltage_display", AUTO)
    cur = selections.get("current_display", AUTO)
    values = {}
    for key in ("vb", "ve", "vc", "vce"):
        values[key] = _spice_entry(result[key], "voltage", vol)
    for key in ("ib", "ic", "ie"):
        values[key] = _spice_entry(result[key], "current", cur)
    return values


def _spice_summary(analysis: str, data: dict, amplitude_v: float, frequency_hz: float) -> list[dict]:
    """สรุปตัวเลขสำคัญของแต่ละ analysis เป็นข้อความพร้อมหน่วย"""
    if analysis == "ac":
        frequencies = data["frequency"]
        gains = data["gain_db"]
        phases = data["phase_deg"]
        index = min(range(len(frequencies)), key=lambda i: abs(frequencies[i] - frequency_hz))
        return [
            {"label": "จำนวนจุด", "text": f"{len(frequencies)} จุด"},
            {
                "label": "ช่วงความถี่",
                "text": (
                    f"{_spice_entry(frequencies[0], 'frequency', AUTO)['text']} – "
                    f"{_spice_entry(frequencies[-1], 'frequency', AUTO)['text']}"
                ),
            },
            {"label": f"Gain @ {_spice_entry(frequency_hz, 'frequency', AUTO)['text']}", "text": f"{gains[index]:.2f} dB"},
            {"label": f"Phase @ {_spice_entry(frequency_hz, 'frequency', AUTO)['text']}", "text": f"{phases[index]:.1f}°"},
            {"label": "Gain สูงสุด", "text": f"{max(gains):.2f} dB"},
        ]

    if analysis == "tran":
        vin = data["vin"]
        vout = data["vout"]
        vin_pp = max(vin) - min(vin)
        vout_pp = max(vout) - min(vout)
        gain = vout_pp / vin_pp if vin_pp > 0 else 0.0
        return [
            {"label": "จำนวนจุด", "text": f"{len(data['time'])} จุด"},
            {"label": "ช่วงเวลา", "text": f"{data['time'][0] * 1000:.3g} – {data['time'][-1] * 1000:.3g} ms"},
            {"label": "Vin peak-peak", "text": _spice_entry(vin_pp, "voltage", AUTO)["text"]},
            {"label": "Vout peak-peak", "text": _spice_entry(vout_pp, "voltage", AUTO)["text"]},
            {"label": "|Vout/Vin| (peak-peak)", "text": f"{gain:.3f} ×"},
            {"label": "ความถี่ SIN", "text": _spice_entry(frequency_hz, "frequency", AUTO)["text"]},
        ]

    return [
        {"label": "จำนวนจุด", "text": f"{len(data['ic'])} ค่า"},
        {"label": "Amplitude ที่ตั้ง", "text": _spice_entry(amplitude_v, "voltage", AUTO)["text"]},
    ]


def _spice_measure(payload: dict, field: str, kind: str, default_si: float, default_unit: str) -> float:
    """อ่านค่าที่มีหน่วยจาก payload แล้วคืนค่า SI (V / Hz)"""
    raw = _clean(payload, field)
    if not raw:
        return default_si

    unit = _clean(payload, f"{field}_unit") or default_unit
    if unit not in ALLOWED_UNITS[kind]:
        raise ValueError(f"หน่วยของ {field.upper()} ไม่ถูกต้อง: {unit}")

    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"ค่าของ {field.upper()} ต้องเป็นตัวเลข") from exc

    try:
        return to_si(value, kind, unit)
    except ValueError as exc:
        raise ValueError(f"หน่วยของ {field.upper()} ไม่ถูกต้อง: {unit}") from exc


def _spice_fill_empty_fields(payload: dict) -> dict:
    """ช่องฟอร์มที่ส่งมาเป็นข้อความว่างให้ใช้ค่าวงจรอ้างอิง Lab 04

    เฉพาะ field ที่มี key อยู่ใน payload เท่านั้น — การขาด field เลยยังถือว่า
    ส่งข้อมูลไม่ครบและต้องแจ้ง error เหมือนเดิม
    """
    filled = dict(payload)
    defaults = spice_engine.reference_params()

    for field in ("vcc", "r1", "r2", "rc", "re", "beta"):
        if field not in filled or _clean(filled, field):
            continue
        if field == "beta":
            filled[field] = f"{defaults['beta']:g}"
            continue

        kind, fallback_unit = FIELD_UNITS[field]
        unit = _clean(filled, f"{field}_unit") or fallback_unit
        if unit not in ALLOWED_UNITS[kind]:
            unit = fallback_unit
        text, _unit = split_value(defaults[field], kind, unit)
        filled[field] = text

    return filled


def _spice_request(payload: dict) -> tuple[str, dict, dict, float, float]:
    """แยก payload วงจร + แปลงค่า amplitude/frequency มาเป็น SI กับค่าที่แสดงผล"""
    analysis = payload.get("analysis", "op")
    if analysis not in spice_engine.ANALYSES:
        raise ValueError(
            f"ไม่รู้จักวิธีวิเคราะห์ '{analysis}' (รองรับ: {', '.join(spice_engine.ANALYSES)})"
        )

    params, selections, _mode = _parse_inputs(_spice_fill_empty_fields(payload))

    amplitude_v = _spice_measure(
        payload, "amplitude", "voltage", spice_engine.DEFAULT_AMPLITUDE_V, "mV"
    )
    frequency_hz = _spice_measure(
        payload, "frequency", "frequency", spice_engine.DEFAULT_FREQUENCY_HZ, "Hz"
    )

    if not 0 < amplitude_v <= 1.0:
        raise ValueError("Amplitude ต้องอยู่ระหว่าง 0 ถึง 1 V peak")
    if not 0 < frequency_hz <= 1e9:
        raise ValueError("Frequency ต้องอยู่ระหว่าง 0 ถึง 1 GHz")

    return analysis, params, selections, amplitude_v, frequency_hz

# ค่าตัวอย่างสำหรับแสดงภาพวงจรตอนเปิดหน้าเว็บครั้งแรก
EXAMPLE = {
    "vcc": 12.0,
    "rb": 1_000_000.0,
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
    "rb_unit": "MΩ",
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


def _mode_of(value: str | None) -> str:
    """อ่านโหมดแบบไม่เข้มงวด ใช้ตอนแสดงฟอร์ม (ค่าไม่รู้จัก → divider)"""
    return value if value in MODES else "divider"


def _mode_from(data) -> str:
    """อ่านโหมดจากฟอร์ม/JSON โหมดที่ไม่รู้จักต้องแจ้ง error ไม่เดาเป็น Divider"""
    raw = _clean(data, "mode")
    if not raw:
        return "divider"
    if raw not in MODES:
        raise ValueError(f"ไม่รู้จักโหมด '{raw}'")
    return raw


def _example_params(mode: str) -> dict:
    """ค่าตัวอย่างสำหรับแสดงภาพวงจรของโหมดที่เลือก"""
    fields = MODE_FIELDS[mode] + ("vbe",)
    return {field: EXAMPLE[field] for field in fields}


def _calculate(mode: str, params: dict) -> dict:
    """เลือกฟังก์ชันคำนวณตามโหมดที่ส่งมาจากฟอร์ม"""
    if mode == "fixed":
        return calculate_fixed_bias(**params)
    if mode == "emitter":
        return calculate_emitter_bias(**params)
    return calculate_dc_bias(**params)


def _parse_inputs(data) -> tuple[dict, dict, str]:
    """อ่านค่าอินพุตตามโหมด แล้วแปลงเป็นหน่วย SI (V, Ω)

    Returns:
        (params, selections, mode)
        - params: ค่าที่โหมดนั้นต้องใช้ทั้งหมดในหน่วย SI
        - selections: หน่วยที่ผู้ใช้เลือก (ใช้แสดงผลและเตรียมฟอร์มกลับ)

    Raises:
        ValueError: เมื่อโหมดไม่รู้จัก ข้อมูลขาดหาย หรือไม่ใช่ตัวเลข
    """
    mode = _mode_from(data)
    values: dict[str, float] = {}
    missing: list[str] = []

    for field in MODE_FIELDS[mode]:
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
    params = {"vcc": to_si(values["vcc"], "voltage", selections["vcc_unit"])}

    # --- VBE (ไม่บังคับ ตรงตาม Lab 2) ---
    vbe_raw = _clean(data, "vbe")
    try:
        vbe_value = float(vbe_raw) if vbe_raw else 0.70
    except ValueError as exc:
        raise ValueError("ค่าของ VBE ต้องเป็นตัวเลข") from exc
    selections["vbe_unit"] = _unit_of(data, "vbe")
    params["vbe"] = to_si(vbe_value, "voltage", selections["vbe_unit"])

    # --- ความต้านทานที่โหมดนี้ใช้จริง ---
    for field in ("rb", "r1", "r2", "rc", "re"):
        if field in values:
            selections[f"{field}_unit"] = _unit_of(data, field)
            params[field] = to_si(values[field], "resistance", selections[f"{field}_unit"])

    params["beta"] = values["beta"]

    # --- หน่วยที่ใช้แสดงผล ---
    voltage_display = _clean(data, "voltage_display") or AUTO
    if voltage_display not in VOLTAGE_DISPLAY_CHOICES:
        voltage_display = AUTO
    current_display = _clean(data, "current_display") or AUTO
    if current_display not in CURRENT_DISPLAY_CHOICES:
        current_display = AUTO
    selections["voltage_display"] = voltage_display
    selections["current_display"] = current_display

    return params, selections, mode


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
    if "vth" in result:
        add("vth", result["vth"], "voltage", vol)
    add("ib", result["ib"], "current", cur)
    add("ic", result["ic"], "current", cur)
    add("ie", result["ie"], "current", cur)
    if "rth" in result:
        add("rth", result["rth"], "resistance", AUTO)
    return display


def _build_figures(
    params: dict, result: dict | None, selections: dict, mode: str = "divider"
) -> dict:
    """สร้าง SVG ทั้งหมด (ภาพวงจร, load line, ระดับแรงดัน) จากค่าที่คำนวณได้"""
    display_units = {
        "voltage": selections.get("voltage_display", AUTO),
        "current": selections.get("current_display", AUTO),
    }

    loadline = None
    levels = None
    measured = result if result and "error" not in result else None

    shown = (
        {
            "vb": measured["vb"],
            "ve": measured["ve"],
            "vc": measured["vc"],
            "ic": measured["ic"],
        }
        if measured
        else {}
    )
    if mode == "fixed":
        schematic = fixed_schematic_svg(**params, **shown, display_units=display_units)
    elif mode == "emitter":
        schematic = emitter_schematic_svg(**params, **shown, display_units=display_units)
    else:
        schematic = schematic_svg(**params, **shown, display_units=display_units)

    if measured:
        loadline = load_line_svg(
            vcc=params["vcc"],
            rc=params["rc"],
            re=params.get("re", 0.0),
            beta=params["beta"],
            ib=measured["ib"],
            ic=measured["ic"],
            vce=measured["vce"],
            region=measured["region"],
            display_units=display_units,
            mode=mode,
        )
        levels = voltage_levels_svg(
            vcc=params["vcc"],
            vc=measured["vc"],
            vb=measured["vb"],
            ve=measured["ve"],
            vce=measured["vce"],
            display_units=display_units,
        )

    return {"schematic": schematic, "loadline": loadline, "levels": levels}


@app.route("/", methods=["GET"])
def index():
    """แสดงหน้าฟอร์มรับค่าอินพุต พร้อมภาพวงจรตัวอย่างของโหมดที่เลือก"""
    mode = _mode_of(request.args.get("mode"))
    figures = _build_figures(_example_params(mode), None, EXAMPLE_SELECTIONS, mode)
    return render_template(
        "index.html",
        mode=mode,
        mode_label=MODE_LABELS[mode],
        result=None,
        display={},
        form={},
        selections=EXAMPLE_SELECTIONS,
        **figures,
    )


@app.route("/", methods=["POST"])
def calculate():
    """รับค่าจากฟอร์ม เลือกฟังก์ชันตามโหมด แล้วแสดงผลพร้อมภาพประกอบ"""
    try:
        params, selections, mode = _parse_inputs(request.form)
    except ValueError as exc:
        mode = _mode_of(_clean(request.form, "mode"))
        figures = _build_figures(_example_params(mode), None, EXAMPLE_SELECTIONS, mode)
        return render_template(
            "index.html",
            mode=mode,
            mode_label=MODE_LABELS[mode],
            result={"error": str(exc), "region": "Error"},
            display={},
            form=request.form,
            selections=_safe_selections(request.form),
            **figures,
        )

    result = _calculate(mode, params)
    display = _build_display(result, selections)
    figures = _build_figures(params, result, selections, mode)
    return render_template(
        "index.html",
        mode=mode,
        mode_label=MODE_LABELS[mode],
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
        params, selections, mode = _parse_inputs(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc), "region": "Error"}), 400

    result = _calculate(mode, params)
    payload_out = dict(result)
    payload_out["mode"] = mode
    payload_out["units"] = selections
    payload_out["display"] = _build_display(result, selections)
    return jsonify(payload_out)


@app.route("/api/spice/status", methods=["GET"])
def api_spice_status():
    """รายงานสถานะ ngspice, โมเดล BJT และค่าอ้างอิงของวงจร Lab 04"""
    exe = spice_engine.find_ngspice()
    model = spice_engine.DEFAULT_MODEL
    model_definition = (
        f"NPN(BF={model['bf']:g} IS={model['is']:g} VAF={model['vaf']:g})"
    )
    return jsonify(
        {
            "available": exe is not None,
            "engine": _spice_engine_label(exe) or "ngspice",
            "engine_path": exe,
            "model": spice_engine.DEFAULT_MODEL_NAME,
            "model_definition": model_definition,
            "reference": spice_engine.reference_params(),
            "defaults": {
                "amplitude_mv": spice_engine.DEFAULT_AMPLITUDE_V * 1000.0,
                "frequency_hz": spice_engine.DEFAULT_FREQUENCY_HZ,
            },
            "install_hint": SPICE_INSTALL_HINT,
        }
    )


@app.route("/api/spice", methods=["POST"])
def api_spice():
    """รัน ngspice จริงสำหรับ analysis ที่เลือก แล้วคืนผลแยกจากค่า Analytical"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "ต้องส่ง JSON object"}), 400

    try:
        analysis, params, selections, amplitude_v, frequency_hz = _spice_request(payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not spice_engine.find_ngspice():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "ไม่พบ ngspice ในเครื่อง — ติดตั้งแล้วตั้งค่า NGSPICE_BIN หรือ PATH",
                    "install_hint": SPICE_INSTALL_HINT,
                }
            ),
            503,
        )

    try:
        run_result = spice_engine.run(
            analysis,
            params,
            amplitude_v=amplitude_v,
            frequency_hz=frequency_hz,
        )
    except spice_engine.SpiceError as exc:
        return jsonify({"ok": False, "error": exc.message, "detail": exc.detail}), 400

    data = run_result["data"]
    response: dict = {
        "ok": True,
        "analysis": analysis,
        "engine": run_result["engine"],
        "engine_path": run_result["engine_path"],
        "model": run_result["model"],
        "netlist": run_result["netlist"],
        "log": run_result["log"],
        "warnings": run_result["warnings"],
        "duration_ms": run_result["duration_ms"],
        "parameters": {**params, **run_result["parameters"]},
        "amplitude": _spice_entry(amplitude_v, "voltage", AUTO),
        "frequency": _spice_entry(frequency_hz, "frequency", AUTO),
        "plot_svg": None,
    }

    if analysis == "op":
        response["values"] = _spice_values(data, selections)
        analytical = _calculate("divider", params)
        response["analytical"] = {
            "source": "dc_bias.py (Python analytical model)",
            "region": analytical.get("region", ""),
            "values": _build_display(analytical, selections),
        }
        return jsonify(response)

    if analysis == "ac":
        response["plot_svg"] = spice_plots.bode_svg(data)
        response["series"] = {
            "kind": "bode",
            "points": len(data["frequency"]),
            "x_label": "Frequency (Hz)",
        }
    else:
        response["plot_svg"] = spice_plots.waveform_svg(data)
        response["series"] = {
            "kind": "waveform",
            "points": len(data["time"]),
            "x_label": "Time (s)",
        }

    response["summary"] = _spice_summary(analysis, data, amplitude_v, frequency_hz)
    return jsonify(response)


if __name__ == "__main__":
    print("=" * 50)
    print("Starting BJT DC Bias Web App...")
    print("=" * 50)
    print("Open: http://127.0.0.1:5000/")
    print("=" * 50)
    app.run(debug=True, host="127.0.0.1", port=5000)
