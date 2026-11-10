"""Tests for unit conversion and formatting (units.py)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from units import (  # noqa: E402
    AUTO,
    auto_unit,
    format_number,
    format_value,
    split_value,
    to_si,
)


class TestConversion(unittest.TestCase):
    def test_resistance_to_si(self):
        self.assertAlmostEqual(to_si(100, "resistance", "kΩ"), 100_000.0)
        self.assertAlmostEqual(to_si(100_000, "resistance", "Ω"), 100_000.0)
        self.assertAlmostEqual(to_si(2.2, "resistance", "MΩ"), 2_200_000.0)

    def test_voltage_to_si(self):
        self.assertAlmostEqual(to_si(12, "voltage", "V"), 12.0)
        self.assertAlmostEqual(to_si(12_000, "voltage", "mV"), 12.0)

    def test_unknown_unit_raises(self):
        with self.assertRaises(ValueError):
            to_si(1, "resistance", "หน่วยเท็ม")

    def test_auto_unit_selection(self):
        self.assertEqual(auto_unit(12.0, "voltage"), "V")
        self.assertEqual(auto_unit(0.012, "voltage"), "mV")
        self.assertEqual(auto_unit(1.2e-3, "current"), "mA")
        self.assertEqual(auto_unit(1.2e-6, "current"), "µA")
        self.assertEqual(auto_unit(100_000.0, "resistance"), "kΩ")
        self.assertEqual(auto_unit(2.2e6, "resistance"), "MΩ")


class TestFormatting(unittest.TestCase):
    def test_format_value_auto(self):
        self.assertEqual(format_value(1.942153, "voltage", AUTO), "1.942 V")
        self.assertEqual(format_value(1.229858e-3, "current", AUTO), "1.23 mA")
        self.assertEqual(format_value(12.298581e-6, "current", AUTO), "12.3 µA")
        self.assertEqual(format_value(100_000.0, "resistance", AUTO), "100 kΩ")

    def test_format_value_fixed_unit(self):
        self.assertEqual(format_value(1.942153, "voltage", "mV"), "1942.153 mV")
        self.assertEqual(format_value(1.229858e-3, "current", "A"), "0.001 A")
        self.assertEqual(format_value(1.229858e-3, "current", "µA"), "1229.858 µA")

    def test_split_value(self):
        text, unit = split_value(1.229858e-3, "current", AUTO)
        self.assertEqual(text, "1.23")
        self.assertEqual(unit, "mA")

    def test_format_number(self):
        self.assertEqual(format_number(1.942153, 3), "1.942")
        self.assertEqual(format_number(2.000, 3), "2")
        self.assertEqual(format_number(0.0, 3), "0")


if __name__ == "__main__":
    unittest.main()
