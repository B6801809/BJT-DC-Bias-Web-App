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


if __name__ == "__main__":
    unittest.main()
