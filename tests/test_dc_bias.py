"""Unit tests for BJT DC Bias engineering calculations."""

from __future__ import annotations

import os
import sys
import unittest

# ทำให้ import dc_bias ได้เมื่อรัน unittest จากโฟลเดอร์ tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dc_bias import calculate_dc_bias  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
