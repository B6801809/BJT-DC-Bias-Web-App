"""SVG charts for ngspice results (Bode plot and transient waveforms).

วาดด้วย Python ล้วน ไม่ใช้ matplotlib และไม่ import Flask
ทุกฟังก์ชันคืนค่าเป็นข้อความ SVG เท่านั้น
"""

from __future__ import annotations

import math
from html import escape
from typing import Any, Iterable, Sequence

FONT = "Noto Sans Thai, Tahoma, Arial, sans-serif"
INK = "#17344b"
MUTED = "#486275"
GRID = "#dbe7ef"
AXIS = "#9cb4c4"
PANEL = "#ffffff"
TEAL = "#07766e"
ORANGE = "#a65a2c"


# --------------------------------------------------------------------------
# Small numeric helpers
# --------------------------------------------------------------------------

def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _num_label(value: float) -> str:
    """จัดรูปตัวเลขบนแกนแบบอ่านง่าย"""
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 1e6 or magnitude < 1e-3:
        return f"{value:.1e}"
    return f"{value:.4g}"


def _nice_step(span: float, target: int = 5) -> float:
    if span <= 0:
        return 1.0
    raw = span / max(target, 1)
    exponent = math.floor(math.log10(raw))
    base = raw / (10 ** exponent)
    for multiple in (1.0, 2.0, 2.5, 5.0, 10.0):
        if base <= multiple:
            return multiple * (10 ** exponent)
    return 10 ** (exponent + 1)


def _ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    if not (_finite(lo) and _finite(hi)) or hi <= lo:
        return [lo]
    step = _nice_step(hi - lo, target)
    start = math.floor(lo / step) * step
    values: list[float] = []
    value = start
    guard = 0
    while value <= hi + step * 1e-6 and guard < 200:
        if value >= lo - step * 1e-6:
            values.append(round(value, 12))
        value += step
        guard += 1
    return values or [lo]


def _polyline(
    points: Iterable[tuple[float, float] | None],
    *,
    stroke: str,
    width: float = 2.0,
) -> str:
    """สร้าง <polyline> หลายช่วง โดยข้ามจุดที่ไม่มีข้อมูล"""
    segments: list[list[str]] = []
    current: list[str] = []
    for point in points:
        if point is None:
            if len(current) > 1:
                segments.append(current)
            current = []
            continue
        current.append(f"{point[0]:.2f},{point[1]:.2f}")
    if len(current) > 1:
        segments.append(current)

    return "".join(
        f'<polyline points="{" ".join(segment)}" fill="none" stroke="{stroke}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round" />'
        for segment in segments
    )


def _placeholder(width: int, height: int, message: str = "ไม่มีข้อมูลสำหรับวาดกราฟ") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" width="100%" style="max-width:{width}px">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{PANEL}" />'
        f'<text x="{width / 2:.0f}" y="{height / 2:.0f}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="15" fill="{MUTED}">{escape(message)}</text>'
        f"</svg>"
    )


def _panel_frame(
    x0: float,
    y0: float,
    width: float,
    height: float,
    *,
    y_ticks: Sequence[float],
    y_lo: float,
    y_hi: float,
    x_ticks: Sequence[float],
    x_to_px,
    x_label: str | None,
    title: str,
) -> tuple[list[str], Any]:
    """วาดกรอบกราฟ + เส้นกริด + ป้ายแกน แล้วคืน (ชิ้นส่วน SVG, ฟังก์ชันแปลง y)"""
    parts: list[str] = [
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'fill="{PANEL}" stroke="{AXIS}" stroke-width="1" />'
    ]

    span = y_hi - y_lo

    def y_to_px(value: float) -> float:
        ratio = (value - y_lo) / span if span else 0.5
        return y0 + height - ratio * height

    for tick in y_ticks:
        py = y_to_px(tick)
        parts.append(
            f'<line x1="{x0:.1f}" y1="{py:.1f}" x2="{x0 + width:.1f}" y2="{py:.1f}" '
            f'stroke="{GRID}" stroke-width="1" />'
        )
        parts.append(
            f'<text x="{x0 - 8:.1f}" y="{py + 4:.1f}" text-anchor="end" '
            f'font-family="{FONT}" font-size="11" fill="{MUTED}">{escape(_num_label(tick))}</text>'
        )

    for tick in x_ticks:
        px = x_to_px(tick)
        parts.append(
            f'<line x1="{px:.1f}" y1="{y0:.1f}" x2="{px:.1f}" y2="{y0 + height:.1f}" '
            f'stroke="{GRID}" stroke-width="1" />'
        )
        if x_label is None:
            parts.append(
                f'<text x="{px:.1f}" y="{y0 + height + 15:.1f}" text-anchor="middle" '
                f'font-family="{FONT}" font-size="11" fill="{MUTED}">{escape(_num_label(tick))}</text>'
            )

    parts.append(
        f'<text x="{x0:.1f}" y="{y0 - 8:.1f}" font-family="{FONT}" font-size="12" '
        f'font-weight="700" fill="{INK}">{escape(title)}</text>'
    )
    if x_label:
        parts.append(
            f'<text x="{x0 + width / 2:.1f}" y="{y0 + height + 32:.1f}" text-anchor="middle" '
            f'font-family="{FONT}" font-size="12" fill="{MUTED}">{escape(x_label)}</text>'
        )
    return parts, y_to_px


# --------------------------------------------------------------------------
# Bode plot
# --------------------------------------------------------------------------

def bode_svg(ac: dict, width: int = 820, height: int = 460) -> str:
    """กราฟ Bode: ขนาด (dB) และเฟส (°) เทียบความถี่แบบ log"""
    frequencies = list(ac.get("frequency") or [])
    gain_db = list(ac.get("gain_db") or [])
    phase = list(ac.get("phase_deg") or [])

    rows = [
        (float(f), float(g), float(p))
        for f, g, p in zip(frequencies, gain_db, phase)
        if _finite(f) and _finite(g) and _finite(p) and float(f) > 0
    ]
    if not rows:
        return _placeholder(width, height)

    freqs = [row[0] for row in rows]
    gains = [row[1] for row in rows]
    phases = [row[2] for row in rows]

    log_lo = math.log10(min(freqs))
    log_hi = math.log10(max(freqs))
    if log_hi - log_lo < 0.5:
        log_lo -= 0.5
        log_hi += 0.5

    pad_left, pad_right, pad_top, pad_bottom = 78.0, 20.0, 44.0, 58.0
    gap = 46.0
    plot_width = width - pad_left - pad_right
    plot_height = (height - pad_top - pad_bottom - gap) / 2

    gain_top = pad_top + 12
    gain_bot = gain_top + plot_height
    phase_top = gain_bot + gap
    phase_bot = phase_top + plot_height

    def f_to_px(freq: float) -> float:
        return pad_left + (math.log10(freq) - log_lo) / (log_hi - log_lo) * plot_width

    gain_lo, gain_hi = min(gains), max(gains)
    gain_pad = max((gain_hi - gain_lo) * 0.12, 1.0)
    gain_lo -= gain_pad
    gain_hi += gain_pad

    phase_lo, phase_hi = min(phases), max(phases)
    phase_pad = max((phase_hi - phase_lo) * 0.12, 5.0)
    phase_lo -= phase_pad
    phase_hi += phase_pad

    decades = [
        float(10 ** exponent)
        for exponent in range(math.ceil(log_lo), math.floor(log_hi) + 1)
    ]

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" width="100%" style="max-width:{width}px">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{PANEL}" />',
    ]

    gain_parts, gain_to_px = _panel_frame(
        pad_left,
        gain_top,
        plot_width,
        plot_height,
        y_ticks=_ticks(gain_lo, gain_hi, 4),
        y_lo=gain_lo,
        y_hi=gain_hi,
        x_ticks=decades,
        x_to_px=f_to_px,
        x_label=None,
        title="Gain (dB)",
    )
    parts.extend(gain_parts)
    parts.append(
        _polyline(
            [(f_to_px(f), gain_to_px(g)) for f, g in zip(freqs, gains)],
            stroke=TEAL,
        )
    )

    phase_parts, phase_to_px = _panel_frame(
        pad_left,
        phase_top,
        plot_width,
        plot_height,
        y_ticks=_ticks(phase_lo, phase_hi, 4),
        y_lo=phase_lo,
        y_hi=phase_hi,
        x_ticks=decades,
        x_to_px=f_to_px,
        x_label="Frequency (Hz)",
        title="Phase (°)",
    )
    parts.extend(phase_parts)
    parts.append(
        _polyline(
            [(f_to_px(f), phase_to_px(p)) for f, p in zip(freqs, phases)],
            stroke=ORANGE,
        )
    )

    parts.append(
        f'<text x="{width - pad_right:.1f}" y="{pad_top - 18:.1f}" text-anchor="end" '
        f'font-family="{FONT}" font-size="12" font-weight="700" fill="{TEAL}">|Vout/Vin|</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Transient waveform
# --------------------------------------------------------------------------

def waveform_svg(tran: dict, width: int = 820, height: int = 400) -> str:
    """กราฟเวลา: Vin และ Vout (มิลลิวินาที / โวลต์)"""
    times = list(tran.get("time") or [])
    vin = list(tran.get("vin") or [])
    vout = list(tran.get("vout") or [])

    rows = [
        (float(t), float(a), float(b))
        for t, a, b in zip(times, vin, vout)
        if _finite(t) and _finite(a) and _finite(b)
    ]
    if not rows:
        return _placeholder(width, height)

    t_values = [row[0] for row in rows]
    vin_values = [row[1] for row in rows]
    vout_values = [row[2] for row in rows]

    t_lo, t_hi = min(t_values), max(t_values)
    if t_hi <= t_lo:
        t_hi = t_lo + 1e-6

    pad_left, pad_right, pad_top, pad_bottom = 82.0, 22.0, 46.0, 64.0
    plot_width = width - pad_left - pad_right
    plot_height = height - pad_top - pad_bottom

    def t_to_px(seconds: float) -> float:
        return pad_left + (seconds - t_lo) / (t_hi - t_lo) * plot_width

    combined = vin_values + vout_values
    v_lo, v_hi = min(combined), max(combined)
    span = v_hi - v_lo
    if span <= 0:
        span = max(abs(v_hi), 1e-3) * 0.4
    v_lo -= span * 0.12
    v_hi += span * 0.12

    x_ticks = [tick / 1000.0 for tick in _ticks(t_lo * 1000.0, t_hi * 1000.0, 6)]

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" width="100%" style="max-width:{width}px">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{PANEL}" />',
    ]

    frame_parts, y_to_px = _panel_frame(
        pad_left,
        pad_top,
        plot_width,
        plot_height,
        y_ticks=_ticks(v_lo, v_hi, 5),
        y_lo=v_lo,
        y_hi=v_hi,
        x_ticks=x_ticks,
        x_to_px=t_to_px,
        x_label="Time (ms)",
        title="Voltage (V)",
    )
    parts.extend(frame_parts)

    parts.append(
        _polyline(
            [(t_to_px(t), y_to_px(v)) for t, v in zip(t_values, vin_values)],
            stroke=MUTED,
            width=1.6,
        )
    )
    parts.append(
        _polyline(
            [(t_to_px(t), y_to_px(v)) for t, v in zip(t_values, vout_values)],
            stroke=TEAL,
            width=2.2,
        )
    )

    legend_y = pad_top - 26
    parts.append(
        f'<line x1="{pad_left + 8:.1f}" y1="{legend_y:.1f}" x2="{pad_left + 30:.1f}" '
        f'y2="{legend_y:.1f}" stroke="{MUTED}" stroke-width="2" />'
        f'<text x="{pad_left + 36:.1f}" y="{legend_y + 4:.1f}" font-family="{FONT}" '
        f'font-size="12" fill="{MUTED}">Vin</text>'
    )
    parts.append(
        f'<line x1="{pad_left + 90:.1f}" y1="{legend_y:.1f}" x2="{pad_left + 112:.1f}" '
        f'y2="{legend_y:.1f}" stroke="{TEAL}" stroke-width="2.2" />'
        f'<text x="{pad_left + 118:.1f}" y="{legend_y + 4:.1f}" font-family="{FONT}" '
        f'font-size="12" fill="{TEAL}" font-weight="700">Vout</text>'
    )

    parts.append("</svg>")
    return "".join(parts)
