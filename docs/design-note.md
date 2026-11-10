# Design Note — BJT DC Bias Web App

## โจทย์

สร้าง Flask Web Application สำหรับคำนวณ DC Bias ของวงจร BJT NPN
Common-Emitter แบบ Voltage-Divider Bias ภายในขอบเขต Lab 02 (DC เท่านั้น)

## ขอบเขต

อยู่ในขอบเขต:
- รับค่า VCC, R1, R2, RC, RE, β, VBE
- คำนวณ VB, VE, VC, VCE, IB, IC, IE
- Validation และ Warning เมื่ออยู่นอกย่าน Forward-Active
- Automated tests

ไม่อยู่ในขอบเขต:
- AC analysis, Bode plot, transient
- Signal generator, overlay animation
- Circuit editor หรือ SPICE solver
- รองรับ FET / bias แบบอื่น

## การตัดสินใจออกแบบ

1. **แยก Engineering Logic ออกจาก Web Layer**
   - `dc_bias.py` เป็น pure function รับ/คืน dict
   - ทำให้ทดสอบได้โดยไม่ต้องเปิด Flask
2. **หน่วยความต้านทาน**
   - UI รับ kΩ (อ่านง่ายสำหรับค่าอุปกรณ์จริง) แล้วคูณ 1000 ใน `app.py`
   - ภายใน calculation ใช้ Ω ทั้งหมด เพื่อลดความสับสน
3. **Validation สองชั้น**
   - ชั้น Flask: ตรวจค่าว่าง / ตัวเลขไม่ถูกต้อง
   - ชั้น Engineering: ตรวจ VCC, R, β, VBE และแจ้ง error รวมกัน
4. **Warning ไม่ใช่ Error**
   - ถ้าอยู่นอก Forward-Active ยังแสดงตัวเลขได้ แต่ต้องมี Warning ชัดเจน
5. **Template ไม่มีสมการ**
   - `index.html` ทำหน้าที่แสดงผลเท่านั้น

## Data Flow

```
Browser form
  -> POST / (Flask)
  -> app._parse_inputs (kΩ -> Ω, validation)
  -> dc_bias.calculate_dc_bias
  -> render_template(index.html, result)
  -> Browser แสดงผล
```

## โครงสร้างไฟล์

- `app.py` — routes, parsing, validation ระดับ HTTP
- `dc_bias.py` — สมการและการตัดสินโซนการทำงาน
- `templates/index.html` — ฟอร์มและผลลัพธ์
- `static/style.css` — responsive layout
- `tests/` — unit + HTTP tests
