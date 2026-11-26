"""Flask tests for the ngspice API and the SPICE section of the page."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
import spice_engine  # noqa: E402


CIRCUIT = {
    "vcc": "12", "vcc_unit": "V",
    "r1": "100", "r1_unit": "kΩ",
    "r2": "22", "r2_unit": "kΩ",
    "rc": "2.2", "rc_unit": "kΩ",
    "re": "1", "re_unit": "kΩ",
    "beta": "100",
    "vbe": "0.70",
}

SIGNAL = {
    "amplitude": "10", "amplitude_unit": "mV",
    "frequency": "1", "frequency_unit": "kHz",
}

EMPTY_CIRCUIT = {
    "vcc": "", "vcc_unit": "V",
    "r1": "", "r1_unit": "kΩ",
    "r2": "", "r2_unit": "kΩ",
    "rc": "", "rc_unit": "kΩ",
    "re": "", "re_unit": "kΩ",
    "beta": "",
}


class SpiceApiCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def spice(self, **payload):
        return self.client.post("/api/spice", json=payload)


class TestSpiceStatus(SpiceApiCase):
    def test_status_reports_engine_and_reference(self):
        response = self.client.get("/api/spice/status")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("available", body)
        self.assertEqual(body["model"], spice_engine.DEFAULT_MODEL_NAME)
        self.assertAlmostEqual(body["reference"]["vcc"], 12.0)
        self.assertAlmostEqual(body["reference"]["r1"], 100e3)
        self.assertEqual(body["defaults"]["amplitude_mv"], 10.0)
        self.assertEqual(body["defaults"]["frequency_hz"], 1000.0)


class TestSpiceApiErrors(SpiceApiCase):
    def test_invalid_analysis_is_rejected(self):
        response = self.spice(analysis="fourier", **CIRCUIT, **SIGNAL)
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertIn("fourier", body["error"])
        self.assertNotIn("plot_svg", body)

    def test_invalid_amplitude_is_rejected(self):
        response = self.spice(analysis="tran", amplitude="0", amplitude_unit="mV", **CIRCUIT)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Amplitude", response.get_json()["error"])

    def test_incomplete_circuit_is_rejected(self):
        response = self.spice(analysis="op", vcc="12", **SIGNAL)
        self.assertEqual(response.status_code, 400)
        self.assertIn("กรุณากรอก", response.get_json()["error"])

    def test_zero_emitter_resistor_returns_400_not_success(self):
        """RE=0 ต้องไม่ส่ง ok=true/plot/values ให้หน้าเว็บแปลเป็นผลสำเร็จปลอม"""
        response = self.spice(analysis="op", **{**CIRCUIT, "re": "0", "re_unit": "kΩ"})
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertIn("RE", body["error"])
        self.assertNotIn("values", body)
        self.assertNotIn("plot_svg", body)

    def test_missing_engine_returns_503_with_hint(self):
        with mock.patch.object(spice_engine, "find_ngspice", return_value=None):
            response = self.spice(analysis="op", **CIRCUIT)
        self.assertEqual(response.status_code, 503)
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertIn("ngspice", body["error"])
        self.assertTrue(body["install_hint"])
        self.assertNotIn("plot_svg", body)

    def test_non_json_body_is_rejected(self):
        response = self.client.post("/api/spice", data="not json")
        self.assertEqual(response.status_code, 400)


class TestSpiceDefaults(SpiceApiCase):
    def test_empty_form_fields_use_reference_circuit(self):
        response = self.spice(analysis="op", **EMPTY_CIRCUIT, **SIGNAL)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertAlmostEqual(float(body["values"]["vb"]["value"]), 1.949, delta=0.05)
        self.assertAlmostEqual(body["parameters"]["r1"], 100e3, delta=1.0)


class TestSpicePageHtml(SpiceApiCase):
    def test_page_identity_is_lab04(self):
        # POST เพื่อให้ section ผลลัพธ์ (02) ถูก render ด้วยข้อมูลจริง
        body = self.client.post("/", data=CIRCUIT).get_data(as_text=True)
        self.assertIn("LAB 04 · BJT CE Amplifier", body)
        self.assertIn("02 / ANALYTICAL DC", body)
        self.assertIn("ผลลัพธ์ DC จาก Analytical", body)
        self.assertIn("03 / DC VISUALIZATION", body)
        self.assertIn("04 / SPICE SIMULATION", body)
        self.assertNotIn("LAB 03", body)

    def test_divider_page_contains_spice_section(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="spice-panel"', body)
        self.assertIn("SPICE SIMULATION", body)
        self.assertIn("analytical", body.lower())

    def test_fixed_mode_page_has_no_spice_section(self):
        body = self.client.get("/?mode=fixed").get_data(as_text=True)
        self.assertNotIn('id="spice-panel"', body)

    def test_spice_error_is_announced(self):
        """ช่อง error ต้องประกาศด้วย role=alert และไม่มี badge ค่าอ้างอิงคงที่"""
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="spice-error"', body)
        self.assertIn('role="alert"', body)
        self.assertNotIn('id="spice-reference-badge"', body)


@unittest.skipUnless(spice_engine.find_ngspice(), "ngspice not installed")
class TestSpiceApiReal(SpiceApiCase):
    def test_op_returns_formatted_values(self):
        response = self.spice(analysis="op", **CIRCUIT, **SIGNAL)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("ngspice", body["engine"])
        self.assertEqual(body["model"], spice_engine.DEFAULT_MODEL_NAME)
        self.assertIn("Q1 vc vb ve", body["netlist"])
        values = body["values"]
        for key in ("vb", "ve", "vc", "vce", "ib", "ic", "ie"):
            self.assertIn(key, values)
            self.assertIn("unit", values[key])
        self.assertAlmostEqual(float(values["vb"]["value"]), 1.949, delta=0.05)
        self.assertEqual(values["vb"]["unit"], "V")
        self.assertIsNone(body["plot_svg"])
        self.assertIn("analytical", body)
        self.assertAlmostEqual(
            float(body["analytical"]["values"]["vb"]["value"]), 1.942, delta=0.05
        )
        self.assertEqual(body["analytical"]["values"]["vb"]["unit"], "V")
        self.assertIn("dc_bias", body["analytical"]["source"])

    def test_ac_returns_bode_svg_and_summary(self):
        response = self.spice(analysis="ac", **CIRCUIT, **SIGNAL)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["plot_svg"].startswith("<svg"))
        self.assertIn("Gain (dB)", body["plot_svg"])
        labels = [item["label"] for item in body["summary"]]
        self.assertIn("จำนวนจุด", labels)
        self.assertGreater(body["series"]["points"], 20)

    def test_tran_returns_waveform_svg_and_summary(self):
        response = self.spice(analysis="tran", **CIRCUIT, **SIGNAL)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["plot_svg"].startswith("<svg"))
        self.assertIn("Time (ms)", body["plot_svg"])
        self.assertIn("Vin", body["plot_svg"])
        labels = [item["label"] for item in body["summary"]]
        self.assertIn("จำนวนจุด", labels)

    def test_warnings_are_surfaced_not_hidden(self):
        response = self.spice(analysis="op", **CIRCUIT, **SIGNAL)
        body = response.get_json()
        self.assertIsInstance(body["warnings"], list)

    def test_circuit_values_change_the_result(self):
        low = self.spice(analysis="op", **{**CIRCUIT, "r1": "47"}, **SIGNAL).get_json()
        high = self.spice(analysis="op", **CIRCUIT, **SIGNAL).get_json()
        self.assertNotAlmostEqual(
            float(low["values"]["vc"]["value"]),
            float(high["values"]["vc"]["value"]),
            places=2,
        )


if __name__ == "__main__":
    unittest.main()
