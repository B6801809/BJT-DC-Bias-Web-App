# Lab 04 — ngspice Integration Plan (CE Voltage Divider Amplifier)

Status: approved by user (`อนุมัคิ`). Execute inline with TDD.

## Goal

Extend the existing Lab 3 Flask app with **real ngspice runs** for one reference
CE voltage-divider circuit:

- `.op` → DC operating point (VB, VE, VC, VCE, IB, IC, IE)
- `.ac` → frequency response, gain magnitude in dB + phase in degrees
- `.tran` → input/output waveforms for a sine excitation

SPICE numbers must be visually separated from the existing analytical
(`dc_bias.py`) numbers, and every failure must surface as an error — never a
stale chart or a fabricated success.

## Reused files (behaviour preserved)

| File | Change |
| --- | --- |
| `dc_bias.py` | none |
| `units.py` | none (reused for formatting) |
| `circuit.py` | none |
| `app.py` | add SPICE routes only; `/`, `POST /`, `/api/calculate` unchanged |
| `templates/index.html` | append one SPICE section (divider mode only) |
| `static/style.css` | append styles for the SPICE section |
| `static/app.js` | append fetch logic; existing example-fill logic untouched |
| `tests/test_*.py` | existing 56 tests must keep passing |

## New modules

### `spice_engine.py`

```python
DEFAULT_MODEL = {"name": "QNPN_GENERIC", "npn": {"bf": 100.0, "is": 1e-14, "vaf": 100.0}}
REFERENCE = {"vcc": 12.0, "r1": 100e3, "r2": 22e3, "rc": 2.2e3, "re": 1e3,
             "beta": 100.0, "vbe": 0.70, "rl": 10e3, "cin": 10e-6, "cout": 10e-6}
DEFAULT_AMPLITUDE_V = 0.010   # 10 mV peak, per lab sheet
DEFAULT_FREQUENCY_HZ = 1_000.0
TIMEOUT_S = 30.0
```

- `reference_params() -> dict` – copy of `REFERENCE` (SI units).
- `find_ngspice() -> str | None` – `NGSPICE_BIN` (file or dir) → `shutil.which`
  → `%LOCALAPPDATA%\Programs\ngspice-*\Spice64\bin\ngspice.exe`.
- `validate_params(params, *, amplitude_v, frequency_hz) -> None` – raises
  `SpiceError` with a Thai message: VCC/RC must be > 0, R1/R2 > 0 (divider),
  RE ≥ 0, beta > 0, `0 < amplitude <= 1.0` V, `0 < frequency <= 1e9` Hz.
- `build_netlist(params, analysis, *, amplitude_v, frequency_hz, model=DEFAULT_MODEL) -> str`
  – one deck per analysis, RL/Cin/Cout from `REFERENCE`, `shell=False` friendly.
- `parse_raw(text) -> dict` – ASCII ngspice rawfile → `{"plotname", "flags",
  "variables": [name...], "points": [[complex|float, ...], ...]}`.
- `read_raw(path) -> dict`.
- `extract_op(raw) -> dict` – `vb, ve, vc, vce, ib, ic, ie`.
- `extract_ac(raw) -> dict` – `frequency, gain_mag, gain_db, phase_deg` lists.
- `extract_tran(raw) -> dict` – `time, vin, vout` lists.
- `run(analysis, params=None, *, amplitude_v=DEFAULT_AMPLITUDE_V,
  frequency_hz=DEFAULT_FREQUENCY_HZ, timeout_s=TIMEOUT_S) -> dict`
  – finds engine, writes deck + runs `[exe, "-b", "-o", log, "-r", raw, deck]`
  in a fresh `tempfile.TemporaryDirectory`, returns:

  ```python
  {"ok": True, "analysis": "ac", "engine": "ngspice-47",
   "engine_path": "...", "model": "QNPN_GENERIC",
   "netlist": "...", "warnings": [...], "log": "...",
   "data": {...}, "duration_ms": 12.3}
  ```

  Raises `SpiceError` when the engine is missing, exit code ≠ 0, timeout,
  rawfile absent/unparseable, or the deck produced zero points.

### `spice_plots.py`

Pure-Python SVG strings, no Flask, no matplotlib:

- `bode_svg(ac, width=760, height=420) -> str` – |gain| dB and phase vs log f,
  two stacked panels, decade grid, axis labels in Hz / dB / °.
- `waveform_svg(tran, width=760, height=360) -> str` – Vin + Vout vs time (ms)
  with legend.
- Both escape text, skip non-finite samples, and never emit `nan`/`inf`.

### `tests/test_spice_engine.py`, `tests/test_spice_plots.py`, `tests/test_spice_web.py`

Unit tests for the parser/netlist/validators/extractors/plots (no ngspice
needed) plus integration tests guarded by
`@unittest.skipUnless(find_ngspice(), "ngspice not installed")`.

## HTTP surface

- `GET /api/spice/status` → `{available, engine, engine_path, model, reference, defaults}`
- `POST /api/spice` (JSON):
  `{"analysis": "op"|"ac"|"tran", <circuit fields as in /api/calculate>,
    "amplitude": 10, "amplitude_unit": "mV", "frequency": 1000, "frequency_unit": "Hz"}`
  → 200 with `ok, engine, model, analysis, values (display dict + SI),
  plot_svg, warnings, log, netlist, duration_ms`; 400 `{error, detail?}` on
  validation failure; 503 `{error}` when ngspice is unavailable.

## UI

Appended section `04 / SPICE SIMULATION` (rendered only when
`mode == 'divider'`):

- engine badge (online/offline + version + model name)
- amplitude (mV) and frequency (Hz) inputs
- three buttons: `.op`, `.ac`, `.tran`
- status line: idle → running → success/error, never "success" on failure
- `.op` table, `.ac` Bode SVG, `.tran` waveform SVG
- explicit captions: `SPICE (ngspice-47)` vs `Analytical (Python, dc_bias.py)`
- error panel shows the engine message and the ngspice log tail

JS sends the current main-form values (empty → reference defaults) plus amplitude
and frequency; on error it clears all previous SPICE panels first.

## Error paths (each has a test)

1. ngspice not found → 503 + install hint.
2. non-zero exit → 400 with log tail.
3. timeout → process killed, `SpiceError("หมดเวลา")`.
4. empty/unparseable rawfile → 400, no chart.
5. invalid RE/amplitude/frequency/analysis → 400 before any netlist runs.
6. mode ≠ divider → no SPICE section in HTML.

## Verification

1. `python -m unittest discover -s tests -v` (old 56 + new tests).
2. Real run against `ngspice-47` for all three analyses; numbers cross-checked
   against the `.op` probe already captured (VB≈1.949, VE≈1.289, VC≈9.189,
   IC≈1.278 mA).
3. Browser demo on `http://127.0.0.1:5000/`: click each button, confirm charts
   render, console clean, and an induced error (bad amplitude) shows an error.
4. `docs/validation.md` records commands, outputs, and the ngspice raw values.
5. README section for Lab 04 + commit.
