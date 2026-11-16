const circulationTranslations = {
    zh: {
        download_excel: "下載 Excel", downloading_excel: "下載中…", download_failed: "下載失敗，請再試一次。",
        loan_search_short: "設備、借用人、料號或序號", all_projects: "全部專案",
        record_count: "筆紀錄", clear_filters: "清除篩選", return_equipment: "歸還",
        confirm_return: "確認歸還", save_loan: "儲存借用紀錄", delete_irreversible: "此操作無法復原。",
        saving: "儲存中…", search_records: "搜尋領取紀錄", record_search_hint: "設備、料號、操作人員或備註",
        quantity_change: "異動數量", text_required: "請填寫此欄位。"
    },
    en: {
        download_excel: "Download Excel", downloading_excel: "Downloading…", download_failed: "Download failed. Please try again.",
        loan_search_short: "Equipment, borrower, part number or serial", all_projects: "All projects",
        record_count: "records", clear_filters: "Clear filters", return_equipment: "Return",
        confirm_return: "Confirm return", save_loan: "Save loan", delete_irreversible: "This action cannot be undone.",
        saving: "Saving…", search_records: "Search stock history", record_search_hint: "Equipment, part number, operator or note",
        quantity_change: "Quantity change", text_required: "Please fill in this field."
    }
};
for (const language of ["zh", "en"]) Object.assign(i18nDictionary[language], circulationTranslations[language]);
applyLanguage(currentLanguage);

const circulationWorkspace = document.getElementById("loanWorkspace") || document.getElementById("recordWorkspace");
const isLoanPage = circulationWorkspace.id === "loanWorkspace";
const searchInput = document.getElementById(isLoanPage ? "loanSearchInput" : "recordSearch");
const statusSelect = document.getElementById(isLoanPage ? "loanStatusFilter" : "recordAction");
const projectSelect = document.getElementById("loanProjectFilter");
const entries = [...circulationWorkspace.querySelectorAll(isLoanPage ? ".loan-entry" : ".record-entry")].map(element => ({
    element, text: element.dataset.search.toLowerCase(),
    status: isLoanPage ? element.dataset.status : element.dataset.action,
    project: element.dataset.project, overdue: element.dataset.overdue === "true"
}));
const downloadButton = document.querySelector("[data-excel-download]");
const emptyMessage = document.querySelector("#circulationEmpty > p");
const clearButton = document.querySelector("[data-clear-circulation]");
const filterControls = isLoanPage ?
    [[searchInput, "q"], [statusSelect, "status"], [projectSelect, "project"]] :
    [[searchInput, "q"], [statusSelect, "action"]];

function storeCirculationFilters() {
    const parameters = new URLSearchParams();
    for (const [control, key] of filterControls) {
        if (control.value) parameters.set(key, control.value);
    }
    history.replaceState(null, "", window.location.pathname + "?" + parameters);
}

function updateCirculation() {
    const query = searchInput.value.trim().toLowerCase();
    let count = 0;
    for (const entry of entries) {
        const statusMatches = statusSelect.value === "ALL" ||
            (statusSelect.value === "OVERDUE" ? entry.overdue : entry.status === statusSelect.value);
        const projectMatches = !projectSelect || !projectSelect.value || entry.project === projectSelect.value;
        entry.element.hidden = !statusMatches || !projectMatches || !entry.text.includes(query);
        if (!entry.element.hidden) count++;
    }
    document.getElementById("circulationCount").textContent = count;
    document.getElementById("circulationEmpty").hidden = count > 0;
    emptyMessage.dataset.i18n = entries.length ? "no_search_matches" : isLoanPage ? "no_loan_records" : "no_records";
    emptyMessage.textContent = i18nDictionary[currentLanguage][emptyMessage.dataset.i18n];
    clearButton.hidden = !searchInput.value && statusSelect.value === "ALL" && (!projectSelect || !projectSelect.value);
}

function restoreCirculationFilters() {
    const parameters = new URLSearchParams(window.location.search);
    for (const [control, key] of filterControls) {
        const value = parameters.get(key) || "";
        if (control.tagName === "SELECT") {
            control.value = [...control.options].some(option => option.value === value) ? value :
                key === "project" ? "" : "ALL";
        } else {
            control.value = value;
        }
    }
    updateCirculation();
}
for (const [control] of filterControls) {
    control.addEventListener(control === searchInput ? "input" : "change", () => {
        updateCirculation();
        storeCirculationFilters();
    });
}
clearButton.addEventListener("click", () => {
    searchInput.value = "";
    statusSelect.value = "ALL";
    if (projectSelect) projectSelect.value = "";
    updateCirculation();
    storeCirculationFilters();
    searchInput.focus();
});
window.addEventListener("popstate", restoreCirculationFilters);

downloadButton.addEventListener("click", async () => {
    const error = document.querySelector("[data-export-error]");
    error.hidden = true;
    downloadButton.disabled = true;
    downloadButton.setAttribute("aria-busy", "true");
    downloadButton.dataset.i18n = "downloading_excel";
    downloadButton.textContent = i18nDictionary[currentLanguage].downloading_excel;
    let objectUrl;
    try {
        const url = new URL(downloadButton.dataset.excelDownload, window.location.origin);
        for (const [control, key] of filterControls) url.searchParams.set(key, control.value);
        url.searchParams.set("lang", currentLanguage);
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok || !response.headers.get("Content-Type")?.includes("spreadsheetml.sheet")) {
            throw new Error("Excel response was not available");
        }
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        const filename = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/);
        link.href = objectUrl;
        link.download = filename ? filename[1] : "records.xlsx";
        document.body.append(link);
        link.click();
        link.remove();
    } catch {
        error.textContent = i18nDictionary[currentLanguage].download_failed;
        error.hidden = false;
    } finally {
        if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
        downloadButton.disabled = false;
        downloadButton.removeAttribute("aria-busy");
        downloadButton.dataset.i18n = "download_excel";
        downloadButton.textContent = i18nDictionary[currentLanguage].download_excel;
    }
});

function setupLoanEditor() {
    const editor = document.getElementById("loanEditor");
    const form = editor.querySelector("form");
    const returnDialog = document.getElementById("loanReturn");
    const deleteDialog = document.getElementById("loanDelete");
    const today = circulationWorkspace.dataset.today;
    const isAdmin = circulationWorkspace.dataset.admin === "true";
    let currentRecord = null;
    let returnFocus = null;

    const dateInputs = ["expected_return_date", "actual_return_date"].map(name => form.elements.namedItem(name));
    function updateDateConstraints() {
        const borrowedOn = form.elements.borrow_date.value;
        for (const input of dateInputs) {
            if (borrowedOn) input.min = borrowedOn;
            else input.removeAttribute("min");
        }
    }
    function updateReturnDate() {
        const returned = form.elements.status.value === "已歸還";
        form.elements.actual_return_date.required = returned;
        if (returned && !form.elements.actual_return_date.value) form.elements.actual_return_date.value = today;
    }

    editor.addEventListener("show.bs.modal", event => {
        if (event.relatedTarget?.hasAttribute("data-back-editor")) return;
        returnFocus = event.relatedTarget;
        currentRecord = event.relatedTarget?.closest("[data-record]")?.dataset.record;
        currentRecord = currentRecord ? JSON.parse(currentRecord) : null;
        form.reset();
        form.querySelector("[data-legacy-status]")?.remove();
        for (const input of form.querySelectorAll("input,textarea")) input.setCustomValidity("");
        if (currentRecord && ![...form.elements.status.options].some(option => option.value === currentRecord.status)) {
            const option = new Option(currentRecord.status, currentRecord.status);
            option.dataset.legacyStatus = "true";
            form.elements.status.append(option);
        }
        const values = currentRecord || { borrow_date: today, status: "已借出", project_name: projectSelect.value };
        for (const [name, value] of Object.entries(values)) {
            const control = form.elements.namedItem(name);
            if (control) control.value = value;
        }
        form.action = currentRecord ? "/loans/update/" + currentRecord.id : "/loans/add";
        editor.querySelector("[data-create-title]").hidden = Boolean(currentRecord);
        editor.querySelector("[data-edit-title]").hidden = !currentRecord;
        editor.querySelector("[data-edit-fields]").hidden = !currentRecord;
        const deleteButton = editor.querySelector("[data-delete-loan]");
        if (deleteButton) deleteButton.hidden = !currentRecord;
        for (const control of editor.querySelectorAll(".loan-primary-fields input")) {
            control.readOnly = Boolean(currentRecord) && !isAdmin;
        }
        form.elements.actual_return_date.required = Boolean(currentRecord) && currentRecord.status === "已歸還";
        updateDateConstraints();
    });
    form.elements.borrow_date.addEventListener("change", updateDateConstraints);
    form.elements.status.addEventListener("change", updateReturnDate);

    const email = form.elements.borrower_email;
    function completeEmail() {
        const value = email.value.trim();
        if (!email.readOnly && value && !value.includes("@")) email.value = value + "@mitaccomputing.com";
    }
    email.addEventListener("blur", completeEmail);
    form.addEventListener("submit", completeEmail);

    returnDialog.addEventListener("show.bs.modal", event => {
        const record = JSON.parse(event.relatedTarget.closest("[data-record]").dataset.record);
        returnDialog.querySelector("form").reset();
        returnDialog.querySelector("form").action = "/loans/return/" + record.id;
        returnDialog.querySelector("[data-return-name]").textContent = record.device_name;
        returnDialog.querySelector("[data-return-borrower]").textContent = record.borrower;
        const date = returnDialog.querySelector("[name=actual_return_date]");
        date.value = today;
        date.min = record.borrow_date;
    });

    if (deleteDialog) {
        deleteDialog.addEventListener("show.bs.modal", () => {
            deleteDialog.querySelector("form").action = "/loans/delete/" + currentRecord.id;
            deleteDialog.querySelector("[data-delete-name]").textContent =
                currentRecord.device_name + " · " + currentRecord.borrower;
        });
        deleteDialog.addEventListener("hidden.bs.modal", () => {
            if (!document.querySelector(".modal.show")) returnFocus?.focus();
        });
    }
    circulationWorkspace.addEventListener("click", event => {
        const button = event.target.closest("[data-loan-detail]");
        if (!button) return;
        const details = document.getElementById(button.getAttribute("aria-controls"));
        details.hidden = !details.hidden;
        button.setAttribute("aria-expanded", String(!details.hidden));
    });

    for (const modal of document.querySelectorAll(".circulation-modal")) {
        modal.addEventListener("shown.bs.modal", () => {
            modal.querySelector("input:not([readonly]),textarea")?.focus();
        });
    }
    for (const input of form.querySelectorAll("input[required][type=text]")) {
        input.addEventListener("input", () => input.setCustomValidity(
            input.value.trim() ? "" : i18nDictionary[currentLanguage].text_required
        ));
    }
    for (const loanForm of document.querySelectorAll("[data-loan-form]")) {
        loanForm.addEventListener("submit", event => {
            if (loanForm.dataset.submitting) { event.preventDefault(); return; }
            loanForm.dataset.submitting = "true";
            try {
                sessionStorage.setItem("loan_return", JSON.stringify({
                    url: window.location.pathname + window.location.search,
                    scroll: window.scrollY
                }));
            } catch {}
            loanForm.setAttribute("aria-busy", "true");
            if (event.submitter) {
                event.submitter.disabled = true;
                event.submitter.textContent = i18nDictionary[currentLanguage].saving;
            }
        });
    }
}

if (isLoanPage) {
    document.querySelectorAll("#main-content > .alert").forEach(alert => alert.classList.add("circulation-feedback"));
    try {
        const pending = JSON.parse(sessionStorage.getItem("loan_return") || "null");
        sessionStorage.removeItem("loan_return");
        if (pending && window.location.search === "" && pending.url.startsWith("/loans?")) {
            history.replaceState(null, "", pending.url);
            requestAnimationFrame(() => window.scrollTo(0, pending.scroll));
        }
    } catch {}
    setupLoanEditor();
}
restoreCirculationFilters();
storeCirculationFilters();
window.addEventListener("pageshow", event => {
    if (event.persisted) {
        document.querySelectorAll("[data-loan-form]").forEach(form => {
            delete form.dataset.submitting;
            form.removeAttribute("aria-busy");
            form.querySelectorAll("[type=submit]").forEach(button => { button.disabled = false; });
        });
        applyLanguage(currentLanguage);
        restoreCirculationFilters();
    }
});
