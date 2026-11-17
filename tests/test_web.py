"""Flask HTTP route tests for BJT DC Bias Web App."""

from __future__ import annotations

import os
import sys
import unittest

# ทำให้ import app ได้เมื่อรัน unittest จาก root ของโปรเจกต์
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402


VALID_FORM = {
    "vcc": "12",
    "r1": "100",   # kΩ
    "r2": "22",    # kΩ
    "rc": "2.2",   # kΩ
    "re": "1",     # kΩ
    "beta": "100",
    "vbe": "0.70",
}


class TestFlaskRoutes(unittest.TestCase):
    """ทดสอบ HTTP routes ด้วย Flask test client"""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_index_get_returns_form(self):
        """A1: GET / ต้องได้ HTTP 200 และมีฟอร์ม"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("BJT DC Bias", body)
        self.assertIn("Calculate DC Bias", body)
        self.assertIn('name="vcc"', body)

    def test_index_get_includes_circuit_schematic(self):
        """GET / ต้องแสดงภาพวงจร SVG พร้อมค่าตัวอย่าง"""
        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertIn("<svg", body)
        self.assertIn("figure-svg", body)
        self.assertIn("Q1 (NPN)", body)

    def test_calculate_renders_all_figures(self):
        """POST / ต้องแสดงภาพวงจร, load line และระดับแรงดัน"""
        response = self.client.post("/", data=VALID_FORM)
        body = response.get_data(as_text=True)
        self.assertEqual(body.count("<svg"), 3)
        self.assertIn("DC Load Line", body)
        self.assertIn("Q: VCE", body)
        self.assertIn("VB = 1.942 V", body)
        self.assertIn("IC = 1.23 mA", body)

    def test_calculate_valid_form(self):
        """A2: POST / ด้วยค่าถูกต้อง ต้องคำนวณและแสดงผลจาก Backend"""
        response = self.client.post("/", data=VALID_FORM)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Forward-Active", body)
        self.assertIn("mA", body)
        # ค่า IC ที่คำนวณได้จาก Python ต้องปรากฏ (ไม่ใช่ค่าฮาร์ดโค้ดใน HTML)
        self.assertIn("1.23", body)

    def test_calculate_uses_kilo_ohm_conversion(self):
        """A3: ต้องแปลง kΩ -> Ω ถูกต้อง (ผลต้องไม่เป็น Saturation)"""
        response = self.client.post("/", data=VALID_FORM)
        body = response.get_data(as_text=True)
        self.assertIn("Forward-Active", body)
        self.assertNotIn("Saturation", body)

    def test_missing_fields(self):
        """A4: ข้อมูลไม่ครบต้องแจ้ง error ชัดเจนและหน้าไม่ล้ม"""
        response = self.client.post("/", data={"vcc": "12"})
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("กรุณากรอกค่าให้ครบ", body)

    def test_non_numeric_input(self):
        """A4: ข้อมูลไม่ใช่ตัวเลขต้องแจ้ง error ชัดเจน"""
        response = self.client.post("/", data=dict(VALID_FORM, vcc="abc"))
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("ต้องเป็นตัวเลข", body)

    def test_zero_resistance_input(self):
        """A4: R ≤ 0 ต้องแสดง error จาก engineering validation"""
        response = self.client.post("/", data=dict(VALID_FORM, r1="0"))
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("R1 ต้องมากกว่า 0", body)

    def test_api_calculate_json(self):
        """API JSON ต้องคืนผลลัพธ์เป็น JSON"""
        response = self.client.post("/api/calculate", json=VALID_FORM)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["region"], "Forward-Active")
        self.assertAlmostEqual(data["ic"], 1.229858e-3, places=8)

    def test_same_result_with_different_input_units(self):
        """A3: หน่วยขาเข้าต่างกัน แต่ค่าที่กรอกเท่ากัน ต้องได้ผลเหมือนกัน"""
        in_ohm = {
            "vcc": "12", "vcc_unit": "V",
            "vbe": "0.70", "vbe_unit": "V",
            "r1": "100000", "r1_unit": "Ω",
            "r2": "22000", "r2_unit": "Ω",
            "rc": "2200", "rc_unit": "Ω",
            "re": "1000", "re_unit": "Ω",
            "beta": "100",
        }
        response = self.client.post("/", data=in_ohm)
        body = response.get_data(as_text=True)
        self.assertIn("Forward-Active", body)
        self.assertIn("1.23", body)      # IC เท่าเดิม
        self.assertIn("8.052", body)     # VCE เท่าเดิม

    def test_millivolt_input_is_converted(self):
        """ค่าแรงดันที่กรอกเป็น mV ต้องถูกแปลงเป็น V ก่อนคำนวณ"""
        data = dict(VALID_FORM, vcc="12000", vcc_unit="mV")
        response = self.client.post("/", data=data)
        body = response.get_data(as_text=True)
        self.assertIn("Forward-Active", body)
        self.assertIn("8.052", body)

    def test_display_unit_selection(self):
        """เลือกหน่วยแสดงผลเป็น mV และ µA ต้องเปลี่ยนข้อความที่แสดง"""
        data = dict(VALID_FORM, voltage_display="mV", current_display="µA")
        response = self.client.post("/", data=data)
        body = response.get_data(as_text=True)
        self.assertIn("1942.157 mV", body)
        self.assertIn("1229.858 µA", body)

    def test_api_accepts_unit_fields(self):
        """API ต้องรับหน่วยขาเข้าและคืนหน่วยที่เลือกไว้"""
        payload = dict(VALID_FORM, r1_unit="Ω", r1="100000")
        response = self.client.post("/api/calculate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["units"]["r1_unit"], "Ω")
        self.assertAlmostEqual(data["ic"], 1.229858e-3, places=8)


FIXED_A2_FORM = {
    "mode": "fixed",
    "vcc": "12",
    "vcc_unit": "V",
    "vbe": "0.70",
    "vbe_unit": "V",
    "rb": "1",
    "rb_unit": "MΩ",
    "rc": "2.2",
    "rc_unit": "kΩ",
    "beta": "100",
}


class TestFixedModeRoutes(unittest.TestCase):
    """Lab 3 · Fixed Bias: เลือกโหมด ตรวจอินพุต และผล A2"""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_fixed_mode_get_shows_only_relevant_fields(self):
        """โหมด Fixed ต้องมีช่อง RB และไม่แสดงช่องของ Divider"""
        response = self.client.get("/?mode=fixed")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="rb"', body)
        self.assertIn('name="rb_unit"', body)
        self.assertNotIn('name="r1"', body)
        self.assertNotIn('name="re"', body)
        self.assertIn('aria-label="วงจร BJT NPN Common-Emitter แบบ Fixed Bias"', body)

    def test_fixed_a2_post(self):
        """A2: RB = 1 MΩ ต้องได้ IC = 1.13 mA และ VCE = 9.514 V"""
        response = self.client.post("/", data=FIXED_A2_FORM)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ผลลัพธ์ DC Bias — Fixed Bias", body)
        self.assertIn("1.13", body)
        self.assertIn("9.514", body)
        self.assertIn("Forward-Active", body)
        self.assertNotIn("VTH = VCC·R2/(R1+R2)", body)

    def test_fixed_a2_api(self):
        """API ต้องเลือกฟังก์ชัน Fixed และไม่ส่งค่าของ Divider กลับมา"""
        response = self.client.post("/api/calculate", json=FIXED_A2_FORM)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["mode"], "fixed")
        self.assertAlmostEqual(data["ib"], 11.30e-6, places=9)
        self.assertAlmostEqual(data["ic"], 1.13e-3, places=8)
        self.assertAlmostEqual(data["vce"], 9.514, places=5)
        self.assertNotIn("vth", data)
        self.assertNotIn("rth", data)

    def test_unknown_mode_is_error(self):
        """โหมดที่ไม่รู้จักต้องแจ้ง error ไม่เดาเป็น Divider"""
        response = self.client.post("/", data=dict(VALID_FORM, mode="unknown"))
        body = response.get_data(as_text=True)
        self.assertIn("ไม่รู้จักโหมด", body)

    def test_fixed_zero_rb_is_error(self):
        """RB = 0 ต้องแจ้ง error จาก engineering validation"""
        response = self.client.post("/", data=dict(FIXED_A2_FORM, rb="0"))
        body = response.get_data(as_text=True)
        self.assertIn("RB ต้องมากกว่า 0", body)


EMITTER_A3_FORM = dict(FIXED_A2_FORM, mode="emitter", re="1", re_unit="kΩ")


class TestEmitterModeRoutes(unittest.TestCase):
    """Lab 3 · Emitter Bias: เลือกโหมด ตรวจอินพุต และผล A3"""

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_emitter_mode_get_shows_rb_and_re(self):
        """โหมด Emitter ต้องมีทั้งช่อง RB และ RE ไม่มีช่อง R1/R2"""
        response = self.client.get("/?mode=emitter")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="rb"', body)
        self.assertIn('name="re"', body)
        self.assertNotIn('name="r1"', body)
        self.assertIn('aria-label="วงจร BJT NPN Common-Emitter แบบ Emitter Bias"', body)

    def test_emitter_a3_post(self):
        """A3: RB = 1 MΩ, RE = 1 kΩ ต้องได้ IC ≈ 1.026 mA และ VCE ≈ 8.705 V"""
        response = self.client.post("/", data=EMITTER_A3_FORM)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ผลลัพธ์ DC Bias — Emitter Bias", body)
        self.assertIn("8.705", body)
        self.assertIn("10.26", body)
        self.assertIn("Forward-Active", body)
        self.assertNotIn("VTH = VCC·R2/(R1+R2)", body)

    def test_emitter_a3_api(self):
        """API ต้องเลือกฟังก์ชัน Emitter และคำนวณผลของ RE ด้วย"""
        response = self.client.post("/api/calculate", json=EMITTER_A3_FORM)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["mode"], "emitter")
        self.assertAlmostEqual(data["ib"], 10.263397e-6, places=9)
        self.assertAlmostEqual(data["ic"], 1.026340e-3, places=8)
        self.assertAlmostEqual(data["ve"], 1.036603, places=5)
        self.assertAlmostEqual(data["vce"], 8.705450, places=5)
        self.assertNotIn("vth", data)

    def test_emitter_zero_re_is_error(self):
        """RE = 0 ในโหมด Emitter ต้องแจ้ง error จาก engineering validation"""
        response = self.client.post("/", data=dict(EMITTER_A3_FORM, re="0"))
        body = response.get_data(as_text=True)
        self.assertIn("RE ต้องมากกว่า 0", body)


if __name__ == "__main__":
    unittest.main()
