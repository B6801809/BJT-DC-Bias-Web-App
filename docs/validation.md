# Validation — BJT DC Bias Web App

## 1. ค่าอ้างอิงที่ใช้ตรวจ

อินพุต:

| พารามิเตอร์ | ค่า |
|---|---|
| VCC | 12 V |
| R1 | 100 kΩ = 100,000 Ω |
| R2 | 22 kΩ = 22,000 Ω |
| RC | 2.2 kΩ = 2,200 Ω |
| RE | 1 kΩ = 1,000 Ω |
| β | 100 |
| VBE | 0.70 V |

คำนวณด้วยมือ:

```
VTH = 12 × 22,000 / (100,000 + 22,000) = 2.163934 V
RTH = 100,000 × 22,000 / 122,000    = 18,032.787 Ω
IB  = (2.163934 − 0.70) / (18,032.787 + 101 × 1,000)
    = 1.463934 / 119,032.787
    = 12.298581 μA
IC  = 100 × 12.298581 μA = 1.229858 mA
IE  = 101 × 12.298581 μA = 1.242157 mA
VE  = 1.242157 mA × 1,000 Ω = 1.242157 V
VB  = 1.242157 + 0.70 = 1.942157 V
VC  = 12 − 1.229858 mA × 2,200 Ω = 9.294312 V
VCE = 9.294312 − 1.242157 = 8.052155 V
```

ผลที่คาดหวัง: **Forward-Active**, ไม่มี Warning

## 2. ผลการรัน Tests

รันด้วยคำสั่ง:

```powershell
python -m unittest discover -s tests -v
```

ครอบคลุม:
- ค่าอ้างอิง Forward-Active ตรงกับสมการมือ
- ความสัมพันธ์ IC = β·IB และ IE = (β+1)·IB
- Cutoff (VTH ≤ VBE) → กระแสเป็นศูนย์ + Warning
- Saturation (VCE < 0.2 V) → Warning
- Validation: VCC ≤ 0, R ≤ 0, β ≤ 0, R ติดลบ
- HTTP: GET /, POST / ค่าถูกต้อง, ข้อมูลขาด, ข้อมูลไม่ใช่ตัวเลข, R = 0
- API JSON

### 2.1 การตรวจสอบหน่วย (tests/test_units.py และ tests/test_web.py)

- การแปลงหน่วย: 100 kΩ = 100000 Ω, 2.2 MΩ = 2,200,000 Ω, 12000 mV = 12 V
- หน่วยที่ไม่รู้จักต้องถูกปฏิเสธ (ValueError)
- การเลือกหน่วยอัตโนมัติ: 12 V → V, 0.012 V → mV, 1.2 mA → mA, 1.2 µA → µA
- การจัดรูปแบบ: 1.942153 V → "1.942 V", 1.229858 mA → "1.23 mA"
- **กรอกด้วยหน่วยต่างกันแต่ค่าเท่ากัน ต้องได้ผลลัพธ์เท่ากัน**
  (เช่น R1 = 100 kΩ เท่ากับ R1 = 100000 Ω → IC และ VCE ต้องเหมือนกัน)
- VCC = 12000 mV ต้องให้ผลลัพธ์เหมือน VCC = 12 V
- เลือกหน่วยแสดงผลเป็น mV/µA ต้องเปลี่ยนข้อความที่แสดง (เช่น VB = 1942.157 mV)
- API ต้องรับฟิลด์หน่วยและคืนค่าหน่วยที่เลือกกลับมา

### 2.2 การตรวจสอบภาพประกอบ (tests/test_circuit.py)

- SVG ทุกภาพต้องเป็น XML ที่ parse ได้
- ภาพวงจรต้องมี R1, R2, RC, RE, Q1 และค่าที่กรอก
- กราฟ load line ต้องมีเส้น load line, เส้นโค้ง IC = β·IB และป้ายจุด Q
- **จุด Q ที่คำนวณได้ต้องอยู่บน DC load line** (ตรวจด้วยสมการ
  IC = (VCC − VCE) / (RC + RE·(β+1)/β) ให้ตรงกับ `dc_bias.py` ถึง 9 ตำแหน่งทศนิยม)
- จุดปลายของ load line: ที่ VCE = 0 ได้ IC = VCC/(RC + RE·(β+1)/β)
  และที่ VCE = VCC ได้ IC = 0

## 3. การตรวจใน Browser

1. เปิด <http://127.0.0.1:5000/>
2. กรอกค่าอ้างอิงข้างต้น
3. กด Calculate DC Bias
4. ตรวจว่าได้ VB ≈ 1.942 V, VE ≈ 1.242 V, VC ≈ 9.294 V, VCE ≈ 8.052 V, IC ≈ 1.23 mA
5. เลื่อนลงไปดูหัวข้อ **03 / VISUALIZATION**
   - ภาพวงจรต้องแสดงค่า R1/R2/RC/RE ตามที่กรอกและค่า VB, VE, VC, IC
   - กราฟ load line ต้องมีจุด Q ที่ตรงกับ VCE = 8.052 V และ IC = 1.23 mA
   - แผนภาพระดับแรงดันต้องแสดง VC > VB > VE
6. ทดลองกรอก R1 = 0 → ต้องเห็น Error
7. ทดลองกรอก R1 = 1,000 kΩ → ต้องเห็น Warning/Cutoff

## 4. ข้อจำกัด

- เป็นแบบจำลอง Forward-Active อย่างง่าย ไม่ใช่ SPICE
- β และ VBE ถือว่าคงที่
- ไม่ได้คำนวณ Early effect, temperature effect หรือ parasitic

## 5. Lab 3 · A2 — Fixed Bias (RB = 1 MΩ)

**วิธีตรวจ:** OpenCode Browser (in-app browser) · http://127.0.0.1:5000/?mode=fixed  
**อินพุตที่กรอกจริง:** โหมด Fixed Bias, VCC = 12 V, RB = 1 MΩ, RC = 2.2 kΩ, β = 100, VBE = 0.70 V  
**หน้าฟอร์ม:** มีช่อง RB และไม่แสดงช่อง R1/R2/RE · ผลและหัวข้อระบุโหมด "Fixed Bias"

| รายการ | คาดหมาย (คำนวณมือ) | เห็นจริงจากหน้าเว็บ | ผลต่าง | สถานะ |
|---|---|---|---|---|
| IB | 11.30 µA | 11.3 µA | 0.00 µA | PASS |
| **IC** | **1.130000 mA** | **1.13 mA** | **0.000 mA** | **PASS** |
| IE | 1.141300 mA | 1.14 mA | 0.001 mA | PASS |
| VB | 0.700 V | 700 mV | 0.000 V | PASS |
| VE | 0.000 V | 0 mV | 0.000 V | PASS |
| VC | 9.514000 V | 9.514 V | 0.000 V | PASS |
| **VCE** | **9.514000 V** | **9.514 V** | **0.000 V** | **PASS** |
| โซน | Forward-Active | Forward-Active | — | PASS |

เกณฑ์ที่ใช้: |ΔIC| ≤ 0.01 mA และ |ΔVCE| ≤ 0.02 V เทียบกับค่าอ้างอิงที่ยังไม่ปัดเศษ → ผ่านทั้งสองรายการ

**หลักฐานจาก browser snapshot:** `ผลลัพธ์ DC Bias — Fixed Bias`, `IC 1.13 mA`, `VCE 9.514 V`, `IB 11.3 µA`, `VB 700 mV`, `VE 0 mV`, `Forward-Active` และภาพวงจร `aria-label="วงจร BJT NPN Common-Emitter แบบ Fixed Bias"` (ไม่มี RE)

**การตรวจย้อนกลับ:** ค่า RB = 1 ที่เลือกหน่วย MΩ ถูกแปลงเป็น 1,000,000 Ω ที่ `app._parse_inputs()` ผ่าน `units.to_si()` ก่อนส่งเข้า `dc_bias.calculate_fixed_bias()` ซึ่งใช้สูตร `(VCC − VBE) / RB` — สมการอยู่ใน Python ไม่ได้ฝังใน HTML

## 6. Lab 3 · A3 — Emitter Bias (RB = 1 MΩ, RE = 1 kΩ)

**วิธีตรวจ:** OpenCode Browser (in-app browser) · http://127.0.0.1:5000/?mode=emitter  
**อินพุตที่กรอกจริง:** โหมด Emitter Bias, VCC = 12 V, RB = 1 MΩ, RC = 2.2 kΩ, RE = 1 kΩ, β = 100, VBE = 0.70 V  
**หน้าฟอร์ม:** แสดงทั้งช่อง RB และ RE ไม่แสดงช่อง R1/R2 · ผลและหัวข้อระบุโหมด "Emitter Bias"

สมการอ้างอิง: `IB = (VCC − VBE) / [RB + (β+1)RE] = 11.3 / (1,000,000 + 101 × 1,000) = 11.3 / 1,101,000 = 10.263397 µA`

| รายการ | คาดหมาย (คำนวณมือ) | เห็นจริงจากหน้าเว็บ | ผลต่าง | สถานะ |
|---|---|---|---|---|
| IB | 10.263397 µA | 10.26 µA | 0.003397 µA | PASS |
| **IC** | **1.026340 mA** | **1.03 mA** | **0.003660 mA** | **PASS** |
| IE | 1.036603 mA | 1.04 mA | 0.003397 mA | PASS |
| VB | 1.736603 V | 1.737 V | 0.000397 V | PASS |
| VE | 1.036603 V | 1.037 V | 0.000397 V | PASS |
| VC | 9.742053 V | 9.742 V | 0.000053 V | PASS |
| **VCE** | **8.705450 V** | **8.705 V** | **0.000450 V** | **PASS** |
| โซน | Forward-Active | Forward-Active | — | PASS |

เกณฑ์ที่ใช้: |ΔIC| ≤ 0.01 mA และ |ΔVCE| ≤ 0.02 V เทียบกับค่าอ้างอิงที่ยังไม่ปัดเศษ → ผ่านทั้งสองรายการ

**หลักฐานจาก browser snapshot:** `ผลลัพธ์ DC Bias — Emitter Bias`, `IC 1.03 mA`, `VCE 8.705 V`, `IB 10.26 µA`, `VE 1.037 V`, `Forward-Active` และภาพวงจร `aria-label="วงจร BJT NPN Common-Emitter แบบ Emitter Bias"` (มี RB และ RE)

**การตรวจย้อนกลับ:** ค่า RE = 1 kΩ ถูกแปลงเป็น 1,000 Ω ที่ `app._parse_inputs()` แล้วส่งเข้า `dc_bias.calculate_emitter_bias()` ซึ่งใช้สมการ `(VCC − VBE)/[RB + (β+1)RE]` และ `VE = IE·RE` — ผล VE = 1.037 V บนหน้าเว็บยืนยันว่าค่า RE เข้าถึงสมการจริง (ใน Fixed Bias VE จะเป็น 0 V เสมอ)

---

# Lab 04 — BJT Amplifier Simulator v1 (SPICE + Analytical)

## ขอบเขตและวิธีตรวจ
- **วันที่/เวอร์ชัน**: ตรวจบนเครื่องนี้ · Flask app รันจริง `http://127.0.0.1:5000/` · **ngspice-47** · Python 3.14.10 · Flask 3.1.3
- **วงจรอ้างอิง**: CE Voltage Divider, VCC 12 V, R1 100 kΩ, R2 22 kΩ, RC 2.2 kΩ, RE 1 kΩ, RL 10 kΩ, Cin/Cout 10 µF, Source 10 mV peak 1 kHz, BJT `QNPN_GENERIC`
- **BJT model**: `QNPN_GENERIC`, NPN(BF=100 IS=1e-14 VAF=100) ตาม `spice_engine.DEFAULT_MODEL` (รายงานโดย `GET /api/spice/status`)
- **วิธีตรวจ (ไม่ใช่ Playwright MCP)**: (1) ยิง **HTTP API จริง** `/api/calculate`, `/api/spice`, `/api/spice/status` บนแอปที่กำลังรัน และ ngspice ทำงานจริง; (2) **in-app browser** (OpenCode browser tools) เปิดหน้าจริง snapshot + screenshot
- ตัวเลขด้านล่างคือค่าที่ **อ่านจริงจาก output** ไม่ใช่ตัวอย่างในใบงาน; **ไม่ claim Playwright MCP**
- แยกป้าย **Analytical** (สมการประมาณจาก `dc_bias.py`) ออกจาก **SPICE** (ngspice); ผลสองแบบไม่ต้องเท่ากันทุกหลัก

## เทสต์อัตโนมัติ (fresh run)
```
python -m unittest discover -s tests -v
Ran 115 tests in ~3.2 s  →  OK   (0 skipped, 0 failed)   [เมื่อมี ngspice]
```
ไม่มี ngspice → เทสต์ `ngspice จริง` ถูก skipped และ `test_empty_form_fields_use_reference_circuit` FAIL (503) — ไม่ถือว่าผ่าน
SPICE engine-not-ready → HTTP 503 + install_hint (มี unit test `test_missing_engine_returns_503_with_hint`); SPICE run error → 400; invalid input → 400

## ผล B1–B8 (สถานะที่พบจริง)

| Case | Method | Input | Expected/Reference | Observed | Evidence | Status |
|---|---|---|---|---|---|---|
| **B1 · Regression** | API `/api/calculate` + GET modes | Fixed A2: VCC12,RB1MΩ,RC2.2kΩ,β100,VBE.7 · Emitter A3 +RE1kΩ · Divider Lab3 ref · GET ?mode= | Lab3 values · 3 modes 200 | **A2** IC=1.13 mA, VCE=9.514 V, VB=0.700, VE=0, FA · **A3** IC=1.0263 mA, VCE=8.7054 V, VB=1.7366, VE=1.0366, FA · **Divider** IC=1.2299 mA, VCE=8.0522 V, VB=1.9422, VE=1.2422, VC=9.2943, VTH=2.164, RTH=18.033k, FA · GET divider/fixed/emitter=200 | response JSON + `docs/validation.md` Lab3 §5/§6 + unit tests | PASS |
| **B2 · DC SPICE** | `/api/spice` analysis=op | reference CE divider | VB/VE/VC/VCE/IC จาก ngspice + model + status + Analytical แยก | ok=true engine=**ngspice-47** model=**QNPN_GENERIC**; VB=1.949 V, VE=1.289 V, VC=9.189 V, VCE=7.900 V, IC=1.28 mA, IB=11.92 µA, IE=1.29 mA; analytical source=`dc_bias.py`; netlist + log + warnings=[] | response + `/api/spice/status` | PASS (ตัวเลข SPICE≠Analytical ได้) |
| **B3 · Change RE** | `/api/spice` op, RE 1→2 kΩ | เปลี่ยนค่าเดียว | OP/Gain เปลี่ยน ไม่ใช่ค่าเดิม | IC 1.28→0.696 mA, VCE 7.900→9.065 V, VE 1.289→1.405 V, VC 9.189→10.469 V, IB 11.92→6.42 µA | before/after JSON | PASS |
| **B4 · AC** | `/api/spice` ac | reference + amplitude/freq | Bode แกน Freq, Gain magnitude+Phase หน่วย จาก run จริง | kind=bode **51 จุด** 10 Hz–1 MHz; **Gain @1 kHz = 4.86 dB**, **Phase @1 kHz = −179.9°**, Gain สูงสุด 4.86 dB; `plot_svg`=SVG | response + SVG | PASS |
| **B5 · Transient** | `/api/spice` tran 10 mV peak 1 kHz | reference | Vin/Vout ตามเวลา กลับเฟส | kind=waveform **1008 จุด** 0–5 ms; Vin p-p=**19.999 mV**, Vout p-p=**34.994 mV**, **|Vout/Vin|=1.750**, f=1 kHz; `plot_svg`=SVG; สัญญาณกลับเฟส | response + SVG | PASS |
| **B6 · Change Source** | `/api/spice` tran amp 10→20 mV | เปลี่ยน amplitude/frequency | waveform เปลี่ยน ไม่ hard-code | Vin p-p 19.999→**39.998 mV**, Vout p-p 34.994→**69.989 mV**, |Vout/Vin|=1.750; **plot เปลี่ยน** (เนื้อหา SVG ต่าง, ความยาวเท่ากัน) | before/after | PASS |
| **B7 · Invalid / Fail** | invalid inputs + engine | RE=0 หรือ engine ไม่พร้อม | error ไม่ค้าง ไม่ fake success | **SPICE RE=0 → 400 `RE ต้องมากกว่า 0`** (browser: error โผล่, output ว่าง, ไม่มีผลสำเร็จปลอม); RE=0 **analytical emitter** → error เดิม; **SPICE RE ติดลบ** → 400; missing fields → 400; bad analysis → 400; **engine not ready → 503** + UI ประกาศ error/ระงับปุ่มทันที; timeout 35 s กันค้าง | response + unit test + browser | PASS |
| **B8 · UI** | in-app browser snapshot + screenshot | desktop; mobile viewport | กราฟ/หน่วย/ปุ่มอ่านง่าย ไม่มีเนื้อหาสำคัญถูกตัด | title `LAB 04 · BJT CE Amplifier — DC Bias + SPICE Simulation`; mode switching; **59** interactive controls; VCC/VBE units, analysis modes, Run; spice section ครบ; screenshot saved `docs/captures/lab4-desktop.jpeg` | snapshot + `docs/captures/lab4-desktop.jpeg` | PASS (desktop) · **mobile NOT RUN** · ตรวจเชิงภาพจำกัด (โมเดลนี้อ่านรูปไม่ได้) |

## ข้อสังเกต / ข้อจำกัดที่พบจริง (ไม่ fabricate, ไม่ซ่อน)
1. **B7 + RE=0 แก้แล้ว (ไม่ fake success)**: ก่อนหน้า `spice_engine` ใช้ `"re": ("RE","ge0")` → ตัดบรรทัด RE ออกแล้ว ngspice คืน `ok=true` ทั้งที่โหนด emitter ลอย (VB≈2.164 V) ตอนนี้ `validate_params` ใช้ `"gt0"` → 400 `RE ต้องมากกว่า 0` ก่อนสร้าง netlist; unit test เปลี่ยนจาก `test_allows_zero_emitter_resistor` เป็น `test_rejects_zero_emitter_resistor` และมี test API กัน `ok/values/plot_svg` ฝั่ง UI เมื่อ engine ไม่พร้อม (`available=false`) จะแสดง error ทันทีและปิดปุ่มรัน; ถ้า fetch ไม่ตอบภายใน 35 s จะ abort แจ้งหมดเวลา ไม่ค้างในสถานะกำลังรัน
2. **Analytical vs SPICE ตัวเลขไม่ตรงทุกหลัก**: เช่น IC Analytical=1.23 mA vs ngspice=1.28 mA, VCE 8.052 vs 7.900 — ปกติ (model β/VBE ต่าง + ngspice solve จริง) แอปแยกป้ายไว้
3. **AC gain ~4.86 dB / |Vout/Vin|≈1.75**: ค่าจริงจาก ngspice ของวงจรนี้ ไม่ใช่ mock; ไม่ claim fL/fH นอกช่วง sweep
4. **B8**: ตรวจ desktop; **mobile viewport NOT RUN** (ไม่มี viewport control ใน browser tool นี้); ไม่ได้ใช้ Playwright MCP; screenshot ถูกเซฟแต่โมเดลนี้อ่านรูปไม่ได้ → ตรวจโครงสร้างผ่าน snapshot แทน
5. **VBE** แสดงเลข float (เช่น 0.699999988079071) ใน snapshot — cosmetic ไม่กระทบคำนวณ (คำนวณใช้ค่าตั้งต้น 0.70 → SI)
6. เทสต์ `ngspice จริง` (4 ตัว) ต้องมี ngspice; เครื่องนี้ติดตั้ง ngspice-47 แล้ว → 115/115 ผ่าน (หลังเพิ่ม test กัน RE=0 fake success)

## หลักฐานที่แนบ
- `docs/captures/lab4-desktop.jpeg` (screenshot in-app browser, full page)
- `GET /api/spice/status`, `POST /api/spice`, `POST /api/calculate` responses (JSON + SVG + log + netlist)
- netlist + log + warnings ที่แอปคืนมา; unit/integration tests `tests/test_spice_*.py`
