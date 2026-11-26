"""Tests for the ngspice integration layer (netlist, rawfile parsing, extraction).

ทุก test ที่ไม่ต้องใช้ ngspice จริงจะรันได้เสมอ
ส่วน integration test จะถูก skip อัตโนมัติเมื่อเครื่องไม่มี ngspice
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import spice_engine as se  # noqa: E402


OP_RAW = """Title: * CE op raw
Date: Tue Nov 24 17:48:55  2026
Command: ngspice-47, Build Aug 11 2026   13:49:23
Plotname: Operating Point
Flags: real
No. Variables: 8
No. Points: 1
Variables:
\t0\tv(vcc)\tvoltage
\t1\tv(vb)\tvoltage
\t2\tv(vc)\tvoltage
\t3\tv(ve)\tvoltage
\t4\ti(vcc)\tcurrent
\t5\ti(@q1[ic])\tcurrent
\t6\ti(@q1[ib])\tcurrent
\t7\ti(@q1[ie])\tcurrent
Values:
0\t\t1.200000000000000e+01
\t1.949112053392557e+00
\t9.189410182055312e+00
\t1.289453694188224e+00
\t-1.378049705804569e-03
\t1.278192757271984e-03
\t1.191895272144118e-05
\t-1.290111719182835e-03
"""

AC_RAW = """Title: * CE ac raw
Date: Tue Nov 24 17:46:43  2026
Command: ngspice-47, Build Aug 11 2026   13:49:23
Plotname: AC Analysis
Flags: complex
No. Variables: 4
No. Points: 2
Variables:
\t0\tfrequency\tfrequency\tgrid=3
\t1\tv(in)\tvoltage
\t2\tv(out)\tvoltage
\t3\tv(vc)\tvoltage
Values:
0\t\t1.000000000000000e+01,1.516186526589997e-311
\t1.000000000000000e+00,0.000000000000000e+00
\t-1.679508670000000e+00,-3.977201750000000e-01
\t9.189410182055312e+00,0.000000000000000e+00
1\t\t1.000000000000000e+03,0.000000000000000e+00
\t1.000000000000000e+00,0.000000000000000e+00
\t2.000000000000000e+00,0.000000000000000e+00
\t9.189410182055312e+00,0.000000000000000e+00
"""

TRAN_RAW = """Title: * CE tran raw
Date: Tue Nov 24 17:46:43  2026
Command: ngspice-47, Build Aug 11 2026   13:49:23
Plotname: Transient Analysis
Flags: real
No. Variables: 3
No. Points: 3
Variables:
\t0\ttime\ttime
\t1\tv(in)\tvoltage
\t2\tv(out)\tvoltage
Values:
0\t0.000000000000000e+00
\t0.000000000000000e+00
\t0.000000000000000e+00
1\t1.000000000000000e-03
\t7.000000000000000e-03
\t-1.000000000000000e+00
2\t2.000000000000000e-03
\t-7.000000000000000e-03
\t1.000000000000000e+00
"""


class TestParseRaw(unittest.TestCase):
    def test_parses_header_variables_and_points(self):
        raw = se.parse_raw(AC_RAW)
        self.assertEqual(raw["plotname"], "AC Analysis")
        self.assertEqual(raw["flags"], "complex")
        self.assertEqual(raw["variables"], ["frequency", "v(in)", "v(out)", "v(vc)"])
        self.assertEqual(len(raw["points"]), 2)
        self.assertEqual(len(raw["points"][0]), 4)

    def test_complex_values_are_python_complex(self):
        raw = se.parse_raw(AC_RAW)
        value = raw["points"][0][2]
        self.assertIsInstance(value, complex)
        self.assertAlmostEqual(value.real, -1.67950867, places=6)
        self.assertAlmostEqual(value.imag, -0.397720175, places=6)

    def test_real_values_are_python_float(self):
        raw = se.parse_raw(TRAN_RAW)
        self.assertEqual(len(raw["points"]), 3)
        self.assertAlmostEqual(raw["points"][1][1], 7e-3)
        self.assertIsInstance(raw["points"][1][1], float)

    def test_rejects_text_without_values(self):
        with self.assertRaises(se.SpiceError):
            se.parse_raw("Title: broken\nNo. Variables: 2\n")


class TestNetlist(unittest.TestCase):
    def setUp(self):
        self.params = se.reference_params()

    def test_reference_circuit_matches_lab_sheet(self):
        self.assertAlmostEqual(self.params["vcc"], 12.0)
        self.assertAlmostEqual(self.params["r1"], 100e3)
        self.assertAlmostEqual(self.params["r2"], 22e3)
        self.assertAlmostEqual(self.params["rc"], 2.2e3)
        self.assertAlmostEqual(self.params["re"], 1e3)
        self.assertAlmostEqual(self.params["rl"], 10e3)
        self.assertAlmostEqual(self.params["cin"], 10e-6)
        self.assertAlmostEqual(self.params["cout"], 10e-6)

    def test_op_netlist_contains_circuit_and_save(self):
        netlist = se.build_netlist(self.params, "op")
        for token in ("VCC vcc 0 12", "R1 vcc vb 100000", "R2 vb 0 22000",
                      "RC vcc vc 2200", "RE ve 0 1000", "Q1 vc vb ve QNPN_GENERIC",
                      "COUT vc out", "RL out 0 10000"):
            self.assertIn(token, netlist)
        self.assertIn(".op", netlist)
        self.assertIn("@q1[ic]", netlist)

    def test_ac_netlist_has_ac_source_and_sweep(self):
        netlist = se.build_netlist(self.params, "ac", amplitude_v=0.01, frequency_hz=1000)
        self.assertIn("AC 1", netlist)
        self.assertIn(".ac dec", netlist)

    def test_tran_netlist_has_sine_source(self):
        netlist = se.build_netlist(self.params, "tran", amplitude_v=0.01, frequency_hz=1000)
        self.assertIn("SIN(0 0.01 1000", netlist)
        self.assertIn(".tran", netlist)

    def test_unknown_analysis_rejected(self):
        with self.assertRaises(se.SpiceError):
            se.build_netlist(self.params, "fourier")


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.params = se.reference_params()

    def _assert_invalid(self, **changes):
        params = dict(self.params)
        params.update(changes)
        with self.assertRaises(se.SpiceError):
            se.validate_params(params)

    def test_reference_is_valid(self):
        se.validate_params(self.params)  # ต้องไม่ raise

    def test_rejects_non_positive_supply(self):
        self._assert_invalid(vcc=0.0)
        self._assert_invalid(vcc=-5.0)

    def test_rejects_zero_resistors(self):
        for field in ("r1", "r2", "rc"):
            with self.subTest(field=field):
                self._assert_invalid(**{field: 0.0})

    def test_rejects_zero_emitter_resistor(self):
        """RE=0 ต้อง error — ถ้าผ่าน netlist จะตัด RE ออกแล้ว ngspice คืนผลปลอม"""
        with self.assertRaises(se.SpiceError) as caught:
            se.validate_params({**self.params, "re": 0.0})
        self.assertIn("RE", caught.exception.message)

    def test_rejects_negative_emitter_resistor(self):
        self._assert_invalid(re=-1.0)

    def test_rejects_bad_beta(self):
        self._assert_invalid(beta=0.0)

    def test_rejects_bad_amplitude_and_frequency(self):
        with self.assertRaises(se.SpiceError):
            se.validate_params(self.params, amplitude_v=0.0)
        with self.assertRaises(se.SpiceError):
            se.validate_params(self.params, amplitude_v=2.0)
        with self.assertRaises(se.SpiceError):
            se.validate_params(self.params, frequency_hz=0.0)


class TestExtractors(unittest.TestCase):
    def test_extract_op(self):
        data = se.extract_op(se.parse_raw(OP_RAW))
        self.assertAlmostEqual(data["vb"], 1.94911205, places=6)
        self.assertAlmostEqual(data["ve"], 1.28945369, places=6)
        self.assertAlmostEqual(data["vc"], 9.18941018, places=6)
        self.assertAlmostEqual(data["vce"], data["vc"] - data["ve"], places=9)
        self.assertAlmostEqual(data["ic"], 1.27819276e-3, places=9)
        self.assertAlmostEqual(data["ib"], 1.19189527e-5, places=9)
        # ie ไหลออกจาก emitter → เก็บเป็นค่าบวก
        self.assertAlmostEqual(data["ie"], 1.29011172e-3, places=9)

    def test_extract_op_missing_node_raises(self):
        broken = OP_RAW.replace("\tv(vb)\t", "\tv(nope)\t")
        with self.assertRaises(se.SpiceError):
            se.extract_op(se.parse_raw(broken))

    def test_extract_ac_gain_and_phase(self):
        data = se.extract_ac(se.parse_raw(AC_RAW))
        self.assertEqual(data["frequency"], [10.0, 1000.0])
        self.assertAlmostEqual(data["gain_mag"][0], 1.726, places=3)
        self.assertAlmostEqual(data["gain_db"][0], 4.7406, places=3)
        self.assertAlmostEqual(data["phase_deg"][0], -166.68, places=1)
        self.assertAlmostEqual(data["gain_mag"][1], 2.0, places=6)
        self.assertAlmostEqual(data["gain_db"][1], 6.0206, places=3)

    def test_extract_tran(self):
        data = se.extract_tran(se.parse_raw(TRAN_RAW))
        self.assertEqual(len(data["time"]), 3)
        self.assertAlmostEqual(data["time"][1], 1e-3)
        self.assertAlmostEqual(data["vin"][1], 7e-3)
        self.assertAlmostEqual(data["vout"][1], -1.0)


class TestRunErrors(unittest.TestCase):
    def test_missing_engine_raises_with_hint(self):
        with mock.patch.object(se, "find_ngspice", return_value=None):
            with self.assertRaises(se.SpiceError) as ctx:
                se.run("op")
        self.assertIn("ngspice", str(ctx.exception))

    def test_nonzero_exit_reports_log(self):
        fake = mock.Mock(returncode=1, stdout="", stderr="boom")
        with mock.patch.object(se, "find_ngspice", return_value="ngspice"), \
             mock.patch.object(se.subprocess, "run", return_value=fake):
            with self.assertRaises(se.SpiceError) as ctx:
                se.run("op")
        self.assertIn("1", str(ctx.exception))

    def test_timeout_is_reported(self):
        with mock.patch.object(se, "find_ngspice", return_value="ngspice"), \
             mock.patch.object(
                 se.subprocess, "run",
                 side_effect=se.subprocess.TimeoutExpired("ngspice", 1),
             ):
            with self.assertRaises(se.SpiceError) as ctx:
                se.run("op", timeout_s=1)
        self.assertIn("หมดเวลา", str(ctx.exception))

    def test_empty_rawfile_is_reported(self):
        fake = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(se, "find_ngspice", return_value="ngspice"), \
             mock.patch.object(se.subprocess, "run", return_value=fake), \
             mock.patch.object(se, "read_raw", return_value={
                 "plotname": "Operating Point", "flags": "real",
                 "variables": [], "points": [],
             }):
            with self.assertRaises(se.SpiceError):
                se.run("op")


@unittest.skipUnless(se.find_ngspice(), "ngspice not installed")
class TestRealNgspice(unittest.TestCase):
    """Integration: รัน ngspice จริงกับวงจรอ้างอิง"""

    def test_op_matches_expected_bias(self):
        out = se.run("op")
        self.assertTrue(out["ok"])
        data = out["data"]
        self.assertAlmostEqual(data["vb"], 1.949, delta=0.05)
        self.assertAlmostEqual(data["ve"], 1.289, delta=0.05)
        self.assertAlmostEqual(data["vc"], 9.189, delta=0.05)
        self.assertGreater(data["ic"], 1e-3)
        self.assertLess(data["ic"], 1.5e-3)
        self.assertIn("ngspice", out["engine"])

    def test_ac_has_full_sweep_and_inverting_gain(self):
        out = se.run("ac", amplitude_v=0.01, frequency_hz=1000)
        data = out["data"]
        self.assertEqual(len(data["frequency"]), len(data["gain_db"]))
        self.assertEqual(len(data["frequency"]), len(data["phase_deg"]))
        self.assertGreater(len(data["frequency"]), 20)
        self.assertGreater(data["frequency"][-1], data["frequency"][0])
        # ที่ความถี่กลาง gain ต้องมากกว่า 1 และเฟสกลับด้าน
        mid = data["gain_mag"][len(data["gain_mag"]) // 2]
        self.assertGreater(mid, 1.0)
        self.assertLess(data["phase_deg"][len(data["phase_deg"]) // 2], -90)

    def test_tran_has_monotonic_time_and_waveforms(self):
        out = se.run("tran", amplitude_v=0.01, frequency_hz=1000)
        data = out["data"]
        self.assertGreater(len(data["time"]), 50)
        self.assertTrue(all(b >= a for a, b in zip(data["time"], data["time"][1:])))
        self.assertGreater(max(abs(v) for v in data["vin"]), 1e-3)
        self.assertGreater(max(abs(v) for v in data["vout"]), 1e-3)


if __name__ == "__main__":
    unittest.main()
