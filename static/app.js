/* สคริปต์เล็ก ๆ ฝั่ง client: ใส่ค่าตัวอย่าง และตรวจ input เบื้องต้นก่อนส่งฟอร์ม
   หมายเหตุ: ตรรกะคำนวณทั้งหมดอยู่ฝั่ง Python (dc_bias.py) ไม่ใช่ที่ไฟล์นี้ */
(function () {
    "use strict";

    /* --------------------------------------------------------------------------
     * Lab 04 — SPICE panel (ngspice)
     * ทุกผลลัพธ์ในส่วนนี้มาจาก fetch ไปที่ /api/spice ซึ่งรัน ngspice จริง
     * ถ้า error จะแจ้งแยกสีแดง แต่ยังคงผลสำเร็จล่าสุดไว้ให้เทียบต่อได้
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
    var engineReady = null;
    var engineHint = "";
    // เวลารอฝั่ง client มากกว่า TIMEOUT_S ของ server เล็กน้อย เผื่อ process ค้าง
    var REQUEST_TIMEOUT_MS = 35000;

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

    function setButtonsDisabled(disabled) {
        buttons.forEach(function (button) { button.disabled = disabled; });
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
        // ถ้ารู้แล้วว่า engine ไม่พร้อม อย่าส่งงานเข้า subprocess ที่ไม่มีตัวตน
        if (engineReady === false) {
            showError("Engine ngspice ไม่พร้อม — รัน SPICE ไม่ได้", engineHint);
            setStatus("ล้มเหลว — engine ไม่พร้อม ไม่ได้ส่งงานเข้า ngspice", "error");
            return;
        }

        clearError();
        setStatus("กำลังรัน ngspice (" + analysis + ")…", "running");
        setButtonsDisabled(true);

        var payload = circuitPayload();
        payload.analysis = analysis;

        var controller = typeof AbortController === "function" ? new AbortController() : null;
        var timer = null;
        if (controller) {
            timer = setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS);
        }
        var init = {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        };
        if (controller) {
            init.signal = controller.signal;
        }

        fetch("/api/spice", init).then(function (response) {
            return response.json().catch(function () {
                return { ok: false, error: "อ่านคำตอบจากเซิร์ฟเวอร์ไม่ได้" };
            }).then(function (body) {
                return { status: response.status, body: body };
            });
        }).then(function (result) {
            if (!result.body.ok || !(result.body.values || result.body.plot_svg || result.body.summary)) {
                var detail = result.body.detail || result.body.install_hint || "";
                showError(result.body.error || "ผลลัพธ์จาก ngspice ไม่สมบูรณ์", detail);
                setStatus("ล้มเหลว (HTTP " + result.status + ") — ไม่มีผลสำเร็จใหม่ ผลเก่าที่ยืนยันแล้วยังอยู่ด้านล่าง", "error");
                return;
            }
            render(result.body);
            setStatus("สำเร็จ — " + result.body.engine + " ใช้เวลา " + result.body.duration_ms + " ms", "ok");
        }).catch(function (error) {
            var aborted = error && (error.name === "AbortError" || /abort/i.test(String(error)));
            if (aborted) {
                showError("หมดเวลารอ ngspice — ยกเลิกการรันแล้ว", "");
                setStatus("ล้มเหลว — หมดเวลารอ ngspice ไม่ค้างอยู่ในสถานะกำลังรัน", "error");
            } else {
                showError("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้", String(error));
                setStatus("ล้มเหลว — เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ ผลเก่าที่ยืนยันแล้วยังอยู่ด้านล่าง", "error");
            }
        }).then(function () {
            if (timer) {
                clearTimeout(timer);
            }
            setButtonsDisabled(engineReady === false);
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
        engineReady = !!body.available;
        engineHint = body.install_hint || "";
        if (modelBadge) {
            modelBadge.textContent = "Model: " + body.model + " (" + body.model_definition + ")";
        }
        if (engineReady) {
            if (engineBadge) {
                engineBadge.textContent = "ngspice พร้อมใช้งาน · " + (body.engine || "ngspice");
                engineBadge.className = "badge ok";
            }
        } else {
            if (engineBadge) {
                engineBadge.textContent = "ไม่พบ ngspice";
                engineBadge.className = "badge bad";
            }
            showError("Engine ngspice ไม่พร้อม — รัน SPICE ไม่ได้", engineHint);
            setStatus("Engine ไม่พร้อม: " + engineHint, "error");
            setButtonsDisabled(true);
        }
    }).catch(function () {
        engineReady = false;
        if (engineBadge) {
            engineBadge.textContent = "ตรวจสอบสถานะ ngspice ไม่ได้";
            engineBadge.className = "badge bad";
        }
        showError("ตรวจสอบสถานะ ngspice ไม่ได้", "โหลด /api/spice/status ล้มเหลว — ระงับปุ่มรันไว้ก่อน");
        setStatus("ตรวจสอบสถานะ ngspice ไม่ได้ — ปุ่มรันถูกระงับไว้ก่อน", "error");
        setButtonsDisabled(true);
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

    var summary = document.getElementById("form-error-summary");
    var FIELD_LABELS = {
        vcc: "VCC", vbe: "VBE", r1: "R1", r2: "R2",
        rb: "RB", rc: "RC", re: "RE", beta: "β"
    };

    function errorId(field) {
        return (field.id || field.name) + "-error";
    }

    function setDescribedBy(field, id, add) {
        var parts = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
        var at = parts.indexOf(id);
        if (add && at === -1) {
            parts.push(id);
        } else if (!add && at !== -1) {
            parts.splice(at, 1);
        }
        if (parts.length) {
            field.setAttribute("aria-describedby", parts.join(" "));
        } else {
            field.removeAttribute("aria-describedby");
        }
    }

    function clearFieldError(field) {
        field.classList.remove("invalid");
        field.removeAttribute("aria-invalid");
        var id = errorId(field);
        setDescribedBy(field, id, false);
        var node = document.getElementById(id);
        if (node && node.parentNode) {
            node.parentNode.removeChild(node);
        }
    }

    function setFieldError(field, message) {
        field.classList.add("invalid");
        field.setAttribute("aria-invalid", "true");
        var id = errorId(field);
        setDescribedBy(field, id, true);
        var node = document.getElementById(id);
        if (!node) {
            node = document.createElement("span");
            node.className = "field-error";
            node.id = id;
            var anchor = field.closest ? field.closest(".field-group") : field;
            if (anchor && anchor.parentNode) {
                anchor.parentNode.insertBefore(node, anchor.nextSibling);
            }
        }
        node.textContent = message;
    }

    function clearAllErrors() {
        Array.prototype.forEach.call(form.querySelectorAll(".invalid"), function (field) {
            clearFieldError(field);
        });
        if (summary) {
            summary.hidden = true;
            summary.textContent = "";
        }
    }

    var fillBtn = document.getElementById("fill-example");
    if (fillBtn) {
        fillBtn.addEventListener("click", function () {
            clearAllErrors();
            Object.keys(EXAMPLE).forEach(function (name) {
                var field = form.elements[name];
                if (field) {
                    field.value = EXAMPLE[name];
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

        clearAllErrors();

        // หาโหมดปัจจุบันจากช่อง select
        var modeSelect = form.elements["mode"];
        var currentMode = modeSelect ? modeSelect.value : "divider";

        // ฟิลด์ที่ต้องตรวจสอบสำหรับแต่ละโหมด
        var MODE_FIELDS = {
            "divider": ["vcc", "r1", "r2", "rc", "re", "beta"],
            "fixed": ["vcc", "rb", "rc", "beta"],
            "emitter": ["vcc", "rb", "rc", "re", "beta"]
        };
        var relevantFields = MODE_FIELDS[currentMode] || [];
        var messages = [];

        Array.prototype.forEach.call(form.elements, function (field) {
            // ข้ามปุ่มและตัวเลือกหน่วย (ไม่ใช่ค่าตัวเลข)
            if (!field.name || field.type === "button" || field.type === "reset" ||
                field.type === "submit" || field.tagName === "SELECT") {
                return;
            }
            // ข้ามฟิลด์ที่ไม่เกี่ยวข้องกับโหมดปัจจุบัน
            if (relevantFields.indexOf(field.name) === -1) {
                return;
            }
            var value = (field.value || "").trim();
            var label = FIELD_LABELS[field.name] || field.name.toUpperCase();
            var message = "";

            if (value === "") {
                message = "กรุณากรอกค่า";
            } else if (isNaN(Number(value))) {
                message = "ต้องเป็นตัวเลข";
            } else if (Number(value) < 0) {
                message = "ค่าต้องไม่ติดลบ";
            }

            if (message) {
                setFieldError(field, message);
                messages.push(label + ": " + message);
            }
        });

        if (messages.length > 0) {
            event.preventDefault();
            if (summary) {
                summary.hidden = false;
                summary.textContent = "ตรวจสอบข้อมูลก่อนคำนวณ — " + messages.join(" · ");
            }
            var first = form.querySelector('[aria-invalid="true"]');
            if (first && first.focus) {
                first.focus();
            }
        }
    });
})();
