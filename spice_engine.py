"""ngspice integration for the CE Voltage-Divider amplifier (Lab 04).

โมดูลนี้รับผิดชอบเฉพาะการคุยกับ ngspice:
- สร้าง netlist ของวงจรอ้างอิง
- เรียก executable ผ่าน ``subprocess`` แบบ list argument (ไม่ใช้ shell)
- อ่านผลลัพธ์จาก ASCII rawfile ที่ ngspice เขียนออกมา

ไม่ import Flask และไม่รู้จัก HTML — ชั้น ``app.py`` เป็นผู้เรียกใช้
หน่วยภายในเป็น SI ทั้งหมด (V, Ω, F, A, Hz)
"""

from __future__ import annotations

import glob
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping

DEFAULT_MODEL_NAME = "QNPN_GENERIC"
DEFAULT_MODEL = {
    "name": DEFAULT_MODEL_NAME,
    "bf": 100.0,
    "is": 1e-14,
    "vaf": 100.0,
}

# วงจรอ้างอิง CE Voltage Divider ตามใบงาน Lab 04
REFERENCE: dict[str, float] = {
    "vcc": 12.0,
    "r1": 100e3,
    "r2": 22e3,
    "rc": 2.2e3,
    "re": 1e3,
    "rl": 10e3,
    "cin": 10e-6,
    "cout": 10e-6,
    "beta": 100.0,
    "vbe": 0.70,
}

DEFAULT_AMPLITUDE_V = 0.010   # 10 mV peak ตามใบงาน
DEFAULT_FREQUENCY_HZ = 1_000.0
TIMEOUT_S = 30.0
AC_SWEEP = "dec 10 10 1meg"
TRAN_STEP = "5u"
TRAN_STOP = "5m"

CIRCUIT_FIELDS = ("vcc", "r1", "r2", "rc", "re", "rl", "cin", "cout", "beta")

ANALYSES = ("op", "ac", "tran")

_MAX_DETAIL = 4000


class SpiceError(Exception):
    """ข้อผิดพลาดจากการเรียก ngspice หรือการอ่านผลลัพธ์"""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail[:_MAX_DETAIL]


# --------------------------------------------------------------------------
# Engine discovery
# --------------------------------------------------------------------------

def find_ngspice() -> str | None:
    """หา executable ของ ngspice จาก env, PATH หรือตำแหน่งติดตั้งมาตรฐาน"""
    override = os.environ.get("NGSPICE_BIN", "").strip().strip('"')
    if override:
        if os.path.isdir(override):
            for name in ("ngspice.exe", "ngspice_con.exe", "ngspice"):
                candidate = os.path.join(override, name)
                if os.path.isfile(candidate):
                    return candidate
        elif os.path.isfile(override):
            return override

    for name in ("ngspice", "ngspice.exe"):
        found = shutil.which(name)
        if found:
            return found

    patterns: list[str] = []
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            patterns.append(os.path.join(local, "Programs", "ngspice-*", "Spice64", "bin", "ngspice.exe"))
            patterns.append(os.path.join(local, "Programs", "ngspice", "Spice64", "bin", "ngspice.exe"))
        patterns.append(r"C:\Program Files\ngspice*\Spice64\bin\ngspice.exe")
        patterns.append(r"C:\Program Files (x86)\ngspice*\Spice64\bin\ngspice.exe")
        patterns.append(r"C:\Spice64\bin\ngspice.exe")
    else:
        patterns.extend(
            [
                "/usr/bin/ngspice",
                "/usr/local/bin/ngspice",
                "/opt/homebrew/bin/ngspice",
            ]
        )

    for pattern in patterns:
        for match in sorted(glob.glob(pattern), reverse=True):
            if os.path.isfile(match):
                return match
    return None


def engine_version_from_command(command: str) -> str:
    """ดึงชื่อรุ่นจากบรรทัด ``Command: ngspice-47, Build ...``"""
    match = re.search(r"(ngspice[\s\-]?[0-9][\w.\-]*)", command or "", re.IGNORECASE)
    if match:
        return match.group(1).replace(" ", "-")
    return "ngspice"


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _as_float(params: Mapping[str, Any], field: str) -> float:
    try:
        return float(params[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise SpiceError(f"ค่า {field.upper()} ต้องเป็นตัวเลข") from exc


def validate_params(
    params: Mapping[str, Any],
    *,
    amplitude_v: float | None = None,
    frequency_hz: float | None = None,
) -> None:
    """ตรวจค่าก่อนสร้าง netlist — ค่าไม่ถูกต้องต้องไม่ถูกส่งเข้า ngspice"""
    limits = {
        "vcc": ("VCC", "gt0"),
        "r1": ("R1", "gt0"),
        "r2": ("R2", "gt0"),
        "rc": ("RC", "gt0"),
        "re": ("RE", "ge0"),
        "beta": ("β", "gt0"),
    }
    for field, (label, rule) in limits.items():
        value = _as_float(params, field)
        if not math.isfinite(value):
            raise SpiceError(f"{label} ต้องเป็นค่าจำกัด")
        if rule == "gt0" and value <= 0:
            raise SpiceError(f"{label} ต้องมากกว่า 0")
        if rule == "ge0" and value < 0:
            raise SpiceError(f"{label} ต้องไม่ติดลบ")

    for field, label in (("rl", "RL"), ("cin", "Cin"), ("cout", "Cout")):
        if field in params:
            value = _as_float(params, field)
            if not math.isfinite(value) or value < 0:
                raise SpiceError(f"{label} ต้องไม่ติดลบ")

    if amplitude_v is not None and not (0 < float(amplitude_v) <= 1.0):
        raise SpiceError("Amplitude ต้องอยู่ระหว่าง 0 ถึง 1 V peak")

    if frequency_hz is not None and not (0 < float(frequency_hz) <= 1e9):
        raise SpiceError("Frequency ต้องอยู่ระหว่าง 0 ถึง 1 GHz")


def reference_params() -> dict[str, float]:
    """คืนค่าพารามิเตอร์ของวงจรอ้างอิง (สำเนา)"""
    return dict(REFERENCE)


# --------------------------------------------------------------------------
# Netlist
# --------------------------------------------------------------------------

def _num(value: float) -> str:
    text = f"{float(value):.12g}"
    return "0" if text == "-0" else text


def build_netlist(
    params: Mapping[str, Any],
    analysis: str,
    *,
    amplitude_v: float = DEFAULT_AMPLITUDE_V,
    frequency_hz: float = DEFAULT_FREQUENCY_HZ,
    model: Mapping[str, Any] = DEFAULT_MODEL,
) -> str:
    """สร้าง netlist วงจร CE Voltage Divider สำหรับ analysis ที่กำหนด"""
    if analysis not in ANALYSES:
        raise SpiceError(f"ไม่รู้จักการวิเคราะห์ '{analysis}' (รองรับ: {', '.join(ANALYSES)})")

    merged = {**REFERENCE, **{k: v for k, v in params.items() if k in CIRCUIT_FIELDS}}
    model_name = str(model.get("name", DEFAULT_MODEL_NAME))

    lines = [
        f"* BJT CE Voltage Divider — Lab 04 ({analysis})",
        "* พารามิเตอร์ทั้งหมดเป็นหน่วย SI (V, ohm, F)",
        f"VCC vcc 0 {_num(merged['vcc'])}",
        f"VIN in 0 DC 0 AC 1 SIN(0 {_num(amplitude_v)} {_num(frequency_hz)})",
        f"CIN in vb {_num(merged['cin'])}",
        f"R1 vcc vb {_num(merged['r1'])}",
        f"R2 vb 0 {_num(merged['r2'])}",
        f"RC vcc vc {_num(merged['rc'])}",
    ]
    if float(merged["re"]) > 0:
        lines.append(f"RE ve 0 {_num(merged['re'])}")
    lines.extend(
        [
            f"Q1 vc vb ve {model_name}",
            f"COUT vc out {_num(merged['cout'])}",
            f"RL out 0 {_num(merged['rl'])}",
            (
                f".model {model_name} NPN(BF={_num(model.get('bf', 100.0))} "
                f"IS={_num(model.get('is', 1e-14))} VAF={_num(model.get('vaf', 100.0))})"
            ),
        ]
    )

    if analysis == "op":
        lines.append(".save all @q1[ic] @q1[ib] @q1[ie]")
        lines.append(".op")
    elif analysis == "ac":
        lines.append(f".ac {AC_SWEEP}")
    else:
        lines.append(f".tran {TRAN_STEP} {TRAN_STOP}")

    lines.append(".end")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Rawfile parsing
# --------------------------------------------------------------------------

def _to_value(text: str, complex_flag: bool) -> complex | float:
    text = text.strip()
    if not text:
        raise SpiceError("พบค่าตัวเลขว่างใน rawfile")
    if "," in text:
        real, imag = text.split(",", 1)
        value = complex(float(real), float(imag))
        return value if complex_flag else value.real
    try:
        return float(text)
    except ValueError as exc:
        raise SpiceError("อ่านค่าตัวเลขจาก rawfile ไม่ได้", detail=text) from exc


def parse_raw(text: str) -> dict:
    """แปลง ASCII rawfile ของ ngspice เป็น dict ที่ใช้งานต่อได้"""
    if not isinstance(text, str) or "Values:" not in text:
        raise SpiceError("rawfile ไม่มีส่วน Values: — อาจรันไม่สำเร็จ")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    header: dict[str, str] = {}
    variables: list[str] = []
    values_at = None
    in_variables = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "Values:":
            values_at = index
            break
        if stripped == "Variables:":
            in_variables = True
            continue
        if in_variables:
            if not stripped:
                continue
            parts = stripped.split()
            if len(parts) >= 2:
                variables.append(parts[1])
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            header[key.strip()] = value.strip()

    if values_at is None:
        raise SpiceError("rawfile ไม่มีส่วน Values:")
    if not variables:
        raise SpiceError("rawfile ไม่มีรายการตัวแปร")

    flags = header.get("Flags", "real").lower()
    complex_flag = "complex" in flags

    points: list[list[complex | float]] = []
    current: list[str] | None = None
    for line in lines[values_at + 1:]:
        if not line.strip():
            continue
        if line[0] not in " \t":
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            current = [parts[1]]
            points.append(current)  # type: ignore[arg-type]
        elif current is not None:
            current.append(line.strip())

    if not points:
        raise SpiceError("rawfile ไม่มีข้อมูลจุดทดสอบ")

    parsed_points: list[list[complex | float]] = []
    for row in points:
        if len(row) != len(variables):
            raise SpiceError(
                "จำนวนค่าต่อจุดไม่ตรงกับจำนวนตัวแปร",
                detail=f"expected={len(variables)} got={len(row)}",
            )
        parsed_points.append([_to_value(cell, complex_flag) for cell in row])

    try:
        declared_points = int(header.get("No. Points", len(parsed_points)))
    except ValueError:
        declared_points = len(parsed_points)
    if declared_points != len(parsed_points):
        raise SpiceError("จำนวนจุดใน rawfile ไม่ตรงกับที่ประกาศไว้")

    return {
        "title": header.get("Title", ""),
        "command": header.get("Command", ""),
        "plotname": header.get("Plotname", ""),
        "flags": flags,
        "variables": variables,
        "points": parsed_points,
    }


def read_raw(path: str) -> dict:
    """อ่าน rawfile จากดิสก์"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return parse_raw(handle.read())
    except OSError as exc:
        raise SpiceError("อ่านไฟล์ผลลัพธ์ของ ngspice ไม่ได้", detail=str(exc)) from exc


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _lookup(raw: dict, names: tuple[str, ...]) -> complex | float | None:
    """หาค่าจากชื่อตัวแปร (ไม่สนตัวพิมพ์) ในจุดแรก"""
    variables = raw["variables"]
    lowered = [name.lower() for name in variables]
    for candidate in names:
        key = candidate.lower()
        if key in lowered:
            return raw["points"][0][lowered.index(key)]
    return None


def _magnitude(value: complex | float | None) -> float:
    if value is None:
        return float("nan")
    if isinstance(value, complex):
        return abs(value)
    return abs(float(value))


def extract_op(raw: dict) -> dict[str, float]:
    """ดึง DC operating point จาก rawfile ของ .op"""
    if not raw.get("points"):
        raise SpiceError("ผล .op ว่างเปล่า")

    vb = _lookup(raw, ("v(vb)",))
    ve = _lookup(raw, ("v(ve)",))
    vc = _lookup(raw, ("v(vc)",))
    if vb is None or ve is None or vc is None:
        missing = [
            name
            for name, value in (("VB", vb), ("VE", ve), ("VC", vc))
            if value is None
        ]
        raise SpiceError("ผล .op ไม่มีแรงดันที่ต้องการ: " + ", ".join(missing))

    ic = _lookup(raw, ("i(@q1[ic])", "@q1[ic]", "ic"))
    ib = _lookup(raw, ("i(@q1[ib])", "@q1[ib]", "ib"))
    ie = _lookup(raw, ("i(@q1[ie])", "@q1[ie]", "ie"))
    if ic is None or ib is None or ie is None:
        raise SpiceError("ผล .op ไม่มีกระแสของทรานซิสเตอร์ (ต้องมี .save @q1[...])")

    vb_f, ve_f, vc_f = float(vb), float(ve), float(vc)
    return {
        "vb": vb_f,
        "ve": ve_f,
        "vc": vc_f,
        "vce": vc_f - ve_f,
        "ib": abs(float(ib)),
        "ic": abs(float(ic)),
        "ie": abs(float(ie)),
    }


def _real_vector(raw: dict, names: tuple[str, ...]) -> list[complex]:
    variables = raw["variables"]
    lowered = [name.lower() for name in variables]
    for candidate in names:
        key = candidate.lower()
        if key in lowered:
            index = lowered.index(key)
            return [complex(row[index]) for row in raw["points"]]
    raise SpiceError("ผล .ac/.tran ไม่มีตัวแปร: " + names[0])


def extract_ac(raw: dict) -> dict[str, list[float]]:
    """ดึง frequency / |gain| / dB / phase จาก rawfile ของ .ac"""
    if not raw.get("points"):
        raise SpiceError("ผล .ac ว่างเปล่า")

    freq = _real_vector(raw, ("frequency", "f"))
    vout = _real_vector(raw, ("v(out)",))
    vin_values = None
    try:
        vin_values = _real_vector(raw, ("v(in)",))
    except SpiceError:
        vin_values = None

    frequencies: list[float] = []
    gain_mag: list[float] = []
    gain_db: list[float] = []
    phase_deg: list[float] = []

    for index, freq_value in enumerate(freq):
        out_value = vout[index]
        if vin_values is not None:
            vin_value = vin_values[index]
            ratio = out_value / vin_value if abs(vin_value) > 1e-15 else out_value
        else:
            ratio = out_value
        magnitude = abs(ratio)
        frequencies.append(float(freq_value.real))
        gain_mag.append(magnitude)
        gain_db.append(20.0 * math.log10(magnitude) if magnitude > 0 else -300.0)
        phase_deg.append(math.degrees(math.atan2(ratio.imag, ratio.real)))

    return {
        "frequency": frequencies,
        "gain_mag": gain_mag,
        "gain_db": gain_db,
        "phase_deg": phase_deg,
    }


def extract_tran(raw: dict) -> dict[str, list[float]]:
    """ดึง time / Vin / Vout จาก rawfile ของ .tran"""
    if not raw.get("points"):
        raise SpiceError("ผล .tran ว่างเปล่า")

    time_values = _real_vector(raw, ("time",))
    vin_values = _real_vector(raw, ("v(in)",))
    vout_values = _real_vector(raw, ("v(out)",))

    return {
        "time": [value.real for value in time_values],
        "vin": [value.real for value in vin_values],
        "vout": [value.real for value in vout_values],
    }


EXTRACTORS = {"op": extract_op, "ac": extract_ac, "tran": extract_tran}


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def _tail(text: str, limit: int = _MAX_DETAIL) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "…" + text[-limit:]


def _warnings_from_log(log: str) -> list[str]:
    warnings = []
    for line in (log or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("warning"):
            warnings.append(stripped)
    return warnings


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def run(
    analysis: str,
    params: Mapping[str, Any] | None = None,
    *,
    amplitude_v: float = DEFAULT_AMPLITUDE_V,
    frequency_hz: float = DEFAULT_FREQUENCY_HZ,
    timeout_s: float = TIMEOUT_S,
) -> dict:
    """รัน ngspice หนึ่งครั้ง แล้วคืนผลลัพธ์ที่ parse แล้ว

    Raises:
        SpiceError: เมื่อไม่พบ ngspice, ค่าไม่ถูกต้อง, process ล้มเหลว,
            หมดเวลา, หรือผลลัพธ์ว่าง/อ่านไม่ได้
    """
    if analysis not in ANALYSES:
        raise SpiceError(f"ไม่รู้จักการวิเคราะห์ '{analysis}'")

    merged = {**REFERENCE}
    if params:
        merged.update({k: v for k, v in params.items() if k in CIRCUIT_FIELDS})

    validate_params(merged, amplitude_v=amplitude_v, frequency_hz=frequency_hz)

    exe = find_ngspice()
    if not exe:
        raise SpiceError(
            "ไม่พบ ngspice ในเครื่อง — ติดตั้งแล้วตั้งค่า NGSPICE_BIN "
            "หรือเพิ่มโฟลเดอร์ bin ของ ngspice ลง PATH"
        )

    netlist = build_netlist(
        merged,
        analysis,
        amplitude_v=amplitude_v,
        frequency_hz=frequency_hz,
    )

    env = dict(os.environ)
    exe_dir = os.path.dirname(os.path.abspath(exe))
    env["PATH"] = exe_dir + os.pathsep + env.get("PATH", "")

    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    with tempfile.TemporaryDirectory(prefix="bjt-spice-") as workdir:
        deck_path = os.path.join(workdir, "circuit.cir")
        raw_path = os.path.join(workdir, "result.raw")
        log_path = os.path.join(workdir, "ngspice.log")
        with open(deck_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(netlist)

        command = [exe, "-b", "-o", log_path, "-r", raw_path, deck_path]
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
                **kwargs,
            )
        except subprocess.TimeoutExpired as exc:
            raise SpiceError(
                f"ngspice ใช้เวลานานเกิน {timeout_s:g} วินาที — หมดเวลารอผลลัพธ์"
            ) from exc
        except OSError as exc:
            raise SpiceError("เรียก ngspice ไม่สำเร็จ", detail=str(exc)) from exc
        duration_ms = (time.perf_counter() - started) * 1000.0

        log_text = _read_text(log_path) or _tail(
            (completed.stdout or "") + (completed.stderr or "")
        )
        if completed.returncode != 0:
            raise SpiceError(
                f"ngspice exited with code {completed.returncode}",
                detail=_tail(log_text),
            )

        raw = read_raw(raw_path)

        if not raw.get("variables") or not raw.get("points"):
            raise SpiceError(
                "ngspice ไม่ได้คืนข้อมูลผลลัพธ์",
                detail=_tail(log_text),
            )

        try:
            data = EXTRACTORS[analysis](raw)
        except SpiceError as exc:
            raise SpiceError(exc.message, detail=_tail(log_text or exc.detail)) from exc

    return {
        "ok": True,
        "analysis": analysis,
        "engine": engine_version_from_command(raw.get("command", "")),
        "engine_path": exe,
        "model": DEFAULT_MODEL_NAME,
        "plotname": raw.get("plotname", ""),
        "netlist": netlist,
        "parameters": {key: merged[key] for key in CIRCUIT_FIELDS},
        "amplitude_v": float(amplitude_v),
        "frequency_hz": float(frequency_hz),
        "warnings": _warnings_from_log(log_text),
        "log": _tail(log_text),
        "data": data,
        "duration_ms": round(duration_ms, 2),
    }
