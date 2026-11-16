const adminTranslations = {
    "zh": {
        "stock_all": "全部庫存",
        "stock_low": "低庫存（≤ 2）",
        "stock_low_short": "低庫存",
        "equipment_count": "項設備",
        "clear_filters": "清除篩選",
        "adjust_stock": "調整庫存",
        "admin_box_search": "箱號、名稱或地點",
        "manage_equipment": "管理設備",
        "edit_box": "編輯備品箱",
        "edit_item": "編輯設備",
        "delete_box": "刪除備品箱",
        "delete_equipment": "刪除設備",
        "save": "儲存",
        "clear_selection": "取消選取",
        "adjust_method": "調整方式",
        "stock_add": "入庫補充",
        "stock_set": "盤點設定",
        "stock_add_qty": "本次入庫數量",
        "stock_set_qty": "盤點後總數",
        "current_stock": "目前庫存",
        "resulting_stock": "調整後庫存",
        "confirm_adjustment": "確認調整",
        "confirm_delete": "確認刪除",
        "delete_irreversible": "此操作無法復原。",
        "delete_contents": "將一併刪除箱內設備，項目數",
        "empty_equipment": "目前沒有設備，可從右上角新增。",
        "first_box": "先建立備品箱，再加入設備。",
        "saving": "儲存中…"
    },
    "en": {
        "stock_all": "All stock",
        "stock_low": "Low stock (≤ 2)",
        "stock_low_short": "Low stock",
        "equipment_count": "items",
        "clear_filters": "Clear filters",
        "adjust_stock": "Adjust stock",
        "admin_box_search": "Box code, name or location",
        "manage_equipment": "Manage equipment",
        "edit_box": "Edit box",
        "edit_item": "Edit equipment",
        "delete_box": "Delete box",
        "delete_equipment": "Delete equipment",
        "save": "Save",
        "clear_selection": "Clear selection",
        "adjust_method": "Adjustment method",
        "stock_add": "Restock",
        "stock_set": "Stocktake",
        "stock_add_qty": "Quantity to add",
        "stock_set_qty": "Counted total",
        "current_stock": "Current stock",
        "resulting_stock": "Resulting stock",
        "confirm_adjustment": "Confirm adjustment",
        "confirm_delete": "Confirm deletion",
        "delete_irreversible": "This action cannot be undone.",
        "delete_contents": "All equipment in this box will also be deleted. Item count",
        "empty_equipment": "No equipment yet. Add equipment using the button above.",
        "first_box": "Create a spare box to start adding equipment.",
        "saving": "Saving…"
    }
};
for (const language of ["zh", "en"]) Object.assign(i18nDictionary[language], adminTranslations[language]);
applyLanguage(currentLanguage);

const workspace = document.getElementById("adminWorkspace");
document.querySelectorAll("#main-content > .alert").forEach(alert => alert.classList.add("admin-feedback"));
const tabs = [...workspace.querySelectorAll("[data-admin-tab]")];
const boxFilter = document.getElementById("boxFilterSelect");
const itemSearch = document.getElementById("itemSearchInput");
const stockFilter = document.getElementById("stockFilter");
const boxSearch = document.getElementById("adminBoxSearch");
const qrFilter = document.getElementById("qrBoxSelect");
const itemRows = [...workspace.querySelectorAll(".item-row")].map(element => ({
    element, text: element.dataset.searchText.toLowerCase(),
    box: element.dataset.boxId, stock: Number(element.dataset.stock)
}));
const boxRows = [...workspace.querySelectorAll("[data-box-record]")];
const boxEditor = document.getElementById("boxEditor");
const itemEditor = document.getElementById("itemEditor");
const stockEditor = document.getElementById("stockEditor");
const deleteDialog = document.getElementById("deleteConfirm");
const photo = document.getElementById("itemCurrentPhoto");
const fileInput = document.getElementById("item-image");
let activeView = "items";
let boxRecord = null;
let itemRecord = null;
let stockRecord = null;
let imageObjectUrl = null;
let returnFocus = null;

function writeViewState(push = false) {
    const parameters = new URLSearchParams();
    parameters.set("view", activeView);
    if (boxFilter.value !== "ALL") parameters.set("box", boxFilter.value);
    if (itemSearch.value) parameters.set("q", itemSearch.value);
    if (stockFilter.value !== "ALL") parameters.set("stock", stockFilter.value);
    if (boxSearch.value) parameters.set("boxq", boxSearch.value);
    if (qrFilter.value !== "ALL") parameters.set("qr", qrFilter.value);
    const url = window.location.pathname + "?" + parameters;
    if (push) history.pushState(null, "", url);
    else history.replaceState(null, "", url);
}

function updateItems() {
    const query = itemSearch.value.trim().toLowerCase();
    let count = 0;
    for (const row of itemRows) {
        const matchesBox = boxFilter.value === "ALL" || row.box === boxFilter.value;
        const matchesStock = stockFilter.value === "ALL" ||
            (stockFilter.value === "low" && row.stock <= 2) ||
            (stockFilter.value === "empty" && row.stock === 0);
        row.element.hidden = !matchesBox || !matchesStock || !row.text.includes(query);
        if (!row.element.hidden) count++;
    }
    document.getElementById("itemResultCount").textContent = count;
    document.getElementById("noMatchingItems").hidden = count !== 0;
    document.querySelector("[data-reset-items]").hidden =
        !itemSearch.value && boxFilter.value === "ALL" && stockFilter.value === "ALL";
    const emptyMessage = document.querySelector("#noMatchingItems > p");
    emptyMessage.dataset.i18n = itemRows.length ? "no_item_matches" :
        boxFilter.options.length > 1 ? "empty_equipment" : "first_box";
    emptyMessage.textContent = i18nDictionary[currentLanguage][emptyMessage.dataset.i18n];
}

function updateBoxes() {
    const query = boxSearch.value.trim().toLowerCase();
    let count = 0;
    for (const row of boxRows) {
        row.hidden = !row.dataset.searchText.toLowerCase().includes(query);
        if (!row.hidden) count++;
    }
    const empty = document.getElementById("boxAdminEmpty");
    empty.hidden = count !== 0;
    empty.dataset.i18n = boxRows.length ? "no_box_matches" : "no_boxes";
    empty.textContent = i18nDictionary[currentLanguage][empty.dataset.i18n];
}

function updateQrCodes() {
    for (const card of workspace.querySelectorAll("[data-qr-box]")) {
        card.hidden = qrFilter.value !== "ALL" && card.dataset.qrBox !== qrFilter.value;
        if (activeView === "qr" && !card.hidden) {
            const image = card.querySelector("img");
            if (!image.hasAttribute("src")) image.src = image.dataset.qrSrc;
        }
    }
}

function selectView(view) {
    activeView = tabs.some(tab => tab.dataset.adminTab === view) ? view : "items";
    for (const tab of tabs) {
        const selected = tab.dataset.adminTab === activeView;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute("aria-controls")).hidden = !selected;
    }
    updateQrCodes();
}

function restoreViewState() {
    const parameters = new URLSearchParams(window.location.search);
    for (const [control, key, fallback] of [
        [boxFilter, "box", "ALL"], [stockFilter, "stock", "ALL"], [qrFilter, "qr", "ALL"]
    ]) {
        const requested = parameters.get(key);
        control.value = [...control.options].some(option => option.value === requested) ? requested : fallback;
    }
    itemSearch.value = parameters.get("q") || "";
    boxSearch.value = parameters.get("boxq") || "";
    selectView(parameters.get("view"));
    updateItems();
    updateBoxes();
}

tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
        selectView(tab.dataset.adminTab);
        writeViewState(true);
    });
    tab.addEventListener("keydown", event => {
        const directions = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: tabs.length - 1 - index };
        if (!(event.key in directions)) return;
        event.preventDefault();
        const next = tabs[(index + directions[event.key] + tabs.length) % tabs.length];
        next.click();
        next.focus();
    });
});
window.addEventListener("popstate", restoreViewState);

for (const control of [boxFilter, itemSearch, stockFilter]) {
    control.addEventListener(control === itemSearch ? "input" : "change", () => {
        updateItems();
        writeViewState();
    });
}
boxSearch.addEventListener("input", () => { updateBoxes(); writeViewState(); });
qrFilter.addEventListener("change", () => { updateQrCodes(); writeViewState(); });
document.querySelector("[data-reset-items]").addEventListener("click", () => {
    boxFilter.value = "ALL";
    stockFilter.value = "ALL";
    itemSearch.value = "";
    updateItems();
    writeViewState();
    itemSearch.focus();
});
workspace.querySelectorAll("[data-view-box]").forEach(button => {
    button.addEventListener("click", () => {
        boxFilter.value = button.dataset.viewBox;
        stockFilter.value = "ALL";
        itemSearch.value = "";
        selectView("items");
        updateItems();
        writeViewState(true);
        boxFilter.focus();
    });
});

function fillForm(form, values) {
    form.reset();
    for (const [name, value] of Object.entries(values)) {
        const control = form.elements.namedItem(name);
        if (control && control.type !== "file") control.value = value;
    }
}

function prepareEditor(modal, record) {
    modal.querySelector("[data-create-title]").hidden = Boolean(record);
    modal.querySelector("[data-edit-title]").hidden = !record;
    modal.querySelector(".btn-outline-danger").hidden = !record;
}

boxEditor.addEventListener("show.bs.modal", event => {
    const trigger = event.relatedTarget;
    if (trigger?.hasAttribute("data-return-editor")) return;
    boxRecord = trigger?.closest("[data-record]")?.dataset.record;
    boxRecord = boxRecord ? JSON.parse(boxRecord) : null;
    prepareEditor(boxEditor, boxRecord);
    fillForm(boxEditor.querySelector("form"), { ...boxRecord, action: boxRecord ? "edit_box" : "add_box" });
    returnFocus = trigger;
});

function releasePreviewUrl() {
    if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
    imageObjectUrl = null;
}

function showItemPhoto(source) {
    photo.hidden = !source;
    if (source) photo.src = source;
    else photo.removeAttribute("src");
}

itemEditor.addEventListener("show.bs.modal", event => {
    const trigger = event.relatedTarget;
    if (trigger?.hasAttribute("data-return-editor")) return;
    itemRecord = trigger?.closest("[data-record]")?.dataset.record;
    itemRecord = itemRecord ? JSON.parse(itemRecord) : null;
    prepareEditor(itemEditor, itemRecord);
    const defaults = { action: "add_item", stock: 0 };
    if (boxFilter.value !== "ALL") defaults.box_id = boxFilter.value;
    fillForm(itemEditor.querySelector("form"), itemRecord ? { ...itemRecord, action: "edit_item" } : defaults);
    const stockInput = document.getElementById("item-stock");
    stockInput.disabled = Boolean(itemRecord);
    stockInput.closest(".mb-3").hidden = Boolean(itemRecord);
    releasePreviewUrl();
    showItemPhoto(itemRecord?.image);
    document.querySelector("[data-clear-image]").hidden = true;
    returnFocus = trigger;
});
fileInput.addEventListener("change", () => {
    releasePreviewUrl();
    const file = fileInput.files[0];
    if (file) imageObjectUrl = URL.createObjectURL(file);
    showItemPhoto(imageObjectUrl || itemRecord?.image);
    document.querySelector("[data-clear-image]").hidden = !file;
});
document.querySelector("[data-clear-image]").addEventListener("click", () => {
    fileInput.value = "";
    fileInput.dispatchEvent(new Event("change"));
});

function updateStockPreview() {
    if (!stockRecord) return;
    const form = stockEditor.querySelector("form");
    const setTotal = form.elements.mode.value === "set";
    const quantity = form.elements.qty;
    quantity.min = setTotal ? "0" : "1";
    const label = stockEditor.querySelector("[data-quantity-label]");
    label.dataset.i18n = setTotal ? "stock_set_qty" : "stock_add_qty";
    label.textContent = i18nDictionary[currentLanguage][label.dataset.i18n];
    const result = quantity.value !== "" && quantity.validity.valid ?
        setTotal ? quantity.valueAsNumber : stockRecord.stock + quantity.valueAsNumber : null;
    stockEditor.querySelector("[data-stock-result]").textContent = result === null ? "\u2014" : result;
}
stockEditor.addEventListener("show.bs.modal", event => {
    stockRecord = JSON.parse(event.relatedTarget.closest("[data-record]").dataset.record);
    fillForm(stockEditor.querySelector("form"), { action: "update_stock", item_id: stockRecord.item_id });
    stockEditor.querySelector("[data-stock-name]").textContent = stockRecord.name;
    stockEditor.querySelector("[data-stock-pn]").textContent = stockRecord.mitac_pn;
    stockEditor.querySelector("[data-stock-current]").textContent = stockRecord.stock;
    updateStockPreview();
});
stockEditor.querySelector("[name=qty]").addEventListener("input", updateStockPreview);
stockEditor.querySelector("[name=mode]").addEventListener("change", () => {
    stockEditor.querySelector("[name=qty]").value = "";
    updateStockPreview();
    stockEditor.querySelector("[name=qty]").focus();
});
document.addEventListener("languagechange", updateStockPreview);

deleteDialog.addEventListener("show.bs.modal", event => {
    const isBox = event.relatedTarget.hasAttribute("data-delete-box");
    const record = isBox ? boxRecord : itemRecord;
    fillForm(deleteDialog.querySelector("form"), {
        action: isBox ? "delete_box" : "delete_item",
        box_id: isBox ? record.box_id : "", item_id: isBox ? "" : record.item_id
    });
    deleteDialog.querySelector("[data-delete-name]").textContent =
        record.name + "\u00b7" + " " + (isBox ? record.box_code : record.mitac_pn);
    deleteDialog.querySelector("[data-delete-box-warning]").hidden = !isBox;
    deleteDialog.querySelector("[data-delete-count]").textContent = isBox ? record.item_count : "";
    deleteDialog.querySelector("[data-return-editor]").setAttribute("data-bs-target", isBox ? "#boxEditor" : "#itemEditor");
});
deleteDialog.addEventListener("hidden.bs.modal", () => {
    if (!document.querySelector(".modal.show") && returnFocus) returnFocus.focus();
});

for (const modal of [boxEditor, itemEditor, stockEditor]) {
    modal.addEventListener("shown.bs.modal", () => {
        modal.querySelector("input:not([type=hidden]), select")?.focus();
    });
}
for (const form of document.querySelectorAll("[data-admin-form]")) {
    form.addEventListener("submit", event => {
        if (form.dataset.submitting) { event.preventDefault(); return; }
        form.dataset.submitting = "true";
        try {
            sessionStorage.setItem("admin_return", JSON.stringify({
                url: window.location.pathname + window.location.search,
                scroll: window.scrollY
            }));
        } catch {}
        form.setAttribute("aria-busy", "true");
        const button = event.submitter;
        if (button) {
            button.disabled = true;
            button.textContent = i18nDictionary[currentLanguage].saving;
        }
    });
}
try {
    const pending = JSON.parse(sessionStorage.getItem("admin_return") || "null");
    sessionStorage.removeItem("admin_return");
    if (pending && window.location.search === "" && pending.url.startsWith("/admin?")) {
        history.replaceState(null, "", pending.url);
        requestAnimationFrame(() => {
            window.scrollTo(0, pending.scroll);
        });
    }
} catch {}
restoreViewState();
writeViewState();
window.addEventListener("pageshow", event => {
    if (event.persisted) {
        document.querySelectorAll("[data-admin-form]").forEach(form => {
            delete form.dataset.submitting;
            form.removeAttribute("aria-busy");
            form.querySelectorAll("[type=submit]").forEach(button => { button.disabled = false; });
        });
        applyLanguage(currentLanguage);
        restoreViewState();
    }
});
