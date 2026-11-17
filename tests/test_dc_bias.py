"""Unit tests for BJT DC Bias engineering calculations."""

from __future__ import annotations

import os
import sys
import unittest

# ทำให้ import dc_bias ได้เมื่อรัน unittest จากโฟลเดอร์ tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dc_bias import (  # noqa: E402
    calculate_dc_bias,
    calculate_emitter_bias,
    calculate_fixed_bias,
)


class TestDCBiasCalculations(unittest.TestCase):
    """ทดสอบตรรกะวิศวกรรมใน dc_bias.calculate_dc_bias"""

    def setUp(self):
        # ค่าทดลองเริ่มต้น: VCC=12V, R1=100kΩ, R2=22kΩ, RC=2.2kΩ, RE=1kΩ, β=100, VBE=0.70V
        self.params = dict(
            vcc=12.0,
            r1=100_000.0,
            r2=22_000.0,
            rc=2_200.0,
            re=1_000.0,
            beta=100.0,
            vbe=0.70,
        )

    def test_forward_active_reference_solution(self):
        """ค่าอ้างอิง Forward-Active ต้องตรงกับสมการมือคำนวณ"""
        result = calculate_dc_bias(**self.params)

        self.assertNotIn("error", result)
        self.assertEqual(result["region"], "Forward-Active")
        self.assertIsNone(result["warning"])

        # ค่าอ้างอิงที่คำนวณด้วยสมการ (independently derived)
        self.assertAlmostEqual(result["vth"], 2.163934, places=5)
        self.assertAlmostEqual(result["rth"], 18_032.786885, places=3)
        self.assertAlmostEqual(result["ib"], 12.298581e-6, places=9)
        self.assertAlmostEqual(result["ic"], 1.229858e-3, places=8)
        self.assertAlmostEqual(result["ie"], 1.242157e-3, places=8)
        self.assertAlmostEqual(result["ve"], 1.242157, places=5)
        self.assertAlmostEqual(result["vb"], 1.942157, places=5)
        self.assertAlmostEqual(result["vc"], 9.294312, places=5)
        self.assertAlmostEqual(result["vce"], 8.052155, places=5)

    def test_current_relations(self):
        """IC = β·IB และ IE = (β+1)·IB"""
        result = calculate_dc_bias(**self.params)

        self.assertAlmostEqual(result["ic"], 100.0 * result["ib"], places=12)
        self.assertAlmostEqual(result["ie"], 101.0 * result["ib"], places=12)
        self.assertAlmostEqual(result["ie"], result["ic"] + result["ib"], places=12)

    def test_cutoff_region(self):
        """VTH ≤ VBE ต้องรายงาน Cutoff และกระแสเป็นศูนย์"""
        params = dict(self.params, r1=1_000_000.0)
        result = calculate_dc_bias(**params)

        self.assertEqual(result["region"], "Cutoff")
        self.assertIsNotNone(result["warning"])
        self.assertEqual(result["ib"], 0.0)
        self.assertEqual(result["ic"], 0.0)
        self.assertEqual(result["ie"], 0.0)

    def test_saturation_warning(self):
        """VCE ต่ำมากต้องรายงาน Saturation พร้อม warning"""
        params = dict(self.params, r1=10_000.0)
        result = calculate_dc_bias(**params)

        self.assertEqual(result["region"], "Saturation")
        self.assertIsNotNone(result["warning"])
        self.assertLess(result["vce"], 0.2)

    def test_invalid_vcc(self):
        result = calculate_dc_bias(**dict(self.params, vcc=0.0))
        self.assertIn("error", result)
        self.assertEqual(result["region"], "Error")

    def test_invalid_resistance(self):
        result = calculate_dc_bias(**dict(self.params, r1=0.0))
        self.assertIn("error", result)

    def test_invalid_beta(self):
        result = calculate_dc_bias(**dict(self.params, beta=0.0))
        self.assertIn("error", result)

    def test_negative_resistance(self):
        result = calculate_dc_bias(**dict(self.params, rc=-1.0))
        self.assertIn("error", result)


class TestFixedBiasCalculations(unittest.TestCase):
    """ทดสอบตรรกะวิศวกรรมของ Fixed Bias (Lab 3 · A2)"""

    def setUp(self):
        # VCC=12V, RB=1MΩ, RC=2.2kΩ, β=100, VBE=0.70V
        self.params = dict(vcc=12.0, rb=1_000_000.0, rc=2_200.0, beta=100.0, vbe=0.70)

    def test_a2_reference_solution(self):
        """A2: ค่าอ้างอิงอิสระต้องตรงกับสมการมือคำนวณ"""
        result = calculate_fixed_bias(**self.params)

        self.assertNotIn("error", result)
        self.assertEqual(result["region"], "Forward-Active")
        self.assertIsNone(result["warning"])
        self.assertAlmostEqual(result["ib"], 11.30e-6, places=9)
        self.assertAlmostEqual(result["ic"], 1.13e-3, places=8)
        self.assertAlmostEqual(result["ie"], 1.1413e-3, places=8)
        self.assertEqual(result["vb"], 0.70)
        self.assertEqual(result["ve"], 0.0)
        self.assertAlmostEqual(result["vc"], 9.514, places=5)
        self.assertAlmostEqual(result["vce"], 9.514, places=5)

    def test_current_relations(self):
        """IC = β·IB และ IE = (β+1)·IB"""
        result = calculate_fixed_bias(**self.params)
        self.assertAlmostEqual(result["ic"], 100.0 * result["ib"], places=12)
        self.assertAlmostEqual(result["ie"], 101.0 * result["ib"], places=12)

    def test_zero_rb_is_error(self):
        """A5 ในโหมด Fixed: RB = 0 ต้องแจ้ง error ไม่ใช่คำนวณต่อ"""
        result = calculate_fixed_bias(**dict(self.params, rb=0.0))
        self.assertIn("error", result)
        self.assertIn("RB ต้องมากกว่า 0", result["error"])
        self.assertEqual(result["region"], "Error")

    def test_saturation_warning(self):
        """VCE ต่ำเกินไปต้องเตือนว่าแบบจำลอง Forward-Active ใช้ไม่ได้"""
        result = calculate_fixed_bias(**dict(self.params, rb=10_000.0))
        self.assertEqual(result["region"], "Saturation")
        self.assertIsNotNone(result["warning"])


class TestEmitterBiasCalculations(unittest.TestCase):
    """ทดสอบตรรกะวิศวกรรมของ Emitter Bias (Lab 3 · A3)"""

    def setUp(self):
        # VCC=12V, RB=1MΩ, RC=2.2kΩ, RE=1kΩ, β=100, VBE=0.70V
        self.params = dict(
            vcc=12.0, rb=1_000_000.0, rc=2_200.0, re=1_000.0, beta=100.0, vbe=0.70
        )

    def test_a3_reference_solution(self):
        """A3: ค่าอ้างอิงอิสระต้องตรงกับสมการมือคำนวณ"""
        result = calculate_emitter_bias(**self.params)

        self.assertNotIn("error", result)
        self.assertEqual(result["region"], "Forward-Active")
        self.assertIsNone(result["warning"])
        self.assertAlmostEqual(result["ib"], 10.263397e-6, places=9)
        self.assertAlmostEqual(result["ic"], 1.026340e-3, places=8)
        self.assertAlmostEqual(result["ie"], 1.036603e-3, places=8)
        self.assertAlmostEqual(result["ve"], 1.036603, places=5)
        self.assertAlmostEqual(result["vb"], 1.736603, places=5)
        self.assertAlmostEqual(result["vc"], 9.742053, places=5)
        self.assertAlmostEqual(result["vce"], 8.705450, places=5)

    def test_re_increases_base_resistance_seen_by_base(self):
        """A4: เพิ่ม RE ต้องลด IB และ IC (แต่ตรวจเฉพาะสมการในโหมดนี้)"""
        bigger = calculate_emitter_bias(**dict(self.params, re=2_000.0))
        base = calculate_emitter_bias(**self.params)
        self.assertLess(bigger["ib"], base["ib"])
        self.assertLess(bigger["ic"], base["ic"])

    def test_current_relations(self):
        """IC = β·IB และ IE = (β+1)·IB"""
        result = calculate_emitter_bias(**self.params)
        self.assertAlmostEqual(result["ic"], 100.0 * result["ib"], places=12)
        self.assertAlmostEqual(result["ie"], 101.0 * result["ib"], places=12)
        self.assertAlmostEqual(result["ve"], result["ie"] * 1_000.0, places=9)

    def test_zero_re_is_error(self):
        """RE = 0 ในโหมด Emitter ต้องแจ้ง error"""
        result = calculate_emitter_bias(**dict(self.params, re=0.0))
        self.assertIn("error", result)
        self.assertIn("RE ต้องมากกว่า 0", result["error"])

    def test_saturation_warning(self):
        """VCE ต่ำเกินไปต้องเตือนว่าแบบจำลอง Forward-Active ใช้ไม่ได้"""
        result = calculate_emitter_bias(**dict(self.params, rb=10_000.0))
        self.assertEqual(result["region"], "Saturation")
        self.assertIsNotNone(result["warning"])


if __name__ == "__main__":
    unittest.main()
