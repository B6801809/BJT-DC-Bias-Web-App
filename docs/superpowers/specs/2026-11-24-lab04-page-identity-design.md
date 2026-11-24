# Design — Lab 04 page identity (Approach A)

## Intent
หน้าเว็บยังแสดงตัวตนเป็น Lab 03 ทั้งที่แอปมี SPICE simulation ของ Lab 04 ครบแล้ว ให้เปลี่ยนอัตลักษณ์หน้าเป็น Lab 04 โดยยังคงโครงสร้างและพฤติกรรม Lab 03 เดิมไว้ทั้งหมด

## Goals
- เปลี่ยน `<title>`, hero `<h1>`, คำอธิบาย และ tag ให้เป็น Lab 04 / CE amplifier / DC + SPICE
- เปลี่ยนป้าย section เป็น `02 / ANALYTICAL DC`, `03 / DC VISUALIZATION` และคง `04 / SPICE SIMULATION`
- ปรับข้อความในส่วนผลลัพธ์/ภาพประกอบให้ระบุว่าเป็นค่าจาก Analytical (Python) ก่อนเทียบกับ SPICE
- khôngกระทบ route, สมการ, โหมด Fixed/Emitter หรือผลลัพธ์ที่มีอยู่

## Non-goals
- ไม่ย้ายลำดับ section ใหม่ (ทาง B)
- ไม่ลบโหมด Lab 03 หรือแก้ `dc_bias.py` / `app.py`
- ไม่เขียนรายงาน Lab 04 เพิ่มในรอบนี้

## Constraints
- แก้เฉพาะ `templates/index.html` เป็นหลัก; ถ้าจำเป็นให้เพิ่มข้อความใน `static/app.js` น้อยที่สุด
- ต้องผ่าน `python -m unittest discover -s tests -v` (110 tests)
- ต้องเปิด browser จริงแล้วเห็นหัวข้อ Lab 04 และ SPICE ยังทำงานได้

## Approaches
- **A (เลือก):** เปลี่ยนอัตลักษณ์/ป้าย section ใน template เดิม — เสี่ยงต่ำ ทำได้เร็ว และคง Lab 03 เดิม
- B: ย้ายแผง SPICE ขึ้นมาหลังฟอร์ม — ดูเป็น Lab 04 ชัดเจนกว่า แต่ต้องขยับโครงสร้างมากขึ้น
- C: ลบโหมด Lab 03 ทิ้ง — ขัดกับข้อกำหนดคงพฤติกรรมเดิม จึงไม่เลือก

## Design
- title: `LAB 04 · BJT CE Amplifier — DC Bias + SPICE Simulation`
- hero: `LAB 04 · BJT CE Amplifier` + คำอธิบายว่าใช้Voltage-Divider Bias เป็นวงจรอ้างอิง วิเคราะห์ DC ด้วย Python และ `.op/.ac/.tran` ด้วย ngspice จริง
- tags: `Flask + Python + ngspice`, `Analytical + SPICE`, `DC · AC · Transient`
- section labels: `01 / INPUT`, `02 / ANALYTICAL DC`, `03 / DC VISUALIZATION`, `04 / SPICE SIMULATION`
- คง footer และข้อความใน SPICE panel เดิมไว้ได้เลย (ระบุ Lab 04 อยู่แล้ว)

## Verification
- รัน unittest เต็มชุด
- browser: เปิด `http://127.0.0.1:5000/` ตรวจ title/hero/ป้าย section และกด `.op` ให้ยังได้ผล ngspice
