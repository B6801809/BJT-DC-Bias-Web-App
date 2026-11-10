# Reflection — Lab 02

## สิ่งที่ได้เรียนรู้

- ความแตกต่างระหว่าง Static HTML กับ Web Application ที่มี Backend จริง
- การแยก Engineering Logic (`dc_bias.py`) ออกจาก Web Layer (`app.py`) ทำให้ทดสอบง่ายและลดการผูกติดกับ framework
- การจัดการหน่วยเป็นจุดที่ผิดพลาดได้ง่าย (kΩ vs Ω) จึงต้องแปลงให้ชัดเจนที่ขอบระบบ
- การทำ Validation และ Warning ทำให้โปรแกรมซื่อสัตย์ต่อข้อจำกัดของแบบจำลอง

## ปัญหาที่พบและวิธีแก้

1. **ModuleNotFoundError: No module named 'flask'**
   - สาเหตุ: รันด้วย Python ระบบที่ยังไม่ได้ติดตั้ง Flask
   - แก้ไข: สร้าง virtual environment แล้ว `pip install -r requirements.txt` และ activate ก่อนรันทุกครั้ง
2. **Activate venv ด้วย path ผิดรูปแบบ (`/c:/...`)**
   - สาเหตุ: ใช้ path แบบ Git Bash ใน PowerShell
   - แก้ไข: ใช้ `.\.venv\Scripts\Activate.ps1`
3. **หน่วยความต้านทานไม่ตรงกัน**
   - สาเหตุ: ฟอร์มเป็น kΩ แต่ backend ตีความเป็น Ω
   - แก้ไข: คูณ 1000 ใน `app._parse_inputs`
4. **Cutoff/Saturation แสดงค่าติดลบ**
   - แก้ไข: จัดการ Cutoff แยกและคืนกระแสศูนย์ พร้อม Warning

## แนวทางพัฒนาต่อ

- เพิ่ม bias แบบ Fixed / Emitter bias
- เพิ่มกราฟ load line
- เพิ่ม AC analysis และ Bode plot ในสัปดาห์ถัดไป
- เพิ่มการบันทึกประวัติการคำนวณ
