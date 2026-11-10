/* สคริปต์เล็ก ๆ ฝั่ง client: ใส่ค่าตัวอย่าง และตรวจ input เบื้องต้นก่อนส่งฟอร์ม
   หมายเหตุ: ตรรกะคำนวณทั้งหมดอยู่ฝั่ง Python (dc_bias.py) ไม่ใช่ที่ไฟล์นี้ */
(function () {
    "use strict";

    var EXAMPLE = {
        vcc: "12",
        r1: "100",
        r2: "22",
        rc: "2.2",
        re: "1",
        beta: "100",
        vbe: "0.70"
    };

    var form = document.getElementById("bias-form");
    if (!form) {
        return;
    }

    var fillBtn = document.getElementById("fill-example");
    if (fillBtn) {
        fillBtn.addEventListener("click", function () {
            Object.keys(EXAMPLE).forEach(function (name) {
                var field = form.elements[name];
                if (field) {
                    field.value = EXAMPLE[name];
                    field.classList.remove("invalid");
                }
            });
        });
    }

    form.addEventListener("submit", function (event) {
        var missing = [];

        Array.prototype.forEach.call(form.elements, function (field) {
            if (!field.name || field.type === "button" || field.type === "reset") {
                return;
            }
            var value = (field.value || "").trim();
            var isEmpty = value === "";
            var isNotNumber = !isEmpty && isNaN(Number(value));

            field.classList.toggle("invalid", isEmpty || isNotNumber);

            if (isEmpty || isNotNumber) {
                missing.push(field.id || field.name);
            }
        });

        if (missing.length > 0) {
            event.preventDefault();
            var first = form.elements[missing[0]];
            if (first && first.focus) {
                first.focus();
            }
        }
    });
})();
