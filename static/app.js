/* สคริปต์เล็ก ๆ ฝั่ง client: ใส่ค่าตัวอย่าง และตรวจ input เบื้องต้นก่อนส่งฟอร์ม
   หมายเหตุ: ตรรกะคำนวณทั้งหมดอยู่ฝั่ง Python (dc_bias.py) ไม่ใช่ที่ไฟล์นี้ */
(function () {
    "use strict";

    /* --------------------------------------------------------------------------
     * Lab 04 — SPICE panel (ngspice)
     * ทุกผลลัพธ์ในส่วนนี้มาจาก fetch ไปที่ /api/spice ซึ่งรัน ngspice จริง
     * ถ้า error จะล้างกราฟเดิมทิ้ง ไม่แสดงผลเก่าค้างไว้
     * ------------------------------------------------------------------------ */

    var panel = document.getElementById("spice-panel");
    if (!panel) {
        return;
    }

    var mainForm = document.getElementById("bias-form");
    var statusBox = document.getElementById("spice-status");
    var errorBox = document.getElementById("spice-error");
    var errorMessage = document.getElementById("spice-error-message");
    var errorDetail = document.getElementById("spice-error-detail");
    var output = document.getElementById("spice-output");
    var engineBadge = document.getElementById("spice-engine-badge");
    var modelBadge = document.getElementById("spice-model-badge");
    var amplitudeInput = document.getElementById("spice-amplitude");
    var amplitudeUnit = document.getElementById("spice-amplitude-unit");
    var frequencyInput = document.getElementById("spice-frequency");
    var frequencyUnit = document.getElementById("spice-frequency-unit");
    var buttons = Array.prototype.slice.call(panel.querySelectorAll("[data-spice-analysis]"));

    var CIRCUIT_FIELDS = ["vcc", "r1", "r2", "rc", "re", "beta"];

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined) {
            node.textContent = text;
        }
        return node;
    }

    function setStatus(text, kind) {
        if (!statusBox) {
            return;
        }
        statusBox.className = "note spice-status-" + (kind || "idle");
        statusBox.textContent = text;
    }

    function clearError() {
        if (!errorBox) {
            return;
        }
        errorBox.hidden = true;
        if (errorMessage) {
            errorMessage.textContent = "";
        }
        if (errorDetail) {
            errorDetail.hidden = true;
            errorDetail.textContent = "";
        }
    }

    function showError(message, detail) {
        clearOutput();
        if (!errorBox) {
            return;
        }
        errorBox.hidden = false;
        if (errorMessage) {
            errorMessage.textContent = message;
        }
        if (errorDetail) {
            if (detail) {
                errorDetail.hidden = false;
                errorDetail.textContent = detail;
            } else {
                errorDetail.hidden = true;
                errorDetail.textContent = "";
            }
        }
    }

    function clearOutput() {
        if (output) {
            output.textContent = "";
        }
    }

    function circuitPayload() {
        var payload = {};
        if (mainForm) {
            CIRCUIT_FIELDS.forEach(function (name) {
                var field = mainForm.elements[name];
                var unitField = mainForm.elements[name + "_unit"];
                // ส่ง key ทุกตัวเสมอ — ค่าที่เว้นว่างจะถูกแทนด้วยวงจรอ้างอิงฝั่ง server
                payload[name] = field ? field.value : "";
                if (unitField) {
                    payload[name + "_unit"] = unitField.value;
                }
            });
            var vbe = mainForm.elements["vbe"];
            var vbeUnit = mainForm.elements["vbe_unit"];
            if (vbe && String(vbe.value || "").trim() !== "") {
                payload.vbe = vbe.value;
            }
            if (vbeUnit) {
                payload.vbe_unit = vbeUnit.value;
            }
            var voltageDisplay = mainForm.elements["voltage_display"];
            var currentDisplay = mainForm.elements["current_display"];
            if (voltageDisplay) {
                payload.voltage_display = voltageDisplay.value;
            }
            if (currentDisplay) {
                payload.current_display = currentDisplay.value;
            }
        }
        payload.amplitude = amplitudeInput ? amplitudeInput.value : "10";
        payload.amplitude_unit = amplitudeUnit ? amplitudeUnit.value : "mV";
        payload.frequency = frequencyInput ? frequencyInput.value : "1000";
        payload.frequency_unit = frequencyUnit ? frequencyUnit.value : "Hz";
        return payload;
    }

    function summaryGrid(items) {
        var grid = el("div", "result-grid spice-summary");
        (items || []).forEach(function (item) {
            var box = el("div", "result-item");
            box.appendChild(el("span", "label", item.label));
            box.appendChild(el("span", "value", item.text));
            grid.appendChild(box);
        });
        return grid;
    }

    function comparisonTable(body) {
        var wrap = el("div", "table-wrap");
        var table = el("table");
        var thead = el("thead");
        var headRow = el("tr");
        ["ค่า", "SPICE (" + body.engine + ")", "Analytical (" + body.analytical.source + ")"].forEach(function (label) {
            headRow.appendChild(el("th", "", label));
        });
        thead.appendChild(headRow);
        table.appendChild(thead);

        var tbody = el("tbody");
        var COMPARE_ROWS = [
            ["VB", "vb"],
            ["VE", "ve"],
            ["VC", "vc"],
            ["VCE", "vce"],
            ["IB", "ib"],
            ["IC", "ic"],
            ["IE", "ie"]
        ];
        COMPARE_ROWS.forEach(function (row) {
            var tr = el("tr");
            tr.appendChild(el("th", "", row[0]));
            var spice = body.values ? body.values[row[1]] || {} : {};
            var ref = (body.analytical && body.analytical.values) ? (body.analytical.values[row[1]] || {}) : {};
            tr.appendChild(el("td", "", spice.text || "—"));
            tr.appendChild(el("td", "", ref.text || "—"));
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        wrap.appendChild(table);
        return wrap;
    }

    function metaLine(body) {
        var text = "Engine: " + body.engine + " · ใช้เวลา " + body.duration_ms + " ms · Model: " + body.model + " · Amplitude " + body.amplitude.text + " · Frequency " + body.frequency.text;
        return el("p", "spice-run-meta", text);
    }

    function warningsBlock(body) {
        if (!body.warnings || body.warnings.length === 0) {
            return null;
        }
        var note = el("div", "note");
        note.appendChild(el("strong", "", "⚠️ ngspice warnings:"));
        var list = el("ul");
        body.warnings.forEach(function (warning) {
            list.appendChild(el("li", "", warning));
        });
        note.appendChild(list);
        return note;
    }

    function rawDetails(body) {
        var details = el("details", "assumptions");
        details.appendChild(el("summary", "", "ดู netlist และ log จาก ngspice"));
        var pre = el("pre", "spice-log");
        pre.textContent = body.netlist + "--- ngspice log ---" + body.log;
        details.appendChild(pre);
        return details;
    }

    function render(body) {
        clearOutput();
        output.appendChild(metaLine(body));

        var heading = el("h3", "", "");
        if (body.analysis === "op") {
            heading.textContent = "ผล .op — SPICE เทียบกับ Analytical";
            output.appendChild(heading);
            output.appendChild(el("p", "hint", "โซนจาก Analytical: " + body.analytical.region));
            output.appendChild(comparisonTable(body));
        } else if (body.analysis === "ac") {
            heading.textContent = "ผล .ac — Bode plot (ขนาด dB และเฟส)";
            output.appendChild(heading);
            output.appendChild(summaryGrid(body.summary));
            output.appendChild(figure(body.plot_svg, "กราฟ Bode จาก ngspice (.ac) — แกนความถี่เป็น log scale"));
        } else {
            heading.textContent = "ผล .tran — รูปคลื่น Vin / Vout";
            output.appendChild(heading);
            output.appendChild(summaryGrid(body.summary));
            output.appendChild(figure(body.plot_svg, "รูปคลื่นจาก ngspice (.tran) — วัดที่โหนด in และ out"));
        }

        var warnings = warningsBlock(body);
        if (warnings) {
            output.appendChild(warnings);
        }
        output.appendChild(rawDetails(body));
    }

    function figure(svg, caption) {
        var box = el("figure", "figure");
        box.innerHTML = svg;
        box.appendChild(el("figcaption", "", caption));
        return box;
    }

    function runSpice(analysis) {
        clearError();
        clearOutput();
        setStatus("กำลังรัน ngspice (" + analysis + ")…", "running");
        buttons.forEach(function (button) { button.disabled = true; });

        var payload = circuitPayload();
        payload.analysis = analysis;

        fetch("/api/spice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }).then(function (response) {
            return response.json().catch(function () {
                return { ok: false, error: "อ่านคำตอบจากเซิร์ฟเวอร์ไม่ได้" };
            }).then(function (body) {
                return { status: response.status, body: body };
            });
        }).then(function (result) {
            if (!result.body.ok) {
                var detail = result.body.detail || result.body.install_hint || "";
                showError(result.body.error || "ไม่ทราบสาเหตุ", detail);
                setStatus("ล้มเหลว (HTTP " + result.status + ") — ไม่แสดงกราฟ", "error");
                return;
            }
            render(result.body);
            setStatus("สำเร็จ — " + result.body.engine + " ใช้เวลา " + result.body.duration_ms + " ms", "ok");
        }).catch(function (error) {
            showError("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้", String(error));
            setStatus("ล้มเหลว — เชื่อมต่อเซิร์ฟเวอร์ไม่ได้", "error");
        }).then(function () {
            buttons.forEach(function (button) { button.disabled = false; });
        });
    }

    buttons.forEach(function (button) {
        button.addEventListener("click", function () {
            runSpice(button.getAttribute("data-spice-analysis"));
        });
    });

    fetch("/api/spice/status").then(function (response) {
        return response.json();
    }).then(function (body) {
        if (modelBadge) {
            modelBadge.textContent = "Model: " + body.model + " (" + body.model_definition + ")";
        }
        if (body.available) {
            if (engineBadge) {
                engineBadge.textContent = "ngspice พร้อมใช้งาน · " + (body.engine || "ngspice");
                engineBadge.className = "badge ok";
            }
        } else {
            if (engineBadge) {
                engineBadge.textContent = "ไม่พบ ngspice";
                engineBadge.className = "badge bad";
            }
            setStatus("ยังไม่ได้ติดตั้ง ngspice: " + body.install_hint, "error");
        }
    }).catch(function () {
        if (engineBadge) {
            engineBadge.textContent = "ตรวจสอบสถานะ ngspice ไม่ได้";
            engineBadge.className = "badge bad";
        }
    });
})();

(function () {
    "use strict";

    var EXAMPLE = {
        vcc: "12",
        vbe: "0.70",
        rb: "1",
        r1: "100",
        r2: "22",
        rc: "2.2",
        re: "1",
        beta: "100"
    };

    var EXAMPLE_UNITS = {
        vcc_unit: "V",
        vbe_unit: "V",
        rb_unit: "MΩ",
        r1_unit: "kΩ",
        r2_unit: "kΩ",
        rc_unit: "kΩ",
        re_unit: "kΩ",
        voltage_display: "auto",
        current_display: "auto"
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
            Object.keys(EXAMPLE_UNITS).forEach(function (name) {
                var field = form.elements[name];
                if (field && field.tagName === "SELECT") {
                    field.value = EXAMPLE_UNITS[name];
                }
            });
        });
    }

    form.addEventListener("submit", function (event) {
        // ปุ่มเปลี่ยนโหมดเป็น GET เพื่อโหลดฟอร์มใหม่ ไม่ต้องตรวจค่าที่ยังกรอกไม่ครบ
        if (event.submitter && event.submitter.name === "apply_mode") {
            return;
        }
        var missing = [];

        Array.prototype.forEach.call(form.elements, function (field) {
            // ข้ามปุ่มและตัวเลือกหน่วย (ไม่ใช่ค่าตัวเลข)
            if (!field.name || field.type === "button" || field.type === "reset" ||
                field.type === "select-one" || field.tagName === "SELECT") {
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
