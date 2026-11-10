"""SVG rendering helpers for the BJT DC Bias web app.

โมดูลนี้เป็น pure function ที่คืนค่าเป็นข้อความ SVG (ไม่ import Flask, ไม่ต้องพึ่ง
ไลบรารีภายนอก) เพื่อให้หน้าเว็บแสดงภาพวงจรและกราฟ DC load line ที่คำนวณจาก
ค่าจริงที่ผู้ใช้กรอก

หลักการ: ทุกค่าที่ถูกวาดลงใน SVG มาจากการ format ตัวเลขของเราเอง เพื่อความปลอดภัย
"""

from __future__ import annotations

from units import (
    AUTO,
    CURRENT_UNITS,
    VOLTAGE_UNITS,
    auto_unit,
    format_number,
    format_value,
)

# สี/ค่าคงที่ของกราฟ
VCE_SAT = 0.2  # V — ใช้เป็นจุดเริ่มต้นของย่าน Saturation ในกราฟ

PALETTE = {
    "wire": "#3c5a73",
    "device": "#103658",
    "component": "#1d638b",
    "component_fill": "#e8f2fa",
    "label": "#17344b",
    "muted": "#546d83",
    "loadline": "#b85c2c",
    "curve": "#0c8078",
    "qpoint": "#b02f6b",
    "ground": "#3c5a73",
}


def _esc(text: object) -> str:
    """Escape ข้อความที่จะแทรกใน SVG/XML"""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _num(value: float, digits: int = 3) -> str:
    """Format ตัวเลขให้อ่านง่าย โดยตัดเลขศูนย์ท้ายที่ไม่จำเป็นออก"""
    return format_number(value, digits)


def _resolve_units(display_units: dict | None) -> dict:
    """รวมค่าหน่วยที่ผู้ใช้เลือก พร้อมค่าเริ่มต้น (auto)"""
    resolved = {"voltage": AUTO, "current": AUTO, "resistance": AUTO}
    if display_units:
        for key, value in display_units.items():
            if key in resolved and value:
                resolved[key] = value
    return resolved


def _ground(x: float, y: float, uid: str) -> str:
    """วาดสัญลักษณ์กราวด์"""
    p = PALETTE
    return (
        f'<g class="ground">'
        f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + 12}" stroke="{p["ground"]}" stroke-width="2"/>'
        f'<line x1="{x - 10}" y1="{y + 12}" x2="{x + 10}" y2="{y + 12}" stroke="{p["ground"]}" stroke-width="2.4"/>'
        f'<line x1="{x - 6}" y1="{y + 17}" x2="{x + 6}" y2="{y + 17}" stroke="{p["ground"]}" stroke-width="2"/>'
        f'<line x1="{x - 2.5}" y1="{y + 22}" x2="{x + 2.5}" y2="{y + 22}" stroke="{p["ground"]}" stroke-width="1.8"/>'
        f"</g>"
    )


def _resistor(x: float, y: float, w: float, h: float, label: str, uid: str) -> str:
    """วาดตัวต้านทานแบบกล่อง (IEC) พร้อมป้ายกำกับ"""
    p = PALETTE
    return (
        f'<g class="component">'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" '
        f'fill="{p["component_fill"]}" stroke="{p["component"]}" stroke-width="2"/>'
        f'<text x="{x + w + 8}" y="{y + h / 2 + 4}" font-size="13" font-weight="bold" fill="{p["label"]}">'
        f"{_esc(label)}</text>"
        f"</g>"
    )


# ---------------------------------------------------------------------------
# 1) ภาพวงจร (schematic)
# ---------------------------------------------------------------------------


def schematic_svg(
    *,
    vcc: float,
    r1: float,
    r2: float,
    rc: float,
    re: float,
    beta: float,
    vbe: float,
    vb: float | None = None,
    ve: float | None = None,
    vc: float | None = None,
    ic: float | None = None,
    display_units: dict | None = None,
) -> str:
    """วาดภาพวงจร BJT NPN Common-Emitter แบบ Voltage-Divider Bias

    ค่าที่รับเข้ามาเป็นหน่วย SI (V, Ω, A) ส่วน vb/ve/vc/ic เป็นค่าที่คำนวณได้
    ถ้าต้องการแสดงบนภาพ (ถ้าไม่ส่งมาจะไม่แสดง)

    display_units: หน่วยที่ใช้แสดงผล เช่น {"voltage": "mV", "current": "µA"}
    """
    p = PALETTE
    uid = "sch"
    units = _resolve_units(display_units)
    parts: list[str] = []

    # --- โครงร่างพิกัด ---
    vcc_y = 40
    base_y = 165
    gnd_y = 330
    x_r1 = 150
    x_rc = 430
    x_q = 300
    x_re = 330

    parts.append(
        f'<defs><marker id="{uid}-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" '
        f'orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="{p["label"]}"/></marker></defs>'
    )
    parts.append(
        f'<rect width="560" height="400" rx="10" fill="#ffffff" stroke="#d3e0ec"/>'
    )

    # --- แรงดันจ่าย VCC ---
    parts.append(
        f'<g class="supply">'
        f'<line x1="110" y1="{vcc_y}" x2="470" y2="{vcc_y}" stroke="{p["wire"]}" stroke-width="2.4"/>'
        f'<circle cx="110" cy="{vcc_y}" r="4" fill="{p["wire"]}"/>'
        f'<text x="150" y="{vcc_y - 14}" text-anchor="middle" font-size="14" font-weight="bold" '
        f'fill="{p["label"]}">VCC = {format_value(vcc, "voltage", units["voltage"])}</text>'
        f"</g>"
    )

    # --- R1 (VCC → Base) ---
    parts.append(f'<line x1="{x_r1}" y1="{vcc_y}" x2="{x_r1}" y2="70" stroke="{p["wire"]}" stroke-width="2.4"/>')
    parts.append(_resistor(x_r1 - 11, 70, 22, 50, f"R1 = {format_value(r1, 'resistance', units['resistance'])}", uid))
    parts.append(f'<line x1="{x_r1}" y1="120" x2="{x_r1}" y2="{base_y}" stroke="{p["wire"]}" stroke-width="2.4"/>')

    # --- R2 (Base → GND) ---
    parts.append(f'<line x1="{x_r1}" y1="{base_y}" x2="{x_r1}" y2="200" stroke="{p["wire"]}" stroke-width="2.4"/>')
    parts.append(_resistor(x_r1 - 11, 200, 22, 50, f"R2 = {format_value(r2, 'resistance', units['resistance'])}", uid))
    parts.append(f'<line x1="{x_r1}" y1="250" x2="{x_r1}" y2="{gnd_y}" stroke="{p["wire"]}" stroke-width="2.4"/>')
    parts.append(_ground(x_r1, gnd_y, uid))

    # --- RC (VCC → Collector) ---
    parts.append(f'<line x1="{x_rc}" y1="{vcc_y}" x2="{x_rc}" y2="70" stroke="{p["wire"]}" stroke-width="2.4"/>')
    parts.append(_resistor(x_rc - 11, 70, 22, 50, f"RC = {format_value(rc, 'resistance', units['resistance'])}", uid))
    parts.append(f'<line x1="{x_rc}" y1="120" x2="{x_rc}" y2="135" stroke="{p["wire"]}" stroke-width="2.4"/>')

    # --- ทรานซิสเตอร์ NPN ---
    parts.append(
        f'<g class="device">'
        f'<circle cx="{x_q}" cy="185" r="44" fill="#ffffff" stroke="{p["device"]}" stroke-width="2"/>'
        f'<line x1="280" y1="150" x2="280" y2="210" stroke="{p["device"]}" stroke-width="3"/>'
        f'<line x1="280" y1="162" x2="322" y2="135" stroke="{p["device"]}" stroke-width="2.4"/>'
        f'<line x1="280" y1="198" x2="322" y2="225" stroke="{p["device"]}" stroke-width="2.4" '
        f'marker-end="url(#{uid}-arrow)"/>'
        f'<text x="{x_q}" y="118" text-anchor="middle" font-size="14" font-weight="bold" '
        f'fill="{p["device"]}">Q1 (NPN)</text>'
        f"</g>"
    )

    # --- เส้นต่อ Base และ Collector ---
    parts.append(f'<line x1="{x_r1}" y1="{base_y}" x2="280" y2="{base_y}" stroke="{p["wire"]}" stroke-width="2.4"/>')
    parts.append(f'<circle cx="{x_r1}" cy="{base_y}" r="4" fill="{p["wire"]}"/>')
    parts.append(f'<line x1="322" y1="135" x2="{x_rc}" y2="135" stroke="{p["wire"]}" stroke-width="2.4"/>')

    # --- RE (Emitter → GND) ---
    parts.append(f'<line x1="{x_re}" y1="225" x2="{x_re}" y2="265" stroke="{p["wire"]}" stroke-width="2.4"/>')
    parts.append(_resistor(x_re - 11, 265, 22, 50, f"RE = {format_value(re, 'resistance', units['resistance'])}", uid))
    parts.append(f'<line x1="{x_re}" y1="315" x2="{x_re}" y2="{gnd_y}" stroke="{p["wire"]}" stroke-width="2.4"/>')
    parts.append(_ground(x_re, gnd_y, uid))

    # --- ลูกศรกระแส IC / IE ---
    parts.append(
        f'<g class="current">'
        f'<line x1="365" y1="135" x2="352" y2="135" stroke="{p["label"]}" stroke-width="1.8" '
        f'marker-end="url(#{uid}-arrow)"/>'
        f'<line x1="{x_re}" y1="243" x2="{x_re}" y2="256" stroke="{p["label"]}" stroke-width="1.8" '
        f'marker-end="url(#{uid}-arrow)"/>'
        f"</g>"
    )

    # --- ค่าของโหนด ---
    if vb is not None:
        parts.append(
            f'<text x="168" y="{base_y - 8}" font-size="12.5" font-weight="bold" fill="{p["muted"]}">'
            f"VB = {format_value(vb, 'voltage', units['voltage'])}</text>"
        )
    if vc is not None:
        parts.append(
            f'<text x="449" y="128" font-size="12.5" font-weight="bold" fill="{p["muted"]}">'
            f"VC = {format_value(vc, 'voltage', units['voltage'])}</text>"
        )
    if ve is not None:
        parts.append(
            f'<text x="342" y="258" font-size="12.5" font-weight="bold" fill="{p["muted"]}">'
            f"VE = {format_value(ve, 'voltage', units['voltage'])}</text>"
        )
    if ic is not None:
        parts.append(
            f'<text x="438" y="152" text-anchor="end" font-size="12.5" font-weight="bold" '
            f'fill="{p["muted"]}">IC = {format_value(ic, 'current', units['current'])}</text>'
        )

    # --- ข้อมูลประจำทรานซิสเตอร์ ---
    parts.append(
        f'<text x="150" y="374" font-size="12.5" fill="{p["muted"]}">'
        f"β = {_num(beta, 0)} · VBE = {format_value(vbe, 'voltage', units['voltage'])} "
        f"· โหมด Forward-Active (β, VBE คงที่)"
        f"</text>"
    )

    return (
        f'<svg viewBox="0 0 560 400" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="วงจร BJT NPN Common-Emitter แบบ Voltage-Divider Bias" '
        f'class="figure-svg">{"".join(parts)}</svg>'
    )


# ---------------------------------------------------------------------------
# 2) กราฟ DC load line และจุด Q
# ---------------------------------------------------------------------------


def load_line_current(vcc: float, rc: float, re: float, beta: float, vce: float) -> float:
    """กระแสคอลเลกเตอร์บน DC load line ที่แรงดัน VCE ที่กำหนด

    จาก VCE = VCC − IC·RC − IE·RE และ IE = IC·(β+1)/β ได้ว่า
    IC = (VCC − VCE) / (RC + RE·(β+1)/β)
    """
    if not beta:
        return 0.0
    re_eff = re * (beta + 1) / beta
    denom = rc + re_eff
    if denom <= 0:
        return 0.0
    return max((vcc - vce) / denom, 0.0)


def load_line_svg(
    *,
    vcc: float,
    rc: float,
    re: float,
    beta: float,
    ib: float,
    ic: float,
    vce: float,
    region: str = "Forward-Active",
    display_units: dict | None = None,
) -> str:
    """วาดกราฟ output characteristic ของทรานซิสเตอร์ร่วมกับ DC load line และจุด Q

    - เส้นโค้งของทรานซิสเตอร์: IC = β·IB คงที่ในย่าน Forward-Active
    - DC load line: VCE = VCC − IC·RC − IE·RE โดยใช้ IE = IC·(β+1)/β
    - จุด Q คือจุดตัดของทั้งสองเส้น
    """
    p = PALETTE
    uid = "ll"
    units = _resolve_units(display_units)

    ic_sat_line = load_line_current(vcc, rc, re, beta, 0.0)
    ic_active = max(beta * ib, 0.0) if beta else 0.0

    # --- ขอบเขตของกราฟ ---
    x_max = max(vcc, vce * 1.05, 1e-9)
    y_max = max(ic_active, ic_sat_line, ic, 1e-12) * 1.25

    left, right = 70, 520
    top, bottom = 40, 310
    width = right - left
    height = bottom - top

    def X(v: float) -> float:
        return left + (v / x_max) * width

    def Y(i: float) -> float:
        return bottom - (i / y_max) * height

    # หน่วยที่ใช้แสดงบนแกนของกราฟ
    vol_unit = units["voltage"] if units["voltage"] != AUTO else auto_unit(x_max, "voltage")
    cur_unit = units["current"] if units["current"] != AUTO else auto_unit(y_max, "current")

    parts: list[str] = [
        f'<defs><marker id="{uid}-axis" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        f'<path d="M0,0 L8,4 L0,8 Z" fill="{p["muted"]}"/></marker></defs>',
        f'<rect width="560" height="380" rx="10" fill="#ffffff" stroke="#d3e0ec"/>',
    ]

    # --- ตารางและแกน ---
    for i in range(6):
        v = x_max * i / 5
        x = X(v)
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#eef3f8" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{bottom + 18}" text-anchor="middle" font-size="11" fill="{p["muted"]}">'
            f"{_num(v / VOLTAGE_UNITS[vol_unit], 1)}</text>"
        )
    for i in range(6):
        cur = y_max * i / 5
        y = Y(cur)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#eef3f8" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="{p["muted"]}">'
            f"{_num(cur / CURRENT_UNITS[cur_unit], 2)}</text>"
        )

    parts.append(
        f'<line x1="{left}" y1="{bottom}" x2="{right + 10}" y2="{bottom}" stroke="{p["muted"]}" '
        f'stroke-width="1.6" marker-end="url(#{uid}-axis)"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{bottom}" x2="{left}" y2="{top - 10}" stroke="{p["muted"]}" '
        f'stroke-width="1.6" marker-end="url(#{uid}-axis)"/>'
    )
    parts.append(
        f'<text x="{right}" y="{bottom + 36}" text-anchor="end" font-size="12.5" font-weight="bold" '
        f'fill="{p["label"]}">VCE ({vol_unit})</text>'
    )
    parts.append(
        f'<text x="{left - 52}" y="{top - 18}" font-size="12.5" font-weight="bold" fill="{p["label"]}">'
        f"IC ({cur_unit})</text>"
    )

    # --- DC load line: จาก (VCE=0, IC=ICsat) ไป (VCE=VCC, IC=0) ---
    parts.append(
        f'<line x1="{X(0):.1f}" y1="{Y(ic_sat_line):.1f}" x2="{X(x_max):.1f}" y2="{Y(0):.1f}" '
        f'stroke="{p["loadline"]}" stroke-width="2.4" stroke-dasharray="8 5"/>'
    )
    parts.append(
        f'<text x="{X(x_max * 0.62):.1f}" y="{Y(ic_sat_line * (1 - 0.62)):.1f}" font-size="12" '
        f'font-weight="bold" fill="{p["loadline"]}">DC Load Line</text>'
    )

    # --- เส้นโค้งของทรานซิสเตอร์ (IC = β·IB) ---
    if ic_active > 0:
        parts.append(
            f'<line x1="{X(VCE_SAT):.1f}" y1="{Y(ic_active):.1f}" x2="{X(x_max):.1f}" y2="{Y(ic_active):.1f}" '
            f'stroke="{p["curve"]}" stroke-width="2.8"/>'
        )
        ic_at_zero = min(ic_active, ic_sat_line)
        parts.append(
            f'<line x1="{X(VCE_SAT):.1f}" y1="{Y(ic_active):.1f}" x2="{X(0):.1f}" y2="{Y(ic_at_zero):.1f}" '
            f'stroke="{p["curve"]}" stroke-width="2.8"/>'
        )
        parts.append(
            f'<text x="{X(VCE_SAT) + 8:.1f}" y="{Y(ic_active) - 10:.1f}" font-size="12" font-weight="bold" '
            f'fill="{p["curve"]}">IC = β·IB = {format_value(ic_active, "current", cur_unit)}</text>'
        )
    else:
        parts.append(
            f'<line x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(x_max):.1f}" y2="{Y(0):.1f}" '
            f'stroke="{p["curve"]}" stroke-width="2.8"/>'
        )
        parts.append(
            f'<text x="{X(VCE_SAT) + 8:.1f}" y="{Y(0) - 10:.1f}" font-size="12" font-weight="bold" '
            f'fill="{p["curve"]}">IC = 0 (Cutoff)</text>'
        )

    # --- จุด Q ---
    qx, qy = X(vce), Y(ic)
    parts.append(
        f'<g class="qpoint">'
        f'<line x1="{qx:.1f}" y1="{qy:.1f}" x2="{qx:.1f}" y2="{bottom}" stroke="{p["qpoint"]}" '
        f'stroke-width="1.2" stroke-dasharray="4 4"/>'
        f'<line x1="{qx:.1f}" y1="{qy:.1f}" x2="{left}" y2="{qy:.1f}" stroke="{p["qpoint"]}" '
        f'stroke-width="1.2" stroke-dasharray="4 4"/>'
        f'<circle cx="{qx:.1f}" cy="{qy:.1f}" r="6" fill="#ffffff" stroke="{p["qpoint"]}" stroke-width="2.6"/>'
        f'<circle cx="{qx:.1f}" cy="{qy:.1f}" r="2" fill="{p["qpoint"]}"/>'
        f"</g>"
    )

    label = (
        f"Q: VCE = {format_value(vce, 'voltage', vol_unit)}, "
        f"IC = {format_value(ic, 'current', cur_unit)}"
    )
    if region != "Forward-Active":
        label += " (ประมาณการ — นอกย่าน Forward-Active)"
    # วางป้ายใต้จุด Q เพื่อไม่ให้ทับเส้นโค้งของทรานซิสเตอร์
    text_y = qy + 26 if qy < bottom - 50 else qy - 14
    parts.append(
        f'<text x="{qx:.1f}" y="{text_y:.1f}" text-anchor="middle" font-size="12.5" font-weight="bold" '
        f'fill="{p["qpoint"]}">{_esc(label)}</text>'
    )

    parts.append(
        f'<text x="546" y="22" text-anchor="end" font-size="12" fill="{p["muted"]}">'
        f"RE มีผลต่อ load line ผ่าน IE = IC·(β+1)/β · VCE(sat) ≈ {_num(VCE_SAT, 1)} V"
        f"</text>"
    )

    return (
        f'<svg viewBox="0 0 560 380" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="กราฟ DC load line และจุด Q ของวงจร" class="figure-svg">'
        f'{"".join(parts)}</svg>'
    )


# ---------------------------------------------------------------------------
# 3) แผนภาพระดับแรงดันของแต่ละโหนด
# ---------------------------------------------------------------------------


def voltage_levels_svg(
    *,
    vcc: float,
    vc: float,
    vb: float,
    ve: float,
    vce: float,
    display_units: dict | None = None,
) -> str:
    """วาดแผนภาพแท่งแรงดันของโหนด VC, VB, VE เทียบกับ VCC"""
    p = PALETTE
    uid = "vl"
    units = _resolve_units(display_units)
    vol_unit = units["voltage"] if units["voltage"] != AUTO else auto_unit(vcc, "voltage")

    left = 110
    bar_max = 330
    top = 54
    row_h = 52

    top_v = max(vcc, 1e-9)

    def width_of(value: float) -> float:
        return max(0.0, min(1.0, value / top_v)) * bar_max

    rows = [
        ("VC", vc, p["loadline"]),
        ("VB", vb, p["component"]),
        ("VE", ve, p["curve"]),
    ]

    parts: list[str] = [
        f'<rect width="560" height="290" rx="10" fill="#ffffff" stroke="#d3e0ec"/>',
    ]

    for index, (name, value, color) in enumerate(rows):
        y = top + index * row_h
        w = width_of(value)
        parts.append(
            f'<text x="{left - 10}" y="{y + 20}" text-anchor="end" font-size="14" font-weight="bold" '
            f'fill="{p["label"]}">{name}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y}" width="{bar_max}" height="28" rx="5" fill="#f1f6fa" '
            f'stroke="#dbe7f0"/>'
        )
        parts.append(
            f'<rect x="{left}" y="{y}" width="{w:.1f}" height="28" rx="5" fill="{color}" opacity="0.85"/>'
        )
        parts.append(
            f'<text x="{left + bar_max + 10}" y="{y + 20}" font-size="13.5" font-weight="bold" '
            f'fill="{p["label"]}">{format_value(value, "voltage", vol_unit)}</text>'
        )

    # เส้นแสดงระดับ VCC
    y_vcc = top + 3 * row_h
    parts.append(
        f'<line x1="{left}" y1="{y_vcc - 8}" x2="{left + bar_max}" y2="{y_vcc - 8}" '
        f'stroke="{p["muted"]}" stroke-width="1.6" stroke-dasharray="6 4"/>'
    )
    parts.append(
        f'<text x="{left}" y="{y_vcc + 8}" font-size="12.5" font-weight="bold" fill="{p["muted"]}">'
        f"VCC = {format_value(vcc, 'voltage', vol_unit)} (ระดับอ้างอิง)</text>"
    )
    parts.append(
        f'<text x="{left}" y="{y_vcc + 30}" font-size="12.5" fill="{p["muted"]}">'
        f"VCE = VC − VE = {format_value(vce, 'voltage', vol_unit)}</text>"
    )

    return (
        f'<svg viewBox="0 0 560 290" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="แผนภาพระดับแรงดันของแต่ละโหนด" class="figure-svg">'
        f'{"".join(parts)}</svg>'
    )
