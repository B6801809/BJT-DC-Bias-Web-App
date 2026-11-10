"""Engineering calculations for BJT DC Bias (Voltage-Divider Bias)."""

from __future__ import annotations

# ค่า VCE ที่ต่ำกว่านี้ถือว่าเข้าใกล้/อยู่ในย่าน Saturation สำหรับแบบจำลองง่าย ๆ
VCE_SATURATION_LIMIT = 0.2


def calculate_dc_bias(
    vcc: float,
    r1: float,
    r2: float,
    rc: float,
    re: float,
    beta: float,
    vbe: float = 0.70,
) -> dict:
    """คำนวณ DC Operating Point ของ NPN Common-Emitter Voltage-Divider Bias.

    สมมติฐาน: Forward-Active (β คงที่, VBE คงที่)

    Args:
        vcc: แรงดันจ่าย VCC [V]
        r1: ตัวต้านทาน R1 (VCC–Base) [Ω]
        r2: ตัวต้านทาน R2 (Base–Ground) [Ω]
        rc: ตัวต้านทาน RC (VCC–Collector) [Ω]
        re: ตัวต้านทาน RE (Emitter–Ground) [Ω]
        beta: อัตราขยายกระแส β (HFE)
        vbe: แรงดัน Base–Emitter [V] (ค่าเริ่มต้น 0.70 V)

    Returns:
        dict:
            vth, rth           – Thevenin equivalent ที่มองจาก Base
            vb, ve, vc, vce    – แรงดัน [V]
            ib, ic, ie         – กระแส [A]
            region             – Forward-Active / Cutoff / Saturation / Error
            warning            – คำเตือนเมื่อแบบจำลอง Forward-Active ใช้ไม่ได้
            error              – ข้อความผิดพลาดของอินพุต (ถ้ามี)
    """
    errors: list[str] = []
    if vcc <= 0:
        errors.append("VCC ต้องมากกว่า 0")
    if r1 <= 0:
        errors.append("R1 ต้องมากกว่า 0")
    if r2 <= 0:
        errors.append("R2 ต้องมากกว่า 0")
    if rc < 0:
        errors.append("RC ต้องไม่ติดลบ")
    if re < 0:
        errors.append("RE ต้องไม่ติดลบ")
    if beta <= 0:
        errors.append("β ต้องมากกว่า 0")
    if vbe <= 0:
        errors.append("VBE ต้องมากกว่า 0")

    if errors:
        return {
            "error": " | ".join(errors),
            "region": "Error",
            "warning": None,
        }

    # --- Thevenin equivalent ของตัวแบ่งแรงดันที่ Base ---
    vth = vcc * r2 / (r1 + r2)
    rth = r1 * r2 / (r1 + r2)

    # --- กรณี Cutoff: แรงดัน Thevenin ไม่พอเปิดรอยต่อ Base–Emitter ---
    if vth <= vbe:
        return {
            "vth": vth,
            "rth": rth,
            "vb": vth,
            "ve": 0.0,
            "vc": vcc,
            "vce": vcc,
            "ib": 0.0,
            "ic": 0.0,
            "ie": 0.0,
            "region": "Cutoff",
            "warning": (
                f"VTH = {vth:.3f} V ≤ VBE = {vbe:.3f} V "
                "ทรานซิสเตอร์อยู่ในย่าน Cutoff — แบบจำลอง Forward-Active ใช้ไม่ได้"
            ),
        }

    # --- Forward-Active approximation ---
    ib = (vth - vbe) / (rth + (beta + 1) * re)
    ic = beta * ib
    ie = (beta + 1) * ib
    ve = ie * re
    vb = ve + vbe
    vc = vcc - ic * rc
    vce = vc - ve

    region = "Forward-Active"
    warning = None

    # VCE เข้าใกล้/ต่ำกว่า VCE(sat) หรือติดลบ => ไม่ใช่ Forward-Active จริง
    if vce < VCE_SATURATION_LIMIT:
        region = "Saturation"
        warning = (
            f"VCE = {vce:.3f} V ต่ำกว่า {VCE_SATURATION_LIMIT:.3f} V "
            "อาจอยู่ในย่าน Saturation — ค่าที่ได้จากสมมติฐาน Forward-Active "
            "ไม่ควรใช้เป็นผลลัพธ์ที่แม่นยำ"
        )

    return {
        "vth": vth,
        "rth": rth,
        "vb": vb,
        "ve": ve,
        "vc": vc,
        "vce": vce,
        "ib": ib,
        "ic": ic,
        "ie": ie,
        "region": region,
        "warning": warning,
    }


if __name__ == "__main__":
    # ตัวอย่างค่าทดลองเริ่มต้น: VCC=12V, R1=100kΩ, R2=22kΩ, RC=2.2kΩ, RE=1kΩ, β=100, VBE=0.70V
    test_result = calculate_dc_bias(
        vcc=12.0,
        r1=100_000.0,
        r2=22_000.0,
        rc=2_200.0,
        re=1_000.0,
        beta=100,
        vbe=0.70,
    )

    print("=" * 50)
    print("DC Bias Calculation (ตัวอย่างการทดสอบ)")
    print("=" * 50)
    print("Input: VCC=12V, R1=100kΩ, R2=22kΩ, RC=2.2kΩ, RE=1kΩ, β=100, VBE=0.70V")
    print()

    if "error" in test_result:
        print(f"ERROR: {test_result['error']}")
    else:
        print("ผลการคำนวณ DC Bias:")
        print(f"  IB  = {test_result['ib'] * 1e6:.2f} μA")
        print(f"  IC  = {test_result['ic'] * 1e3:.2f} mA")
        print(f"  IE  = {test_result['ie'] * 1e3:.2f} mA")
        print(f"  VB  = {test_result['vb']:.3f} V")
        print(f"  VE  = {test_result['ve']:.3f} V")
        print(f"  VC  = {test_result['vc']:.3f} V")
        print(f"  VCE = {test_result['vce']:.3f} V")
        print(f"  โซนการทำงาน: {test_result['region']}")
        if test_result["warning"]:
            print(f"  Warning: {test_result['warning']}")

    print("=" * 50)
