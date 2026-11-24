# Plan — Lab 04 page identity (Approach A)

Spec: `docs/superpowers/specs/2026-11-24-lab04-page-identity-design.md`
Repo: `C:\Users\B6801809\Documents\Default Project\BJT-DC-Bias-Web-App`

## Task 1 — ทดสอบก่อนแก้ (TDD)
ไฟล์: `tests/test_spice_web.py`

เพิ่ม test ใน `TestSpicePageHtml`:

```python
def test_page_identity_is_lab04(self):
    body = self.client.get("/").get_data(as_text=True)
    self.assertIn("<title>LAB 04 · BJT CE Amplifier — DC Bias + SPICE Simulation</title>", body)
    self.assertIn("<h1>LAB 04 · BJT CE Amplifier</h1>", body)
    self.assertIn("02 / ANALYTICAL DC", body)
    self.assertIn("03 / DC VISUALIZATION", body)
    self.assertNotIn("LAB 03", body)
```

รัน `.\.venv\Scripts\python.exe -m unittest tests.test_spice_web.TestSpicePageHtml -v` → ต้อง FAIL (red) เพราะหน้ายังเป็น Lab 03

## Task 2 — เปลี่ยนอัตลักษณ์หน้า
ไฟล์: `templates/index.html` (แก้ข้อความเท่านั้น ห้ามแตะสมการ/route/โครงสร้าง form)

แทนที่ข้อความต่อไปนี้ด้วยค่าที่ระบุ (ตามลำดับบรรทัด):

| บรรทัด | เดิม | ใหม่ |
|---|---|---|
| 6 | `<title>BJT DC Bias Calculator</title>` | `<title>LAB 04 · BJT CE Amplifier — DC Bias + SPICE Simulation</title>` |
| 14 | `<h1>LAB 03 · BJT DC Bias Calculator</h1>` | `<h1>LAB 04 · BJT CE Amplifier</h1>` |
| 15 | `วงจร BJT NPN Common-Emitter — เลือก Fixed Bias หรือ Voltage-Divider Bias คำนวณ DC Operating Point จาก Python Backend` | `วงจร BJT NPN Common-Emitter — วิเคราะห์ DC Operating Point ด้วย Python และจำลอง .op / .ac / .tran ด้วย ngspice จริง (วงจรอ้างอิง Voltage-Divider Bias)` |
| 16 | `<span class="tag">Flask + Python</span>` | `<span class="tag">Flask + Python + ngspice</span>` |
| 17 | `<span class="tag">Forward-Active Approximation</span>` | `<span class="tag">Analytical + SPICE</span>` `<span class="tag">DC · AC · Transient</span>` (สองบรรทัด) |
| 202 | `<div class="kicker">02 / RESULT</div>` | `<div class="kicker">02 / ANALYTICAL DC</div>` |
| 210 | `<h3>ผลลัพธ์ DC Bias — {{ mode_label }}</h3>` | `<h3>ผลลัพธ์ DC จาก Analytical — {{ mode_label }}</h3>` |
| 303 | `<div class="kicker">03 / VISUALIZATION</div>` | `<div class="kicker">03 / DC VISUALIZATION</div>` |
| 304 | `<h2>ภาพวงจรและกราฟที่ใช้ในการคำนวณ</h2>` | `<h2>ภาพวงจรและกราฟจากการคำนวณ Analytical</h2>` |

คง `01 / INPUT`, `04 / SPICE SIMULATION`, footer และปุ่มทั้งหมดไว้ตามเดิม (footer เขียน Lab 04 อยู่แล้ว)

## Task 3 — ตรวจ test ผ่าน (green)
รัน `.\.venv\Scripts\python.exe -m unittest tests.test_spice_web.TestSpicePageHtml -v` → ต้อง OK

## Task 4 — ตรวจ browser จริง
เซิร์ฟเวอร์: `.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5000` (ถ้าเก่ายังรันอยู่ให้ใช้ PID เดิม)

ด้วย in-app browser:
1. เปิด `http://127.0.0.1:5000/` ตรวจ title, h1 ว่าเป็น Lab 04 และป้าย 02/03/04 ถูกต้อง
2. กด `Run DC .op` → ต้องได้ข้อความ `ผล .op` และ VB ≈ 1.949 V (ngspice จริง)
3. ตรวจ console error = 0

## Task 5 — full suite + commit
1. `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` → ต้อง `OK` (111 tests หลังเพิ่ม test ใหม่)
2. `git diff --check`
3. commit `Update page identity to Lab 04 (Analytical + SPICE)` แล้ว `git push origin main`
   (git: `C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\TeamFoundation\Team Explorer\Git\cmd\git.exe`)

## Constraints
- ไม่แก้ `app.py`, `dc_bias.py`, `units.py`, `circuit.py`, `static/app.js`, `static/style.css` ในรอบนี้
- ไม่ลบโหมด Fixed/Emitter และไม่ย้ายลำดับ section (ทาง B)
- ทุกข้อความ UI เป็นภาษาไทยที่อ่านเข้าใจง่ายตาม AGENTS.md
