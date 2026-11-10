"""Tests for the SVG figure generation (circuit.py)."""

from __future__ import annotations

import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from circuit import (  # noqa: E402
    load_line_current,
    load_line_svg,
    schematic_svg,
    voltage_levels_svg,
)
from dc_bias import calculate_dc_bias  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"


def _text_of(svg: str) -> str:
    """ดึงข้อความทั้งหมดออกจาก SVG"""
    root = ET.fromstring(svg)
    return " ".join(node.text or "" for node in root.iter(f"{SVG_NS}text"))


class TestSchematic(unittest.TestCase):
    def test_schematic_is_valid_xml(self):
        svg = schematic_svg(
            vcc=12.0, r1=100_000.0, r2=22_000.0, rc=2_200.0,
            re=1_000.0, beta=100.0, vbe=0.70,
        )
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))

    def test_schematic_contains_components_and_values(self):
        svg = schematic_svg(
            vcc=12.0, r1=100_000.0, r2=22_000.0, rc=2_200.0,
            re=1_000.0, beta=100.0, vbe=0.70,
        )
        text = _text_of(svg)
        for expected in ("R1", "R2", "RC", "RE", "Q1", "VCC = 12 V", "100 kΩ", "22 kΩ", "2.2 kΩ"):
            self.assertIn(expected, text)

    def test_schematic_shows_node_voltages(self):
        svg = schematic_svg(
            vcc=12.0, r1=100_000.0, r2=22_000.0, rc=2_200.0,
            re=1_000.0, beta=100.0, vbe=0.70,
            vb=1.942, ve=1.242, vc=9.294, ic=1.23e-3,
        )
        text = _text_of(svg)
        self.assertIn("VB = 1.942 V", text)
        self.assertIn("VE = 1.242 V", text)
        self.assertIn("VC = 9.294 V", text)
        self.assertIn("IC = 1.23 mA", text)


class TestLoadLine(unittest.TestCase):
    def test_load_line_is_valid_xml(self):
        svg = load_line_svg(
            vcc=12.0, rc=2_200.0, re=1_000.0, beta=100.0,
            ib=12.298581e-6, ic=1.229858e-3, vce=8.052155,
        )
        ET.fromstring(svg)

    def test_load_line_contains_labels(self):
        svg = load_line_svg(
            vcc=12.0, rc=2_200.0, re=1_000.0, beta=100.0,
            ib=12.298581e-6, ic=1.229858e-3, vce=8.052155,
        )
        text = _text_of(svg)
        self.assertIn("DC Load Line", text)
        self.assertIn("IC = β·IB", text)
        self.assertIn("Q:", text)

    def test_q_point_lies_on_load_line(self):
        """จุด Q ที่คำนวณได้ต้องอยู่บน DC load line ของวงจร"""
        params = dict(
            vcc=12.0, r1=100_000.0, r2=22_000.0, rc=2_200.0,
            re=1_000.0, beta=100.0, vbe=0.70,
        )
        result = calculate_dc_bias(**params)
        ic_on_line = load_line_current(
            params["vcc"], params["rc"], params["re"], params["beta"], result["vce"]
        )
        self.assertAlmostEqual(result["ic"], ic_on_line, places=9)

    def test_load_line_current_endpoints(self):
        # ที่ VCE = 0 กระแสสูงสุดเท่ากับ VCC / (RC + RE·(β+1)/β)
        ic0 = load_line_current(12.0, 2_200.0, 1_000.0, 100.0, 0.0)
        self.assertAlmostEqual(ic0, 12.0 / (2_200.0 + 1_000.0 * 101 / 100), places=9)
        # ที่ VCE = VCC กระแสเป็นศูนย์
        self.assertAlmostEqual(load_line_current(12.0, 2_200.0, 1_000.0, 100.0, 12.0), 0.0)

    def test_cutoff_marks_zero_current(self):
        svg = load_line_svg(
            vcc=12.0, rc=2_200.0, re=1_000.0, beta=100.0,
            ib=0.0, ic=0.0, vce=12.0, region="Cutoff",
        )
        text = _text_of(svg)
        self.assertIn("Cutoff", text)
        self.assertIn("นอกย่าน Forward-Active", text)


class TestVoltageLevels(unittest.TestCase):
    def test_levels_is_valid_xml_and_contains_nodes(self):
        svg = voltage_levels_svg(vcc=12.0, vc=9.294, vb=1.942, ve=1.242, vce=8.052)
        ET.fromstring(svg)
        text = _text_of(svg)
        self.assertIn("VC", text)
        self.assertIn("VB", text)
        self.assertIn("VE", text)
        self.assertIn("9.294 V", text)


if __name__ == "__main__":
    unittest.main()
