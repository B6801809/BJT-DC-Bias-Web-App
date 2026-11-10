"""Flask Web Application สำหรับ BJT DC Bias Calculator (Voltage-Divider Bias)."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from dc_bias import calculate_dc_bias

app = Flask(__name__)

# ฟอร์มบนหน้าเว็บรับค่าความต้านทานเป็น kΩ จึงต้องคูณ 1000 เพื่อแปลงเป็น Ω ก่อนคำนวณ
KILO = 1000.0

REQUIRED_FIELDS = ("vcc", "r1", "r2", "rc", "re", "beta")


def _parse_inputs(data) -> dict:
    """อ่านและแปลงค่าอินพุตจาก form หรือ JSON ให้เป็นหน่วย SI (Ω, V, A).

    - vcc, vbe : V
    - r1, r2, rc, re : kΩ จากผู้ใช้ -> แปลงเป็น Ω
    - beta : ไม่มีหน่วย

    Raises:
        ValueError: เมื่อข้อมูลขาดหายหรือไม่ใช่ตัวเลข
    """
    values: dict[str, float] = {}
    missing: list[str] = []

    for field in REQUIRED_FIELDS:
        raw = data.get(field)
        raw = "" if raw is None else str(raw).strip()
        if raw == "":
            missing.append(field.upper())
            continue
        try:
            values[field] = float(raw)
        except ValueError as exc:
            raise ValueError(f"ค่าของ {field.upper()} ต้องเป็นตัวเลข") from exc

    if missing:
        raise ValueError("กรุณากรอกค่าให้ครบ: " + ", ".join(missing))

    vbe_raw = data.get("vbe")
    vbe_raw = "" if vbe_raw is None else str(vbe_raw).strip()
    try:
        vbe = float(vbe_raw) if vbe_raw else 0.70
    except ValueError as exc:
        raise ValueError("ค่าของ VBE ต้องเป็นตัวเลข") from exc

    return {
        "vcc": values["vcc"],
        "r1": values["r1"] * KILO,
        "r2": values["r2"] * KILO,
        "rc": values["rc"] * KILO,
        "re": values["re"] * KILO,
        "beta": values["beta"],
        "vbe": vbe,
    }


@app.route("/", methods=["GET"])
def index():
    """แสดงหน้าฟอร์มรับค่าอินพุต."""
    return render_template("index.html", result=None, form={})


@app.route("/", methods=["POST"])
def calculate():
    """รับค่าจากฟอร์ม คำนวณ DC Bias แล้วแสดงผลในหน้าเดิม."""
    try:
        params = _parse_inputs(request.form)
    except ValueError as exc:
        return render_template(
            "index.html",
            result={"error": str(exc), "region": "Error"},
            form=request.form,
        )

    result = calculate_dc_bias(**params)
    return render_template("index.html", result=result, form=request.form)


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    """API แบบ JSON สำหรับทดสอบอัตโนมัติ (ความต้านทานรับเป็น kΩ เหมือนหน้าเว็บ)."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "ต้องส่ง JSON object", "region": "Error"}), 400

    try:
        params = _parse_inputs(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc), "region": "Error"}), 400

    return jsonify(calculate_dc_bias(**params))


if __name__ == "__main__":
    print("=" * 50)
    print("Starting BJT DC Bias Web App...")
    print("=" * 50)
    print("Open: http://127.0.0.1:5000/")
    print("=" * 50)
    app.run(debug=True, host="127.0.0.1", port=5000)
