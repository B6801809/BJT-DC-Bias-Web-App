# AGENTS.md — แนวทางการทำงานของ AI ในโปรเจกต์นี้

## หลักการ

- แยกความรับผิดชอบตามไฟล์: `app.py` (HTTP/Flask), `dc_bias.py` (วิศวกรรม), `circuit.py` (ภาพ SVG), `templates/` (HTML), `static/` (CSS/JS), `tests/` (การทดสอบ)
- `dc_bias.py` ต้องไม่ import Flask หรือรู้จัก HTML/HTTP
- `circuit.py` ต้องคืนค่าเป็นข้อความ SVG เท่านั้น และห้าม import Flask เช่นกัน
- ห้ามฝังสมการฟิสิกส์หรือค่าคำตอบไว้ใน template
- ทุกการเปลี่ยนตรรกะคำนวณต้องมี test รองรับ

## ภาพประกอบ (SVG)

- วาดภาพด้วย Python ล้วน ไม่ใช้ matplotlib หรือไลบรารีภายนอก
- ค่าที่แทรกใน SVG ต้องมาจากการ format ตัวเลขของเราเอง และ escape ข้อความก่อนใส่
- จุด Q ที่วาดต้องอยู่บน DC load line เสมอ (มี test ยืนยัน)
- สีและขนาดกำหนดใน `static/style.css` เท่าที่ทำได้

## หน่วย

- ฟอร์มรับความต้านทานเป็น kΩ และแปลงเป็น Ω ที่ชั้น `app.py`
- ฟังก์ชันใน `dc_bias.py` รับ/คืนหน่วย SI (Ω, V, A)
- แสดงผลต้องมีหน่วยกำกับเสมอ

## การตรวจสอบ

- รัน `python -m unittest discover -s tests -v` ก่อน commit ทุกครั้ง
- รักษา Warning สำหรับ Cutoff/Saturation ไว้เสมอ
- ห้าม commit `.venv/`, `.env` หรือ credentials

## รูปแบบโค้ด

- Python ใช้ type hints และ docstring
- ข้อความบน UI เป็นภาษาไทยที่อ่านเข้าใจง่าย
