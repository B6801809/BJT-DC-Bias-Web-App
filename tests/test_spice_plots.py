"""Tests for the pure-Python SVG chart helpers (no matplotlib, no Flask)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spice_plots as sp  # noqa: E402

AC_DATA = {
    "frequency": [10.0, 100.0, 1000.0, 10000.0, 1e6],
    "gain_mag": [1.726, 2.4, 2.1, 1.1, 0.02],
    "gain_db": [4.74, 7.6, 6.44, 0.83, -34.0],
    "phase_deg": [-166.7, -175.2, -179.9, -160.0, -95.0],
}

TRAN_DATA = {
    "time": [0.0, 0.00025, 0.0005, 0.00075, 0.001],
    "vin": [0.0, 0.01, 0.0, -0.01, 0.0],
    "vout": [0.0, -0.0172, 0.0, 0.0172, 0.0],
}


class TestBodeSvg(unittest.TestCase):
    def setUp(self):
        self.svg = sp.bode_svg(AC_DATA)

    def test_returns_svg_document(self):
        self.assertIsInstance(self.svg, str)
        self.assertTrue(self.svg.startswith("<svg"))
        self.assertTrue(self.svg.rstrip().endswith("</svg>"))

    def test_has_axis_labels_and_legend(self):
        for text in ("Frequency (Hz)", "Gain (dB)", "Phase (°)", "|Vout/Vin|"):
            self.assertIn(text, self.svg)

    def test_draws_two_traces(self):
        self.assertEqual(self.svg.count("<polyline"), 2)

    def test_has_decade_grid_and_svg_namespace(self):
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', self.svg)
        self.assertIn("1000", self.svg)  # ป้ายหลักสิบ/ร้อย/พัน

    def test_no_non_finite_text(self):
        self.assertNotIn("nan", self.svg.lower())
        self.assertNotIn("inf", self.svg.lower())

    def test_empty_data_renders_placeholder(self):
        svg = sp.bode_svg({"frequency": [], "gain_db": [], "phase_deg": []})
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("ไม่มีข้อมูล", svg)

    def test_ignores_non_finite_samples(self):
        data = {
            "frequency": [10.0, 100.0, 1000.0],
            "gain_db": [float("nan"), 3.0, float("inf")],
            "phase_deg": [-10.0, float("-inf"), 10.0],
        }
        svg = sp.bode_svg(data)
        self.assertNotIn("nan", svg.lower())
        self.assertNotIn("inf", svg.lower())


class TestWaveformSvg(unittest.TestCase):
    def setUp(self):
        self.svg = sp.waveform_svg(TRAN_DATA)

    def test_returns_svg_document(self):
        self.assertTrue(self.svg.startswith("<svg"))
        self.assertTrue(self.svg.rstrip().endswith("</svg>"))

    def test_has_labels_and_two_traces(self):
        for text in ("Time (ms)", "Vin", "Vout", "Voltage (V)"):
            self.assertIn(text, self.svg)
        self.assertEqual(self.svg.count("<polyline"), 2)

    def test_empty_data_renders_placeholder(self):
        svg = sp.waveform_svg({"time": [], "vin": [], "vout": []})
        self.assertIn("ไม่มีข้อมูล", svg)

    def test_no_non_finite_text(self):
        data = {
            "time": [0.0, 1e-3, 2e-3],
            "vin": [0.0, float("nan"), 0.0],
            "vout": [float("inf"), 0.0, 0.0],
        }
        svg = sp.waveform_svg(data)
        self.assertNotIn("nan", svg.lower())
        self.assertNotIn("inf", svg.lower())


if __name__ == "__main__":
    unittest.main()
