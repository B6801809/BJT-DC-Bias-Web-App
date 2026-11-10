# BJT DC Bias Web App

เว็บแอปพลิเคชัน Flask สำหรับคำนวณ **DC Operating Point** ของวงจร BJT NPN
Common-Emitter แบบ **Voltage-Divider Bias** (ENG29 2121 · Lab 02)

## ภาพรวม

- Frontend: ฟอร์ม HTML + CSS (Jinja template)
- Backend: Flask รับ HTTP request แล้วเรียกฟังก์ชันคำนวณใน Python
- Engineering logic แยกอยู่ใน `dc_bias.py` (ไม่รู้จัก HTML/HTTP)
- มี automated tests ทั้ง unit test และ Flask HTTP test

## ข้อกำหนดเบื้องต้น

- Python 3.10 ขึ้นไป
- Git (สำหรับ clone repository)

## การติดตั้งและรัน

```powershell
# 1) เข้าโฟลเดอร์โปรเจกต์
cd "C:\path\to\BJT DC Bias Web App"

# 2) สร้าง virtual environment
python -m venv .venv

# 3) เปิดใช้งาน (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 4) ติดตั้ง dependencies
python -m pip install -r requirements.txt

# 5) รันเว็บ
python -m flask --app app run --debug
```

เปิดเบราว์เซอร์ที่ <http://127.0.0.1:5000/>

> หมายเหตุ: ต้องเปิดผ่าน Flask local server เท่านั้น ไม่ใช่ double-click เปิดไฟล์
> `templates/index.html` ด้วย `file://`

## วิธีใช้

1. กรอกค่า VCC (V), VBE (V) และค่าความต้านทาน R1, R2, RC, RE เป็น **kΩ**
2. กรอก β
3. กด **Calculate DC Bias**
4. ระบบจะแสดง VB, VE, VC, VCE (V), IB (μA), IC/IE (mA), VTH, RTH และโซนการทำงาน
5. หากอินพุตผิดหรืออยู่นอกย่าน Forward-Active จะมี Error/Warning แจ้ง

### ค่าตัวอย่างสำหรับทดสอบ

| พารามิเตอร์ | ค่า |
|---|---|
| VCC | 12 V |
| R1 | 100 kΩ |
| R2 | 22 kΩ |
| RC | 2.2 kΩ |
| RE | 1 kΩ |
| β | 100 |
| VBE | 0.70 V |

ผลลัพธ์อ้างอิง (Forward-Active):

| ค่า | ผลลัพธ์ |
|---|---|
| IB | 12.30 μA |
| IC | 1.23 mA |
| IE | 1.24 mA |
| VB | 1.942 V |
| VE | 1.242 V |
| VC | 9.294 V |
| VCE | 8.052 V |

## สมการที่ใช้

```
VTH = VCC · R2 / (R1 + R2)
RTH = R1·R2 / (R1 + R2)
IB  = (VTH − VBE) / (RTH + (β+1)·RE)
IC  = β·IB
IE  = (β+1)·IB
VE  = IE·RE
VB  = VE + VBE
VC  = VCC − IC·RC
VCE = VC − VE
```

สมมติฐาน: โหมด Forward-Active, β คงที่, VBE คงที่

## การทดสอบ

```powershell
python -m unittest discover -s tests -v
```

## โครงสร้างโปรเจกต์

```
BJT DC Bias Web App/
├── app.py                  # Flask routes
├── dc_bias.py              # Engineering calculations
├── templates/index.html    # Input form + results (Jinja)
├── static/style.css        # Layout / presentation
├── tests/
│   ├── test_dc_bias.py     # Unit tests (engineering math)
│   └── test_web.py         # Flask HTTP tests
├── docs/
│   ├── design-note.md
│   ├── validation.md
│   └── reflection.md
├── requirements.txt
├── AGENTS.md
└── README.md
```

## ข้อจำกัด

แบบจำลองนี้ไม่ใช่ SPICE และใช้ได้ดีเฉพาะย่าน Forward-Active
หากวงจรอยู่ในย่าน Cutoff หรือ Saturation เว็บจะแสดง Warning
และไม่ควรถือค่าที่คำนวณได้เป็นผลลัพธ์ที่แม่นยำ
