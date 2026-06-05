const state = {
  bootstrap: null,
  selectedFormSlug: null,
  loadedForm: null,
  baselineDraft: null,
  draft: null,
  dirty: false,
  ui: {
    libraryOpen: false,
    previewOpen: false,
    advancedMode: false,
    focusPane: "setup",
    setupOpen: true,
    saveOpen: false,
    openSectionPaths: [],
    openFieldDetailPaths: [],
    activeItemPath: null,
    activeOptionToken: null,
    activePreviewSectionId: null,
    printPreview: {
      status: "idle",
      html: "",
      signature: "",
      error: "",
    },
  },
};

const sortableInstances = [];

const INPUT_TYPES = [
  { id: "text", label: "Text", control: "input", dataType: "text" },
  { id: "number", label: "Number", control: "input", dataType: "number" },
  { id: "choice", label: "Choice", control: "select", dataType: "enum" },
  { id: "image", label: "Image", control: "input", dataType: "image" },
  { id: "date", label: "Date", control: "input", dataType: "date" },
  { id: "time", label: "Time", control: "input", dataType: "time" },
  { id: "datetime", label: "Date & time", control: "input", dataType: "datetime" },
];
const ACTIVE_BLOCK_SCHEMA_SOURCE = "builder_blocks_v1";
const DEFAULT_PRINT_ACCENT_COLOR = "#1e5d52";
const PRINT_SUMMARY_SOURCES = [
  { id: "field", label: "Field" },
  { id: "primary_identity", label: "Primary label" },
  { id: "secondary_identity", label: "Secondary label" },
  { id: "record_key", label: "Record key" },
  { id: "issued_at", label: "Issued" },
  { id: "form_version", label: "Form version" },
];
const PRINT_SIGNATURE_SOURCES = [
  { id: "blank", label: "Blank line" },
  { id: "prepared_by", label: "Prepared by" },
  { id: "manual", label: "Manual name" },
  { id: "field", label: "Form field" },
];
const PRINT_FONT_FAMILIES = [
  { id: "arial", label: "Arial", description: "Neutral clinic document" },
  { id: "arial_narrow", label: "Arial Narrow", description: "Compact printed form" },
  { id: "aptos", label: "Aptos", description: "Modern Windows" },
  { id: "segoe_ui", label: "Segoe UI", description: "Clean screen/print" },
  { id: "cambria_title", label: "Cambria title", description: "Formal title, clean body" },
  { id: "georgia_title", label: "Georgia title", description: "Classic title, clean body" },
  { id: "times_new_roman", label: "Times New Roman", description: "Traditional report" },
  { id: "bahnschrift_title", label: "Bahnschrift title", description: "Modern compact title" },
];
const DEFAULT_PATIENT_REQUESTING_PHYSICIAN_OPTIONS = [
  "DR. RAUL VILLAR",
  "DR. LAVINIA BELTIJAR",
  "DR. MELWANI GARRIDO",
  "DR. MARIANIDA SISANTE",
  "DR. LEONA CARMEN SISANTE",
  "DR. ALMA LOWENA ANACAY",
  "DR. MARIBENZ ANGON",
  "DR. NELSON PIPIT",
  "DR. ELENITA SISAYAN",
  "DR. GIELZEN JOI SISAYAN",
  "DR. PERLITA CASTRO",
  "DR. BAYANI PASCO",
  "DR. DEXTER SCHROTH",
  "DR. JAYMEE SCHROTH",
  "DR. AIKO SALORSANO",
  "DR. LUCILA OBILLO",
  "DR. NOEL OBILLO",
  "DR. ARNEL MILAY",
  "DR. CANARIE JOY ESGUERRA",
  "DR. ELIZABETH PANGANIBAN",
  "DR. DONNALIZA CRUZ",
  "DR. CHERRIE ANN ANGON",
  "DR. HANNA TRISSIA SUMABONG",
  "DR. JERICA CRISTEL ESGUERRA",
  "DR. KENNETH JAVIER",
  "DR. VERONICA ALERTA",
  "DR. ANGELA FERNANDO",
  "DR. LYSSEL SARACANLAO",
  "DR. IDGEE GABRIEL BONDOC",
];
const DEFAULT_PATIENT_ROOM_OPTIONS = [
  "ST. THOMAS",
  "ST. ANDREW",
  "ST. JOSEPH",
  "ST. FRANCIS",
  "ST. TIMOTHY",
  "ST. PAUL",
  "ST. JOHN",
  "ST. GABRIEL",
  "ST. ANTHONY",
  "ST. PETER",
  "ST. MATTHEW",
  "ST. DOMINIC",
  "ST. AUGUSTINE",
  "ST. JAMES",
  "ST. MICHAEL",
  "ST. LUKE",
  "ST. LOUIE",
  "ST. JUDE",
  "NICU",
  "OPD",
  "ER",
];
const DEFAULT_MEDTECH_SIGNATORY_OPTIONS = [
  { id: "imelda_a_elemia", name: "Imelda A. Elemia, RMT", license: "0036643" },
  { id: "crystel_c_tesoro", name: "Crystel C. Tesoro, RMT", license: "0103760" },
  { id: "ma_jesusa_b_vite", name: "Ma. Jesusa B. Vite, RMT", license: "0118710" },
  { id: "andrea_coleen_a_avellones", name: "Andrea Coleen A. Avellones, RMT", license: "0119501" },
  { id: "julie_kyle_a_ronato", name: "Julie Kyle A. Ronato, RMT", license: "0119616" },
  { id: "shiela_mae_d_libradilla", name: "Shiela Mae D. Libradilla, RMT", license: "0135995" },
];
const DEFAULT_PATHOLOGIST_SIGNATORY_OPTIONS = [
  { id: "bernardita_mojica_figueroa", name: "Bernardita Mojica Figueroa, MD, DPSP", license: "068053" },
];
const SIGNATORY_INPUT_TYPES = [
  { id: "person_dropdown", label: "Person choice" },
  { id: "fixed", label: "Fixed person" },
  { id: "stamp_image", label: "Fixed stamp image" },
  { id: "manual", label: "Manual entry" },
  { id: "blank", label: "Blank line" },
];
const DEFAULT_PRINT_SUMMARY_ITEMS = [
  { id: "summary_primary", label: "Record", source: "primary_identity", field_id: "" },
  { id: "summary_secondary", label: "Detail", source: "secondary_identity", field_id: "" },
  { id: "summary_issued", label: "Issued", source: "issued_at", field_id: "" },
  { id: "summary_version", label: "Form version", source: "form_version", field_id: "" },
];
const DEFAULT_PATIENT_INFO_FIELDS = [
  { key: "name", name: "Name", dataType: "text", required: true },
  { key: "age", name: "Age", dataType: "text", required: false },
  {
    key: "sex",
    name: "Sex",
    control: "select",
    dataType: "enum",
    options: ["Male", "Female"],
    required: false,
  },
  { key: "date_or_datetime", name: "Date / Date-Time", dataType: "datetime", required: false },
  {
    key: "requesting_physician",
    name: "Requesting Physician",
    control: "select",
    dataType: "enum",
    options: DEFAULT_PATIENT_REQUESTING_PHYSICIAN_OPTIONS,
    required: false,
  },
  {
    key: "room",
    name: "Room",
    control: "select",
    dataType: "enum",
    options: DEFAULT_PATIENT_ROOM_OPTIONS,
    required: false,
  },
  { key: "case_number", name: "Case Number", dataType: "text", required: true },
];

const initialFormSlug = document.body?.dataset?.initialFormSlug || "";
const initialBuilderMode = document.body?.dataset?.initialBuilderMode || "";
const initialQuery = new URLSearchParams(window.location.search);

const formListEl = document.getElementById("formList");
const formSearchEl = document.getElementById("formSearch");
const statusTextEl = document.getElementById("statusText");
const dirtyBadgeEl = document.getElementById("dirtyBadge");
const formEditorEl = document.getElementById("formEditor");
const builderOutlineEl = document.getElementById("builderOutline");
const previewCanvasEl = document.getElementById("previewCanvas");
const jsonOutputEl = document.getElementById("jsonOutput");
const drawerScrimEl = document.getElementById("drawerScrim");
const workspaceShellEl = document.getElementById("workspaceShell") || document.querySelector(".workspace-shell") || document.querySelector(".stage-shell");
const libraryDrawerEl = document.getElementById("libraryDrawer");
const previewPanelEl = document.getElementById("previewPanel") || document.getElementById("previewDrawer");
const currentFormNameEl = document.getElementById("currentFormName");
const currentFormMetaEl = document.getElementById("currentFormMeta");
const stageTitleEl = document.getElementById("stageTitle");
const stageDescriptionEl = document.getElementById("stageDescription");
const previewCalloutTitleEl = document.getElementById("previewCalloutTitle");
const previewCalloutMetaEl = document.getElementById("previewCalloutMeta");
const openPreviewBtnEl = document.getElementById("openPreviewBtn");
const closePreviewBtnEl = document.getElementById("closePreviewBtn");
const toggleAdvancedBtnEl = document.getElementById("toggleAdvancedBtn");
const saveBtnEl = document.getElementById("saveBtn");
const saveDockEl = document.getElementById("saveDock");
const saveDockTitleEl = document.getElementById("saveDockTitle");
const saveDockMetaEl = document.getElementById("saveDockMeta");
const saveDockBtnEl = document.getElementById("saveDockBtn");
const resetDraftBtnEl = document.getElementById("resetDraftBtn");
const devPanelEl = document.querySelector(".dev-panel");
const dialogScrimEl = document.getElementById("dialogScrim");
const confirmDialogEl = document.getElementById("confirmDialog");
const confirmDialogEyebrowEl = document.getElementById("confirmDialogEyebrow");
const confirmDialogTitleEl = document.getElementById("confirmDialogTitle");
const confirmDialogMessageEl = document.getElementById("confirmDialogMessage");
const confirmDialogCancelBtnEl = document.getElementById("confirmDialogCancelBtn");
const confirmDialogAltBtnEl = document.getElementById("confirmDialogAltBtn");
const confirmDialogConfirmBtnEl = document.getElementById("confirmDialogConfirmBtn");

let dialogResolver = null;
let dialogReturnFocusEl = null;
let allowIntentionalUnload = false;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function parsePositiveInt(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "item";
}

function normalizeArray(value) {
  return Array.isArray(value) ? value : [];
}

function splitLines(value) {
  return String(value || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function compactText(value) {
  return String(value || "").trim();
}

function blockKind(node) {
  return String(node?.kind || "").trim();
}

function getDraftFormKey(draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return "";
  }
  const meta = ensureBlockSchemaMeta(draft);
  return compactText(meta?.form_key) || slugify(draft.name || "untitled_form") || "untitled_form";
}

function setDraftFormKey(value, draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return;
  }
  const meta = ensureBlockSchemaMeta(draft);
  meta.form_key = compactText(value) || slugify(draft.name || "untitled_form") || "untitled_form";
}

function getDraftFormNotes(draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return [];
  }
  const meta = ensureBlockSchemaMeta(draft);
  return normalizeArray(meta?.notes);
}

function setDraftFormNotes(value, draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return;
  }
  const meta = ensureBlockSchemaMeta(draft);
  const notes = normalizeArray(value);
  if (notes.length) {
    meta.notes = deepClone(notes);
  } else {
    delete meta.notes;
  }
}

function getDraftRecordIdentity(draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return {
      primary_field_id: "",
      secondary_field_id: "",
      searchable_field_ids: [],
    };
  }
  const meta = ensureBlockSchemaMeta(draft);
  if (!meta.record_identity || typeof meta.record_identity !== "object") {
    meta.record_identity = {};
  }
  const identity = meta.record_identity;
  identity.primary_field_id = compactText(identity.primary_field_id);
  identity.secondary_field_id = compactText(identity.secondary_field_id);
  identity.searchable_field_ids = normalizeArray(identity.searchable_field_ids)
    .map((fieldId) => compactText(fieldId))
    .filter(Boolean)
    .filter((fieldId, index, all) => all.indexOf(fieldId) === index);
  return identity;
}

function setDraftRecordIdentityValue(key, value, draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return;
  }
  const identity = getDraftRecordIdentity(draft);
  if (key === "searchable_field_ids") {
    identity.searchable_field_ids = normalizeArray(value)
      .map((fieldId) => compactText(fieldId))
      .filter(Boolean)
      .filter((fieldId, index, all) => all.indexOf(fieldId) === index);
  } else {
    identity[key] = compactText(value);
  }
  if (!identity.primary_field_id && !identity.secondary_field_id && !identity.searchable_field_ids.length) {
    const meta = ensureBlockSchemaMeta(draft);
    delete meta.record_identity;
  }
}

function normalizeSignatoryOption(rawOption, index, slotId) {
  const option = rawOption && typeof rawOption === "object" ? rawOption : { name: rawOption };
  const name = compactText(option.name || option.label || option.value);
  if (!name) {
    return null;
  }
  const key = slugify(option.key || option.id || name);
  return {
    id: compactText(option.id) || `${slotId}.${key}`,
    key,
    name,
    title: compactText(option.title),
    license: compactText(option.license || option.license_no || option.license_number),
    order: parsePositiveInt(option.order, index),
  };
}

function makeDefaultSignatoryOptions(slotId, options) {
  return normalizeArray(options)
    .map((option, index) => normalizeSignatoryOption(option, index + 1, slotId))
    .filter(Boolean);
}

function defaultSignatorySlots() {
  const medtech1Options = makeDefaultSignatoryOptions("medical_technologist_1", DEFAULT_MEDTECH_SIGNATORY_OPTIONS);
  const medtech2Options = makeDefaultSignatoryOptions("medical_technologist_2", DEFAULT_MEDTECH_SIGNATORY_OPTIONS);
  const pathologistOptions = makeDefaultSignatoryOptions("pathologist", DEFAULT_PATHOLOGIST_SIGNATORY_OPTIONS);
  return [
    {
      id: "medical_technologist_1",
      label: "Medical Technologist",
      input_type: "person_dropdown",
      required: true,
      show_on_print: true,
      show_license: true,
      signature_line: true,
      default_option_id: "",
      options: medtech1Options,
    },
    {
      id: "medical_technologist_2",
      label: "Medical Technologist",
      input_type: "person_dropdown",
      required: false,
      show_on_print: true,
      show_license: true,
      signature_line: true,
      default_option_id: "",
      options: medtech2Options,
    },
    {
      id: "pathologist",
      label: "Pathologist",
      input_type: "fixed",
      required: false,
      show_on_print: true,
      show_license: true,
      signature_line: true,
      default_option_id: pathologistOptions[0]?.id || "",
      options: pathologistOptions,
    },
  ];
}

function normalizeSignatorySlot(rawSlot, index) {
  const slot = rawSlot && typeof rawSlot === "object" ? rawSlot : {};
  const label = compactText(slot.label) || `Signatory ${index}`;
  const slotId = slugify(slot.id || slot.key || label || `signatory_${index}`);
  const requestedInputType = compactText(slot.input_type).toLowerCase();
  const inputType = SIGNATORY_INPUT_TYPES.some((type) => type.id === requestedInputType)
    ? requestedInputType
    : "person_dropdown";
  const options = makeDefaultSignatoryOptions(slotId, slot.options);
  let defaultOptionId = compactText(slot.default_option_id);
  if (defaultOptionId && !options.some((option) => option.id === defaultOptionId)) {
    defaultOptionId = "";
  }
  if (inputType === "fixed" && !defaultOptionId && options.length) {
    defaultOptionId = options[0].id;
  }
  return {
    id: slotId,
    label,
    input_type: inputType,
    required: normalizePrintBoolean(slot.required, false),
    show_on_print: normalizePrintBoolean(slot.show_on_print, true),
    show_license: normalizePrintBoolean(slot.show_license, true),
    signature_line: normalizePrintBoolean(slot.signature_line, true),
    default_option_id: defaultOptionId,
    manual_name: compactText(slot.manual_name),
    manual_title: compactText(slot.manual_title),
    manual_license: compactText(slot.manual_license),
    stamp_image_url: compactText(slot.stamp_image_url),
    stamp_image_filename: compactText(slot.stamp_image_filename),
    stamp_image_mime_type: compactText(slot.stamp_image_mime_type),
    options,
  };
}

function getDraftSignatories(draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return [];
  }
  const meta = ensureBlockSchemaMeta(draft);
  if (!Array.isArray(meta.signatories)) {
    meta.signatories = defaultSignatorySlots();
  }
  meta.signatories = meta.signatories
    .map((slot, index) => normalizeSignatorySlot(slot, index + 1))
    .filter(Boolean);
  return meta.signatories;
}

function getDraftSignatory(slotId) {
  const targetId = compactText(slotId);
  return getDraftSignatories().find((slot) => slot.id === targetId) || null;
}

function makeBlankSignatorySlot() {
  const slotId = `signatory_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  return normalizeSignatorySlot(
    {
      id: slotId,
      label: "Signatory",
      input_type: "person_dropdown",
      required: false,
      show_on_print: true,
      show_license: true,
      signature_line: true,
      default_option_id: "",
      options: [],
    },
    getDraftSignatories().length + 1
  );
}

function signatoryOptionsToText(slot) {
  return normalizeArray(slot.options)
    .map((option) => [compactText(option.name), compactText(option.license)].filter(Boolean).join(" | "))
    .filter(Boolean)
    .join("\n");
}

function parseSignatoryOptionsText(value, slotId) {
  return splitLines(value)
    .map((line, index) => {
      const parts = line.split("|").map((part) => compactText(part));
      return normalizeSignatoryOption(
        {
          name: parts[0],
          license: parts.slice(1).join(" | "),
        },
        index + 1,
        slotId
      );
    })
    .filter(Boolean);
}

function addDraftSignatorySlot() {
  const slots = getDraftSignatories();
  slots.push(makeBlankSignatorySlot());
}

function removeDraftSignatorySlot(slotId) {
  const meta = ensureBlockSchemaMeta(state.draft);
  const targetId = compactText(slotId);
  meta.signatories = getDraftSignatories().filter((slot) => slot.id !== targetId);
}

function moveDraftSignatorySlot(slotId, direction) {
  const slots = getDraftSignatories();
  const index = slots.findIndex((slot) => slot.id === slotId);
  if (index === -1) {
    return;
  }
  const nextIndex = direction === "up" ? index - 1 : index + 1;
  if (nextIndex < 0 || nextIndex >= slots.length) {
    return;
  }
  const [slot] = slots.splice(index, 1);
  slots.splice(nextIndex, 0, slot);
}

function updateDraftSignatorySlot(slotId, key, value) {
  const slot = getDraftSignatory(slotId);
  if (!slot) {
    return;
  }
  if (key === "label") {
    slot.label = compactText(value) || "Signatory";
    return;
  }
  if (key === "input_type") {
    slot.input_type = SIGNATORY_INPUT_TYPES.some((type) => type.id === value) ? value : "person_dropdown";
    if (slot.input_type === "fixed" && !slot.default_option_id && slot.options.length) {
      slot.default_option_id = slot.options[0].id;
    }
    return;
  }
  if (key === "default_option_id") {
    slot.default_option_id = compactText(value);
    return;
  }
  if (key === "manual_name" || key === "manual_license" || key === "manual_title") {
    slot[key] = compactText(value);
  }
  if (key === "stamp_image_url" || key === "stamp_image_filename" || key === "stamp_image_mime_type") {
    slot[key] = compactText(value);
  }
}

function updateDraftSignatoryOptions(slotId, rawText) {
  const slot = getDraftSignatory(slotId);
  if (!slot) {
    return;
  }
  slot.options = parseSignatoryOptionsText(rawText, slot.id);
  if (slot.default_option_id && !slot.options.some((option) => option.id === slot.default_option_id)) {
    slot.default_option_id = "";
  }
  if (slot.input_type === "fixed" && !slot.default_option_id && slot.options.length) {
    slot.default_option_id = slot.options[0].id;
  }
}

async function uploadSignatoryStamp(inputEl) {
  const slotId = compactText(inputEl.dataset.id);
  const file = inputEl.files?.[0];
  if (!slotId || !file) {
    return;
  }
  const slot = getDraftSignatory(slotId);
  if (!slot) {
    inputEl.value = "";
    return;
  }

  const formData = new FormData();
  formData.append("stamp_file", file);
  try {
    setStatus("Uploading stamp image...");
    const response = await fetch("/api/forms/signatory-stamp", {
      method: "POST",
      body: formData,
    });
    const body = await response.json().catch(async () => ({ detail: await response.text() }));
    if (!response.ok) {
      throw new Error(body.detail || "Stamp upload failed.");
    }
    slot.stamp_image_url = compactText(body.url);
    slot.stamp_image_filename = compactText(body.original_filename) || file.name;
    slot.stamp_image_mime_type = compactText(body.mime_type) || file.type;
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    setStatus("Stamp image uploaded.");
  } catch (error) {
    console.error(error);
    setStatus(`Stamp upload failed: ${error.message}`, true);
  } finally {
    inputEl.value = "";
  }
}

function setDraftSignatoryToggle(slotId, key, checked) {
  const slot = getDraftSignatory(slotId);
  if (!slot || !["required", "show_on_print", "show_license", "signature_line"].includes(key)) {
    return;
  }
  slot[key] = Boolean(checked);
}

function normalizePrintAccentColor(value) {
  const text = compactText(value);
  return /^#[0-9a-fA-F]{6}$/.test(text) ? text.toLowerCase() : DEFAULT_PRINT_ACCENT_COLOR;
}

function printAccentInkColor(value) {
  const color = normalizePrintAccentColor(value).replace("#", "");
  const red = parseInt(color.slice(0, 2), 16);
  const green = parseInt(color.slice(2, 4), 16);
  const blue = parseInt(color.slice(4, 6), 16);
  const linear = (channel) => {
    const normalized = channel / 255;
    return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  const luminance = 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
  const darkContrast = (luminance + 0.05) / 0.05;
  const lightContrast = 1.05 / (luminance + 0.05);
  return darkContrast >= lightContrast ? "#171512" : "#ffffff";
}

function normalizePrintDensity(value) {
  const text = compactText(value).toLowerCase();
  return text === "comfortable" ? "comfortable" : "compact";
}

function normalizePrintImageSize(value) {
  const text = compactText(value).toLowerCase();
  return ["small", "medium", "large"].includes(text) ? text : "medium";
}

function normalizePrintTableDensity(value) {
  const text = compactText(value).toLowerCase();
  return text === "comfortable" ? "comfortable" : "compact";
}

function normalizePrintResultLayout(value) {
  const text = compactText(value).toLowerCase();
  return text === "rows" ? "rows" : "compact_grid";
}

function normalizePrintFontFamily(value) {
  const text = compactText(value).toLowerCase().replace(/[-\s]+/g, "_");
  return PRINT_FONT_FAMILIES.some((option) => option.id === text) ? text : "arial_narrow";
}

function normalizePrintSignatureSource(value, fallback = "blank") {
  const text = compactText(value).toLowerCase();
  return PRINT_SIGNATURE_SOURCES.some((option) => option.id === text) ? text : fallback;
}

function normalizePrintBoolean(value, fallback = true) {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  if (typeof value === "string") {
    return !["0", "false", "no", "off"].includes(value.trim().toLowerCase());
  }
  return Boolean(value);
}

function printSummarySourceLabel(source) {
  return PRINT_SUMMARY_SOURCES.find((item) => item.id === source)?.label || "Field";
}

function defaultPrintSummaryLabel(source, fieldId = "") {
  if (source === "primary_identity") {
    return "Record";
  }
  if (source === "secondary_identity") {
    return "Detail";
  }
  if (source === "record_key") {
    return "Record key";
  }
  if (source === "issued_at") {
    return "Issued";
  }
  if (source === "form_version") {
    return "Form version";
  }
  const field = collectIdentityFieldOptions().find((item) => item.id === fieldId);
  return field?.label || "Field";
}

function makePrintSummaryItem(source = "field") {
  return {
    id: `summary_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    label: defaultPrintSummaryLabel(source),
    source,
    field_id: "",
  };
}

function normalizePrintSummaryItem(item, index) {
  const rawItem = item && typeof item === "object" ? item : {};
  const source = PRINT_SUMMARY_SOURCES.some((option) => option.id === rawItem.source)
    ? rawItem.source
    : "field";
  const fieldId = compactText(rawItem.field_id);
  return {
    id: compactText(rawItem.id) || `summary_${index + 1}`,
    label: compactText(rawItem.label) || defaultPrintSummaryLabel(source, fieldId),
    source,
    field_id: source === "field" ? fieldId : "",
  };
}

function normalizePrintSummaryItems(items) {
  const normalized = normalizeArray(items).map(normalizePrintSummaryItem);
  return normalized.length ? normalized : deepClone(DEFAULT_PRINT_SUMMARY_ITEMS);
}

function getDraftPrintConfig(draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return {
      accent_color: DEFAULT_PRINT_ACCENT_COLOR,
      density: "compact",
      font_family: "arial_narrow",
      show_logo: true,
      show_clinic_info: true,
      show_status: true,
      show_summary: false,
      show_signatures: true,
      hide_empty_fields: false,
      show_section_titles: true,
      show_group_titles: true,
      image_size: "medium",
      table_density: "compact",
      result_layout: "compact_grid",
      signature_left_label: "Medical Technologist",
      signature_left_source: "prepared_by",
      signature_left_name: "",
      signature_left_field_id: "",
      signature_right_label: "Pathologist",
      signature_right_source: "blank",
      signature_right_name: "",
      signature_right_field_id: "",
      summary_items: deepClone(DEFAULT_PRINT_SUMMARY_ITEMS),
    };
  }
  const meta = ensureBlockSchemaMeta(draft);
  if (!meta.print_config || typeof meta.print_config !== "object") {
    meta.print_config = {};
  }
  const config = meta.print_config;
  config.accent_color = normalizePrintAccentColor(config.accent_color);
  config.density = normalizePrintDensity(config.density);
  config.font_family = normalizePrintFontFamily(config.font_family);
  config.show_logo = normalizePrintBoolean(config.show_logo, true);
  config.show_clinic_info = normalizePrintBoolean(config.show_clinic_info, true);
  config.show_status = normalizePrintBoolean(config.show_status, true);
  config.show_summary = normalizePrintBoolean(config.show_summary, false);
  config.show_signatures = normalizePrintBoolean(config.show_signatures, true);
  config.hide_empty_fields = normalizePrintBoolean(config.hide_empty_fields, false);
  config.show_section_titles = normalizePrintBoolean(config.show_section_titles, true);
  config.show_group_titles = normalizePrintBoolean(config.show_group_titles, true);
  config.image_size = normalizePrintImageSize(config.image_size);
  config.table_density = normalizePrintTableDensity(config.table_density);
  config.result_layout = normalizePrintResultLayout(config.result_layout);
  config.signature_left_label = compactText(config.signature_left_label) || "Medical Technologist";
  config.signature_left_source = normalizePrintSignatureSource(config.signature_left_source, "prepared_by");
  config.signature_left_name = compactText(config.signature_left_name);
  config.signature_left_field_id = compactText(config.signature_left_field_id);
  config.signature_right_label = compactText(config.signature_right_label) || "Pathologist";
  config.signature_right_source = normalizePrintSignatureSource(config.signature_right_source, "blank");
  config.signature_right_name = compactText(config.signature_right_name);
  config.signature_right_field_id = compactText(config.signature_right_field_id);
  config.summary_items = normalizePrintSummaryItems(config.summary_items);
  return config;
}

function setDraftPrintConfigValue(key, value, draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return;
  }
  const config = getDraftPrintConfig(draft);
  if (key === "accent_color") {
    config.accent_color = normalizePrintAccentColor(value);
  } else if (key === "density") {
    config.density = normalizePrintDensity(value);
  } else if (key === "font_family") {
    config.font_family = normalizePrintFontFamily(value);
  } else if (key === "image_size") {
    config.image_size = normalizePrintImageSize(value);
  } else if (key === "table_density") {
    config.table_density = normalizePrintTableDensity(value);
  } else if (key === "result_layout") {
    config.result_layout = normalizePrintResultLayout(value);
  } else if (key === "signature_left_source") {
    config.signature_left_source = normalizePrintSignatureSource(value, "prepared_by");
  } else if (key === "signature_right_source") {
    config.signature_right_source = normalizePrintSignatureSource(value, "blank");
  } else if ([
    "signature_left_label",
    "signature_left_name",
    "signature_left_field_id",
    "signature_right_label",
    "signature_right_name",
    "signature_right_field_id",
  ].includes(key)) {
    config[key] = compactText(value);
  } else if ([
    "show_logo",
    "show_clinic_info",
    "show_status",
    "show_summary",
    "show_signatures",
    "hide_empty_fields",
    "show_section_titles",
    "show_group_titles",
  ].includes(key)) {
    config[key] = Boolean(value);
  }
}

function getDraftPrintSummaryItem(itemId) {
  const config = getDraftPrintConfig(state.draft);
  return config.summary_items.find((item) => item.id === itemId);
}

function updateDraftPrintSummaryItem(itemId, key, value) {
  const item = getDraftPrintSummaryItem(itemId);
  if (!item) {
    return;
  }
  if (key === "source") {
    const previousDefault = defaultPrintSummaryLabel(item.source, item.field_id);
    const nextSource = PRINT_SUMMARY_SOURCES.some((option) => option.id === value) ? value : "field";
    item.source = nextSource;
    if (nextSource !== "field") {
      item.field_id = "";
    }
    if (!compactText(item.label) || item.label === previousDefault) {
      item.label = defaultPrintSummaryLabel(nextSource, item.field_id);
    }
    return;
  }
  if (key === "field_id") {
    item.field_id = compactText(value);
    if (!compactText(item.label) || item.label === "Field") {
      item.label = defaultPrintSummaryLabel(item.source, item.field_id);
    }
    return;
  }
  if (key === "label") {
    item.label = compactText(value);
  }
}

function addDraftPrintSummaryItem() {
  const config = getDraftPrintConfig(state.draft);
  config.summary_items.push(makePrintSummaryItem("field"));
}

function removeDraftPrintSummaryItem(itemId) {
  const config = getDraftPrintConfig(state.draft);
  config.summary_items = config.summary_items.filter((item) => item.id !== itemId);
  if (!config.summary_items.length) {
    config.summary_items = deepClone(DEFAULT_PRINT_SUMMARY_ITEMS);
  }
}

function moveDraftPrintSummaryItem(itemId, direction) {
  const config = getDraftPrintConfig(state.draft);
  const index = config.summary_items.findIndex((item) => item.id === itemId);
  if (index === -1) {
    return;
  }
  const nextIndex = direction === "up" ? index - 1 : index + 1;
  if (nextIndex < 0 || nextIndex >= config.summary_items.length) {
    return;
  }
  const [item] = config.summary_items.splice(index, 1);
  config.summary_items.splice(nextIndex, 0, item);
}

function currentPrintPreviewSignature() {
  if (!state.draft) {
    return "";
  }
  return JSON.stringify({
    name: state.draft.name || "",
    location_name: displayLocationName(state.draft),
    form_schema: state.draft.block_schema || {},
  });
}

function printPreviewIsCurrent() {
  return Boolean(
    state.draft &&
    state.ui.printPreview.html &&
    state.ui.printPreview.signature &&
    state.ui.printPreview.signature === currentPrintPreviewSignature()
  );
}

function printPreviewStatusCopy() {
  const preview = state.ui.printPreview;
  if (preview.status === "loading") {
    return "Generating preview...";
  }
  if (preview.status === "error") {
    return "Preview failed";
  }
  if (!preview.html) {
    return "No preview generated yet";
  }
  if (!printPreviewIsCurrent()) {
    return "Preview needs update";
  }
  return "Preview is current";
}

function resetPrintPreview() {
  state.ui.printPreview = {
    status: "idle",
    html: "",
    signature: "",
    error: "",
  };
}

function syncPrintPreviewFrame() {
  const frame = document.getElementById("printPreviewFrame");
  if (!(frame instanceof HTMLIFrameElement)) {
    return;
  }
  const html = state.ui.printPreview.html || "";
  if (frame.srcdoc !== html) {
    frame.srcdoc = html;
  }
}

async function refreshPrintPreview() {
  if (!state.draft) {
    return;
  }

  syncDraftKeys();
  const signature = currentPrintPreviewSignature();
  state.ui.printPreview.status = "loading";
  state.ui.printPreview.error = "";
  renderAll();

  const payload = {
    name: state.draft.name || "Untitled Form",
    location_name: displayLocationName(state.draft),
    form_schema: state.draft.block_schema,
  };

  try {
    const response = await fetch("/api/forms/print-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const html = await response.text();
    if (!response.ok) {
      throw new Error(html || `Preview failed: ${response.status}`);
    }
    state.ui.printPreview = {
      status: "loaded",
      html,
      signature,
      error: "",
    };
    setStatus("Print preview updated");
  } catch (error) {
    console.error(error);
    state.ui.printPreview.status = "error";
    state.ui.printPreview.error = error.message || "Unable to build print preview.";
    setStatus(`Print preview failed: ${state.ui.printPreview.error}`, true);
  } finally {
    renderAll();
  }
}

function ensureDraftBlockState(draft) {
  if (!draft || typeof draft !== "object") {
    return draft;
  }

  const existingBlockSchema = draft.block_schema && typeof draft.block_schema === "object"
    ? deepClone(draft.block_schema)
    : null;

  if (existingBlockSchema) {
    draft.block_schema = existingBlockSchema;
  } else {
    draft.block_schema = {
      schema_version: 1,
      source_kind: ACTIVE_BLOCK_SCHEMA_SOURCE,
      meta: {},
      blocks: [],
    };
  }

  draft.name = compactText(draft.name) || "Untitled Form";
  syncRootMetaToBlockSchema(draft);
  syncDraftLocationState(draft);
  normalizeArray(draft.block_schema.blocks).forEach(normalizeLiveBlockNode);
  delete draft.schema;
  delete draft.form_schema;
  return draft;
}

function ensureBlockSchemaMeta(draft) {
  if (!draft || typeof draft !== "object") {
    return null;
  }

  if (!draft.block_schema || typeof draft.block_schema !== "object") {
    draft.block_schema = {
      schema_version: 1,
      source_kind: ACTIVE_BLOCK_SCHEMA_SOURCE,
      meta: {},
      blocks: [],
    };
  }

  if (!draft.block_schema.meta || typeof draft.block_schema.meta !== "object") {
    draft.block_schema.meta = {};
  }

  draft.block_schema.blocks = normalizeArray(draft.block_schema.blocks);
  return draft.block_schema.meta;
}

function syncRootMetaToBlockSchema(draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return;
  }

  const meta = ensureBlockSchemaMeta(draft);
  if (!meta) {
    return;
  }

  draft.block_schema.source_kind = ACTIVE_BLOCK_SCHEMA_SOURCE;
  delete meta.legacy_form_id;
  meta.form_key = compactText(meta.form_key) || slugify(draft.name || "untitled_form") || "untitled_form";
  meta.form_order = parsePositiveInt(meta.form_order, 1);
  delete meta.legacy_form_key;
  delete meta.legacy_order;

  const notes = normalizeArray(meta.notes);
  if (notes.length) {
    meta.notes = deepClone(notes);
  } else {
    delete meta.notes;
  }

  if (!(meta.source && typeof meta.source === "object")) {
    delete meta.source;
  }

  const identity = getDraftRecordIdentity(draft);
  if (!identity.primary_field_id && !identity.secondary_field_id && !identity.searchable_field_ids.length) {
    delete meta.record_identity;
  }

  getDraftPrintConfig(draft);
  getDraftSignatories(draft);
}

function syncDraftBlockState() {
  if (!state.draft) {
    return;
  }
  syncRootMetaToBlockSchema(state.draft);
}

function isBlockNode(node) {
  const kind = blockKind(node);
  return kind === "field" || kind === "field_group" || kind === "section";
}

function isStoredBlockNode(node) {
  const kind = blockKind(node);
  return kind === "field" || kind === "field_group" || kind === "section" || kind === "note" || kind === "divider" || kind === "table";
}

function isUtilityBlockNode(node) {
  const kind = blockKind(node);
  return kind === "note" || kind === "divider" || kind === "table";
}

function getNodeProps(node) {
  if (!isStoredBlockNode(node)) {
    return {};
  }
  if (!node.props || typeof node.props !== "object") {
    node.props = {};
  }
  return node.props;
}

function getNodeChildren(node) {
  if (!isStoredBlockNode(node)) {
    return [];
  }
  node.children = normalizeArray(node.children);
  return node.children;
}

function getNodeKey(node) {
  return isStoredBlockNode(node) ? String(getNodeProps(node).key || "").trim() : "";
}

function getNodeNotes(node) {
  return isStoredBlockNode(node) ? normalizeArray(getNodeProps(node).notes) : [];
}

function getInputControl(field) {
  return isBlockNode(field)
    ? String(getNodeProps(field).control || "input").trim() || "input"
    : "input";
}

function getInputDataType(field) {
  return isBlockNode(field)
    ? String(getNodeProps(field).data_type || "text").trim() || "text"
    : "text";
}

function getInputUnitHint(field) {
  return isBlockNode(field) ? String(getNodeProps(field).unit_hint || "").trim() : "";
}

function getInputReferenceText(field) {
  return isBlockNode(field)
    ? String(getNodeProps(field).reference_text || getNodeProps(field).normal_value || "").trim()
    : "";
}

function getInputNormalMin(field) {
  return isBlockNode(field) ? String(getNodeProps(field).normal_min || "").trim() : "";
}

function getInputNormalMax(field) {
  return isBlockNode(field) ? String(getNodeProps(field).normal_max || "").trim() : "";
}

function inputNormalRangeLabel(field) {
  const min = compactText(getInputNormalMin(field));
  const max = compactText(getInputNormalMax(field));
  if (min && max) {
    return `Normal ${min} - ${max}`;
  }
  if (min) {
    return `Normal from ${min}`;
  }
  if (max) {
    return `Normal to ${max}`;
  }
  return "";
}

function normalizeInputOptions(field, { allowLegacyLabel = false } = {}) {
  if (!isBlockNode(field)) {
    return [];
  }
  const props = getNodeProps(field);
  props.options = normalizeArray(props.options).map((option, index) => {
    if (option && typeof option === "object") {
      const normalized = { ...option };
      const normalizedName = compactText(
        normalized.name || (allowLegacyLabel ? normalized.label : "")
      );
      normalized.name = normalizedName;
      delete normalized.label;
      normalized.key = compactText(normalized.key) || slugify(normalizedName || `option_${index + 1}`) || `option_${index + 1}`;
      normalized.order = parsePositiveInt(normalized.order, index + 1);
      normalized.is_normal = Boolean(normalized.is_normal);
      return normalized;
    }
    const normalizedName = compactText(option);
    return {
      name: normalizedName,
      key: slugify(normalizedName || `option_${index + 1}`) || `option_${index + 1}`,
      order: index + 1,
      is_normal: false,
    };
  });
  return props.options;
}

function normalizeLiveBlockNode(node) {
  if (!isStoredBlockNode(node)) {
    return;
  }

  const props = getNodeProps(node);
  delete props.field_type;

  const referenceText = compactText(props.reference_text || props.normal_value);
  if (referenceText) {
    props.reference_text = referenceText;
  } else {
    delete props.reference_text;
  }
  delete props.normal_value;

  const normalMin = compactText(props.normal_min);
  if (normalMin) {
    props.normal_min = normalMin;
  } else {
    delete props.normal_min;
  }

  const normalMax = compactText(props.normal_max);
  if (normalMax) {
    props.normal_max = normalMax;
  } else {
    delete props.normal_max;
  }

  if (blockKind(node) === "field") {
    if (props.required) {
      props.required = true;
    } else {
      delete props.required;
    }
    normalizeInputOptions(node, { allowLegacyLabel: true });
  }

  getNodeChildren(node).forEach(normalizeLiveBlockNode);
}

function getInputOptions(field) {
  return normalizeInputOptions(field);
}

function topLevelBlocks() {
  return normalizeArray(state.draft?.block_schema?.blocks);
}

function topLevelSectionEntries() {
  return topLevelBlocks()
    .map((node, index) => ({ node, path: ["block_schema", "blocks", index] }))
    .filter((entry) => entry.node?.kind === "section");
}

function collectIdentityFieldOptions(blocks = topLevelBlocks(), parentNames = []) {
  const options = [];
  normalizeArray(blocks).forEach((node) => {
    if (!isStoredBlockNode(node)) {
      return;
    }
    const kind = blockKind(node);
    const nodeName = compactText(node.name);
    if (kind === "section" || kind === "field_group") {
      options.push(...collectIdentityFieldOptions(
        getNodeChildren(node),
        nodeName ? [...parentNames, nodeName] : parentNames
      ));
      return;
    }
    if (kind !== "field") {
      return;
    }
    const fieldName = nodeName || "Untitled field";
    options.push({
      id: compactText(node.id),
      label: fieldName,
      pathLabel: [...parentNames, fieldName].filter(Boolean).join(" / ") || fieldName,
    });
  });
  return options.filter((option) => option.id);
}

function topLevelContentEntries() {
  const entries = topLevelBlockEntries();
  if (state.ui.advancedMode) {
    return entries;
  }
  return entries.filter((entry) => {
    const kind = blockKind(entry.node);
    return kind === "field" || kind === "field_group" || kind === "section";
  });
}

function isContainerBlockNode(node) {
  const kind = blockKind(node);
  return kind === "section" || kind === "field_group";
}

function topLevelBlockEntries() {
  return topLevelBlocks().map((node, index) => ({
    node,
    path: ["block_schema", "blocks", index],
  }));
}

function setContentSelection(path) {
  const node = getNodeByPath(path);
  if (!node) {
    return;
  }

  if (isContainerBlockNode(node)) {
    ensureAncestorContainersOpen(path);
    setContainerOpen(path, true);
    state.ui.activeItemPath = null;
  } else if (blockKind(node) === "field") {
    ensureAncestorContainersOpen(path);
    setFieldDetailsOpen(path, true);
    state.ui.activeItemPath = pathKey(path);
  } else {
    ensureAncestorContainersOpen(path);
    state.ui.activeItemPath = pathKey(path);
  }
  state.ui.activeOptionToken = null;
}

function collectContainerPathKeysFromNode(node, basePath) {
  const keys = [];
  if (isContainerBlockNode(node)) {
    keys.push(pathKey(basePath));
  }

  getNodeChildren(node).forEach((child, index) => {
    keys.push(...collectContainerPathKeysFromNode(child, [...basePath, "children", index]));
  });

  return keys;
}

function collectContainerPathKeys(container, basePath = []) {
  const keys = [];
  normalizeArray(container?.blocks).forEach((block, index) => {
    keys.push(...collectContainerPathKeysFromNode(block, [...basePath, "blocks", index]));
  });
  getNodeChildren(container).forEach((child, index) => {
    keys.push(...collectContainerPathKeysFromNode(child, [...basePath, "children", index]));
  });
  return keys;
}

function collectFieldPathKeysFromNode(node, basePath) {
  const keys = [];
  if (blockKind(node) === "field") {
    keys.push(pathKey(basePath));
  }

  getNodeChildren(node).forEach((child, index) => {
    keys.push(...collectFieldPathKeysFromNode(child, [...basePath, "children", index]));
  });

  return keys;
}

function collectFieldPathKeys(container, basePath = []) {
  const keys = [];
  normalizeArray(container?.blocks).forEach((block, index) => {
    keys.push(...collectFieldPathKeysFromNode(block, [...basePath, "blocks", index]));
  });
  getNodeChildren(container).forEach((child, index) => {
    keys.push(...collectFieldPathKeysFromNode(child, [...basePath, "children", index]));
  });
  return keys;
}

function collectItemPathKeysFromNode(node, basePath) {
  const keys = [];
  const kind = String(node?.kind || "").trim();

  if (kind === "field" || kind === "field_group" || kind === "note" || kind === "divider" || kind === "table") {
    keys.push(pathKey(basePath));
  }

  getNodeChildren(node).forEach((child, index) => {
    keys.push(...collectItemPathKeysFromNode(child, [...basePath, "children", index]));
  });

  return keys;
}

function insertTopLevelItem(kind) {
  const blocks = topLevelBlocks();
  const nextNode = makeBlankBlock(kind);
  const firstSectionIndex = blocks.findIndex((block) => String(block?.kind || "").trim() === "section");

  if (firstSectionIndex === -1) {
    blocks.push(nextNode);
    return blocks.length - 1;
  }

  blocks.splice(firstSectionIndex, 0, nextNode);
  return firstSectionIndex;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function encodePath(path) {
  return encodeURIComponent(JSON.stringify(path));
}

function decodePath(serialized) {
  return JSON.parse(decodeURIComponent(serialized));
}

function pathKey(path) {
  return JSON.stringify(path);
}

function parsePathKey(serialized) {
  return JSON.parse(serialized);
}

function pathStartsWith(path, prefix) {
  return prefix.every((segment, index) => path[index] === segment);
}

function quickSwitchForms() {
  return normalizeArray(state.bootstrap?.form_choices).filter((form) => compactText(form?.slug));
}

function quickSwitchLocationLabel(form) {
  const direct = compactText(form?.location_path_label);
  if (direct) {
    return direct;
  }
  const formPathLabel = compactText(form?.form_path_label);
  const name = compactText(form?.name);
  if (!formPathLabel || formPathLabel === name) {
    return "Top level";
  }
  const suffix = ` / ${name}`;
  return formPathLabel.endsWith(suffix) ? formPathLabel.slice(0, -suffix.length) : formPathLabel;
}

function currentVersionLabel() {
  return state.draft?.current_version_number ? `Version ${state.draft.current_version_number}` : "New draft";
}

function topLevelPreviewSegments() {
  const segments = [];
  let looseItems = [];
  let looseGroupCount = 0;

  const flushLooseItems = () => {
    if (!looseItems.length) {
      return;
    }
    const localIndex = ++looseGroupCount;
    const baseLabel = localIndex === 1
      ? "Details"
      : localIndex === 2
        ? "More details"
        : `More details ${localIndex - 1}`;
    const baseId = localIndex === 1
      ? "details"
      : localIndex === 2
        ? "more_details"
        : `more_details_${localIndex - 1}`;
    segments.push({
      id: `preview_section_${baseId}`,
      label: baseLabel,
      title: baseLabel,
      items: looseItems,
    });
    looseItems = [];
  };

  topLevelBlockEntries().forEach((entry, index) => {
    if (entry.node?.kind === "section") {
      flushLooseItems();
      const sectionName = compactText(entry.node?.name);
      segments.push({
        id: previewSectionId(sectionName || "Container", index),
        label: sectionName || "Container",
        title: sectionName || "Untitled Container",
        items: getNodeChildren(entry.node),
      });
      return;
    }
    looseItems.push(entry.node);
  });

  flushLooseItems();
  return segments;
}

function normalizeTopLevelLocationValue(value) {
  const normalized = compactText(value);
  return normalized === "Unassigned" ? "Top level" : normalized;
}

function isTopLevelLocationName(name) {
  const value = normalizeTopLevelLocationValue(name);
  return !value || value === "Top level";
}

function compactLocationName(draft = state.draft) {
  return normalizeTopLevelLocationValue(draft?.location_name);
}

function compactLocationPathLabel(draft = state.draft) {
  return normalizeTopLevelLocationValue(draft?.location_path_label);
}

function availableLocationOptions() {
  return normalizeArray(state.bootstrap?.container_options);
}

function findLocationOptionByNodeKey(nodeKey) {
  const key = compactText(nodeKey);
  if (!key) {
    return null;
  }
  return availableLocationOptions().find((option) => compactText(option.node_key) === key) || null;
}

function findLocationOptionByFolderPathLabel(folderPathLabel) {
  const label = compactText(folderPathLabel);
  if (!label) {
    return null;
  }
  return availableLocationOptions().find((option) => compactText(option.folder_path_label) === label) || null;
}

function isTopLevelDraftLocation(draft = state.draft) {
  if (!draft) {
    return true;
  }
  if (compactText(draft.library_parent_node_key)) {
    return false;
  }
  const locationName = compactLocationName(draft);
  return !locationName || locationName === "Top level";
}

function displayLocationName(draft = state.draft) {
  if (!draft) {
    return "Top level";
  }
  const explicitPath = compactLocationPathLabel(draft);
  if (explicitPath) {
    return explicitPath;
  }
  const matchedOption = findLocationOptionByNodeKey(draft.library_parent_node_key);
  if (matchedOption?.folder_path_label) {
    return matchedOption.folder_path_label;
  }
  return isTopLevelDraftLocation(draft) ? "Top level" : compactLocationName(draft) || "Top level";
}

function editableLocationValue(draft = state.draft) {
  if (!draft) {
    return "";
  }
  const explicitPath = compactLocationPathLabel(draft);
  if (explicitPath && explicitPath !== "Top level") {
    return explicitPath;
  }
  const matchedOption = findLocationOptionByNodeKey(draft.library_parent_node_key);
  if (matchedOption?.folder_path_label) {
    return matchedOption.folder_path_label;
  }
  return isTopLevelDraftLocation(draft) ? "" : compactLocationName(draft);
}

function syncDraftLocationState(draft = state.draft) {
  if (!draft || typeof draft !== "object") {
    return;
  }

  const explicitName = compactLocationName(draft);
  const explicitPath = compactLocationPathLabel(draft);
  const pendingFolderName = compactText(draft.library_new_container_name);
  const matchedOption = findLocationOptionByNodeKey(draft.library_parent_node_key);

  if (pendingFolderName) {
    const parentPath = compactText(matchedOption?.folder_path_label);
    const folderName = explicitName || pendingFolderName;
    draft.location_name = folderName || "Top level";
    draft.location_path_label = [parentPath, folderName].filter(Boolean).join(" / ") || folderName || "Top level";
    draft.location_node_key = null;
    draft.location_kind = folderName ? "folder" : "top_level";
    return;
  }

  if (matchedOption) {
    draft.location_name = compactText(matchedOption.name) || explicitName || "Top level";
    draft.location_path_label = compactText(matchedOption.folder_path_label) || explicitPath || draft.location_name;
    draft.location_node_key = compactText(matchedOption.node_key) || null;
    draft.location_kind = "folder";
    return;
  }

  const freeform = explicitPath || explicitName;
  if (!freeform || isTopLevelLocationName(freeform)) {
    draft.location_name = "Top level";
    draft.location_path_label = "Top level";
    draft.location_node_key = null;
    draft.location_kind = "top_level";
    return;
  }

  draft.location_name = compactText(freeform);
  draft.location_path_label = compactText(freeform);
  draft.location_node_key = null;
  draft.location_kind = "folder";
}

function availableLocationNames() {
  const names = new Set();
  availableLocationOptions().forEach((option) => {
    const label = compactText(option.folder_path_label);
    if (label) {
      names.add(label);
    }
  });
  const currentLocation = displayLocationName(state.draft);
  if (currentLocation && currentLocation !== "Top level") {
    names.add(currentLocation);
  }
  return [...names].filter(Boolean).sort((a, b) => a.localeCompare(b));
}

function renderLocationSuggestions() {
  const names = availableLocationNames();
  if (!names.length) {
    return "";
  }
  return `
    <datalist id="locationSuggestions">
      ${names.map((name) => `<option value="${escapeHtml(name)}"></option>`).join("")}
    </datalist>
  `;
}

function renderHelpPopover(label, text) {
  return `
    <details class="inline-help">
      <summary aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">?</summary>
      <div class="help-popover">${escapeHtml(text)}</div>
    </details>
  `;
}

function isDialogOpen() {
  return Boolean(confirmDialogEl && !confirmDialogEl.hidden);
}

function closeTransientDetails() {
  if (!document.body) {
    return;
  }

  document.querySelectorAll(".action-details[open], .manage-details[open], .inline-help[open]").forEach((item) => {
    item.open = false;
  });
}

function closeDecisionDialog(result = "cancel") {
  if (!confirmDialogEl || !dialogScrimEl) {
    return;
  }

  confirmDialogEl.hidden = true;
  confirmDialogEl.classList.add("hidden");
  dialogScrimEl.hidden = true;
  dialogScrimEl.classList.add("hidden");
  document.body.classList.remove("modal-open");

  const resolve = dialogResolver;
  const returnFocus = dialogReturnFocusEl;
  dialogResolver = null;
  dialogReturnFocusEl = null;

  if (returnFocus && typeof returnFocus.focus === "function") {
    queueMicrotask(() => returnFocus.focus());
  }

  if (resolve) {
    resolve(result);
  }
}

function openDecisionDialog({
  eyebrow = "Please confirm",
  title = "What do you want to do?",
  message = "",
  cancelLabel = "Cancel",
  altLabel = "",
  confirmLabel = "Continue",
  destructive = false,
}) {
  if (!confirmDialogEl || !dialogScrimEl) {
    return Promise.resolve("confirm");
  }

  if (dialogResolver) {
    closeDecisionDialog("cancel");
  }

  closeTransientDetails();
  dialogReturnFocusEl = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  confirmDialogEyebrowEl.textContent = eyebrow;
  confirmDialogTitleEl.textContent = title;
  confirmDialogMessageEl.textContent = message;
  confirmDialogCancelBtnEl.textContent = cancelLabel;
  confirmDialogConfirmBtnEl.textContent = confirmLabel;
  confirmDialogConfirmBtnEl.classList.toggle("warn-fill", destructive);

  const showAlt = Boolean(altLabel);
  confirmDialogAltBtnEl.hidden = !showAlt;
  confirmDialogAltBtnEl.classList.toggle("hidden", !showAlt);
  confirmDialogAltBtnEl.textContent = altLabel || "";

  confirmDialogEl.hidden = false;
  confirmDialogEl.classList.remove("hidden");
  dialogScrimEl.hidden = false;
  dialogScrimEl.classList.remove("hidden");
  document.body.classList.add("modal-open");

  return new Promise((resolve) => {
    dialogResolver = resolve;
    queueMicrotask(() => {
      const focusTarget = showAlt ? confirmDialogAltBtnEl : confirmDialogCancelBtnEl;
      if (focusTarget && typeof focusTarget.focus === "function") {
        focusTarget.focus();
      }
    });
  });
}

async function resolveDirtyBeforeContinue() {
  if (!state.dirty) {
    return true;
  }

  const decision = await openDecisionDialog({
    eyebrow: "Draft changed",
    title: "What should happen to this draft?",
    message: "You still have changes in this form.",
    cancelLabel: "Keep editing",
    altLabel: "Save and continue",
    confirmLabel: "Discard changes",
    destructive: true,
  });

  if (decision === "cancel") {
    return false;
  }

  if (decision === "alt") {
    try {
      await saveDraft();
    } catch (error) {
      console.error(error);
      setStatus(`Save failed: ${error.message}`, true);
      return false;
    }
  }

  return true;
}

function syncShellState() {
  const previewPane = String(state.ui.focusPane || defaultFocusPane());
  const inputPreviewAllowed = previewPane === "setup" || previewPane === "content";
  const previewVisible = state.ui.previewOpen && inputPreviewAllowed && Boolean(state.draft);
  if (libraryDrawerEl) {
    libraryDrawerEl.hidden = !state.ui.libraryOpen;
    if (state.ui.libraryOpen) {
      libraryDrawerEl.removeAttribute("inert");
    } else {
      libraryDrawerEl.setAttribute("inert", "");
    }
    libraryDrawerEl.classList.toggle("is-open", state.ui.libraryOpen);
    libraryDrawerEl.setAttribute("aria-hidden", String(!state.ui.libraryOpen));
  }

  if (previewPanelEl) {
    previewPanelEl.hidden = !previewVisible;
    previewPanelEl.classList.toggle("is-hidden", !previewVisible);
    previewPanelEl.setAttribute("aria-hidden", String(!previewVisible));
    if (previewVisible) {
      previewPanelEl.removeAttribute("inert");
    } else {
      previewPanelEl.setAttribute("inert", "");
    }

    if (previewPanelEl.id === "previewDrawer") {
      previewPanelEl.classList.toggle("is-open", previewVisible);
    }
  }

  workspaceShellEl?.classList.toggle("preview-open", previewVisible);
  drawerScrimEl.hidden = !state.ui.libraryOpen;
  drawerScrimEl.classList.toggle("hidden", !state.ui.libraryOpen);
  document.body.classList.toggle("drawer-open", state.ui.libraryOpen);
  if (openPreviewBtnEl) {
    openPreviewBtnEl.textContent = previewVisible ? "Hide" : "Preview";
  }
  renderPreviewCallout();
}

function syncAdvancedModeUi() {
  if (toggleAdvancedBtnEl) {
    const enabled = state.ui.advancedMode;
    toggleAdvancedBtnEl.textContent = "Advanced";
    toggleAdvancedBtnEl.setAttribute("aria-pressed", String(enabled));
    toggleAdvancedBtnEl.setAttribute("aria-label", `Advanced options ${enabled ? "on" : "off"}`);
    toggleAdvancedBtnEl.title = `Advanced options ${enabled ? "on" : "off"}`;
  }

  if (devPanelEl) {
    devPanelEl.hidden = !state.ui.advancedMode;
    if (!state.ui.advancedMode) {
      devPanelEl.open = false;
    }
  }
}

function closeDrawers() {
  state.ui.libraryOpen = false;
  syncShellState();
}

function openLibrary() {
  state.ui.libraryOpen = true;
  syncShellState();
}

function togglePreview() {
  const previewPane = String(state.ui.focusPane || defaultFocusPane());
  const shouldOpen = !state.ui.previewOpen || previewPane !== "content";
  if (shouldOpen) {
    state.ui.focusPane = "content";
    state.ui.previewOpen = true;
  } else {
    state.ui.previewOpen = false;
  }
  renderAll();
}

function renderShellSummary() {
  if (!state.draft) {
    currentFormNameEl.textContent = "Start with a form";
    currentFormMetaEl.textContent = "Choose one from the library or start new.";
    stageTitleEl.textContent = "Choose a form";
    stageDescriptionEl.textContent = "Edit one area at a time.";
    renderPreviewCallout();
    return;
  }

  const formName = state.draft.name || "Untitled Form";
  const locationName = displayLocationName(state.draft);
  const version = currentVersionLabel();

  currentFormNameEl.textContent = formName;
  currentFormMetaEl.textContent = `${locationName} | ${version}`;
  stageTitleEl.textContent = formName;
  stageDescriptionEl.textContent = state.ui.previewOpen
    ? "Edit one area at a time."
    : "Edit one area at a time. Show preview anytime.";
  renderPreviewCallout();
}

function renderPreviewCallout() {
  if (!previewCalloutTitleEl || !previewCalloutMetaEl || !openPreviewBtnEl) {
    return;
  }

  if (!state.draft) {
    previewCalloutTitleEl.textContent = "Live preview";
    previewCalloutMetaEl.textContent = "Choose a form to see it here.";
    openPreviewBtnEl.disabled = true;
    return;
  }

  openPreviewBtnEl.disabled = false;
  previewCalloutTitleEl.textContent = "Live preview";

  if (state.ui.previewOpen) {
    previewCalloutMetaEl.textContent = "Updates while you edit.";
    return;
  }

  previewCalloutMetaEl.textContent = "Show it for a quick check.";
}

function resetEditorPanels() {
  state.ui.setupOpen = !state.selectedFormSlug;
  state.ui.saveOpen = !state.selectedFormSlug;
  state.ui.openSectionPaths = [];
  state.ui.openFieldDetailPaths = [];
  state.ui.activeItemPath = null;
  state.ui.activeOptionToken = null;
  state.ui.focusPane = defaultFocusPane();
}

function collectItemPathKeys(container, basePath = []) {
  const paths = [];
  normalizeArray(container?.blocks).forEach((block, index) => {
    paths.push(...collectItemPathKeysFromNode(block, [...basePath, "blocks", index]));
  });
  getNodeChildren(container).forEach((child, index) => {
    paths.push(...collectItemPathKeysFromNode(child, [...basePath, "children", index]));
  });
  return paths;
}

function syncEditorPanels() {
  const validContainerPaths = new Set(collectContainerPathKeys(state.draft?.block_schema, ["block_schema"]));
  state.ui.openSectionPaths = normalizeArray(state.ui.openSectionPaths).filter((item) => validContainerPaths.has(item));

  const validItemPaths = new Set(collectItemPathKeys(state.draft?.block_schema, ["block_schema"]));
  if (state.ui.activeItemPath && !validItemPaths.has(state.ui.activeItemPath)) {
    state.ui.activeItemPath = null;
    state.ui.activeOptionToken = null;
  }

  const validFieldPaths = new Set(collectFieldPathKeys(state.draft?.block_schema, ["block_schema"]));
  state.ui.openFieldDetailPaths = normalizeArray(state.ui.openFieldDetailPaths).filter((item) => validFieldPaths.has(item));

  if (state.ui.activeOptionToken) {
    const parsed = parseOptionToken(state.ui.activeOptionToken);
    const field = parsed ? getNodeByPath(parsed.path) : null;
    const options = getInputOptions(field);
    if (!parsed || !options[parsed.index]) {
      state.ui.activeOptionToken = null;
    }
  }

  syncFocusPane();
}

function isContainerOpen(path) {
  return normalizeArray(state.ui.openSectionPaths).includes(pathKey(path));
}

function isSectionOpen(path) {
  return isContainerOpen(path);
}

function setContainerOpen(path, open) {
  const token = pathKey(path);
  const current = new Set(normalizeArray(state.ui.openSectionPaths));
  if (open) {
    current.add(token);
  } else {
    current.delete(token);
    if (state.ui.activeItemPath && pathStartsWith(parsePathKey(state.ui.activeItemPath), path)) {
      state.ui.activeItemPath = null;
      state.ui.activeOptionToken = null;
    }
  }
  state.ui.openSectionPaths = [...current];
}

function ensureAncestorContainersOpen(path) {
  const current = new Set(normalizeArray(state.ui.openSectionPaths));
  for (let length = 1; length <= path.length; length += 1) {
    const candidatePath = path.slice(0, length);
    if (isContainerBlockNode(getNodeByPath(candidatePath))) {
      current.add(pathKey(candidatePath));
    }
  }
  state.ui.openSectionPaths = [...current];
}

function toggleContainer(path) {
  setContainerOpen(path, !isContainerOpen(path));
  state.ui.focusPane = "content";
  renderEditor();
}

function toggleSection(path) {
  toggleContainer(path);
}

function isFieldDetailsOpen(path) {
  return normalizeArray(state.ui.openFieldDetailPaths).includes(pathKey(path));
}

function setFieldDetailsOpen(path, open) {
  const token = pathKey(path);
  const current = new Set(normalizeArray(state.ui.openFieldDetailPaths));
  if (open) {
    current.add(token);
  } else {
    current.delete(token);
    if (state.ui.activeItemPath === token) {
      state.ui.activeItemPath = null;
      state.ui.activeOptionToken = null;
    }
  }
  state.ui.openFieldDetailPaths = [...current];
}

function toggleFieldDetails(path) {
  const shouldOpen = !isFieldDetailsOpen(path);
  if (shouldOpen) {
    ensureAncestorContainersOpen(path);
    state.ui.activeItemPath = pathKey(path);
  }
  setFieldDetailsOpen(path, shouldOpen);
  state.ui.focusPane = "content";
  renderEditor();
}

function toggleSetup() {
  state.ui.setupOpen = !state.ui.setupOpen;
  renderEditor();
}

function toggleSaveStep() {
  state.ui.saveOpen = !state.ui.saveOpen;
  renderEditor();
}

function isItemOpen(path) {
  const node = getNodeByPath(path);
  if (isContainerBlockNode(node)) {
    return isContainerOpen(path);
  }
  if (blockKind(node) === "field") {
    return isFieldDetailsOpen(path);
  }
  return Boolean(state.ui.activeItemPath && state.ui.activeItemPath === pathKey(path));
}

function toggleItem(path) {
  const node = getNodeByPath(path);
  if (isContainerBlockNode(node)) {
    toggleContainer(path);
    return;
  }
  if (blockKind(node) === "field") {
    toggleFieldDetails(path);
    return;
  }

  state.ui.activeItemPath = pathKey(path);
  state.ui.activeOptionToken = null;
  renderEditor();
}

function remapPathAfterMove(path, parentPath, fromIndex, toIndex) {
  if (!pathStartsWith(path, parentPath)) {
    return path;
  }

  const indexPosition = parentPath.length;
  const currentIndex = path[indexPosition];
  if (typeof currentIndex !== "number") {
    return path;
  }

  let nextIndex = currentIndex;
  if (currentIndex === fromIndex) {
    nextIndex = toIndex;
  } else if (fromIndex < toIndex && currentIndex > fromIndex && currentIndex <= toIndex) {
    nextIndex = currentIndex - 1;
  } else if (fromIndex > toIndex && currentIndex >= toIndex && currentIndex < fromIndex) {
    nextIndex = currentIndex + 1;
  }

  if (nextIndex === currentIndex) {
    return path;
  }

  const copy = [...path];
  copy[indexPosition] = nextIndex;
  return copy;
}

function remapUiStateAfterMove(parentPath, fromIndex, toIndex) {
  state.ui.openSectionPaths = [...new Set(
    normalizeArray(state.ui.openSectionPaths).map((serialized) => pathKey(remapPathAfterMove(parsePathKey(serialized), parentPath, fromIndex, toIndex)))
  )];
  state.ui.openFieldDetailPaths = [...new Set(
    normalizeArray(state.ui.openFieldDetailPaths).map((serialized) => pathKey(remapPathAfterMove(parsePathKey(serialized), parentPath, fromIndex, toIndex)))
  )];

  if (state.ui.activeItemPath) {
    state.ui.activeItemPath = pathKey(remapPathAfterMove(parsePathKey(state.ui.activeItemPath), parentPath, fromIndex, toIndex));
  }
}

function setDirty(value) {
  state.dirty = value;
  dirtyBadgeEl.classList.toggle("hidden", !value);
  saveBtnEl.disabled = !value;
  saveBtnEl.textContent = value ? "Save" : "Saved";
  renderSaveDock();
}

function setStatus(message, isError = false) {
  statusTextEl.textContent = message;
  statusTextEl.dataset.tone = isError ? "error" : "normal";
}

function getNodeByPath(path) {
  let cursor = state.draft;
  for (const segment of path) {
    cursor = cursor?.[segment];
  }
  return cursor;
}

function getParentCollection(path) {
  const parentPath = path.slice(0, -1);
  return {
    collection: getNodeByPath(parentPath),
    index: path[path.length - 1],
  };
}

function setBoundValue(target, bind, rawValue) {
  if (target === state.draft && bind === "form_key") {
    setDraftFormKey(rawValue);
    syncRootMetaToBlockSchema();
    return;
  }

  if (target === state.draft && bind === "form_notes") {
    setDraftFormNotes(rawValue);
    syncRootMetaToBlockSchema();
    return;
  }

  if (target === state.draft && bind.startsWith("record_identity.")) {
    setDraftRecordIdentityValue(bind.replace("record_identity.", ""), rawValue);
    syncRootMetaToBlockSchema();
    return;
  }

  if (target === state.draft && bind.startsWith("print_config.")) {
    setDraftPrintConfigValue(bind.replace("print_config.", ""), rawValue);
    syncRootMetaToBlockSchema();
    return;
  }

  if (isStoredBlockNode(target)) {
    const props = getNodeProps(target);
    if (bind === "name") {
      target.name = rawValue;
      return;
    }
    if (bind === "sample_rows") {
      props.sample_rows = parsePositiveInt(rawValue, 3);
      return;
    }
    if (
      bind === "key" ||
      bind === "notes" ||
      bind === "reference_text" ||
      bind === "normal_min" ||
      bind === "normal_max" ||
      bind === "unit_hint" ||
      bind === "content" ||
      bind === "columns"
    ) {
      props[bind] = rawValue;
      return;
    }
  }

  const parts = bind.split(".");
  let cursor = target;
  for (let index = 0; index < parts.length - 1; index += 1) {
    cursor = cursor[parts[index]];
  }
  const key = parts[parts.length - 1];
  if (key.includes("order")) {
    cursor[key] = Number(rawValue || 0);
    return;
  }
  cursor[key] = rawValue;
}

function makeBlankGroup() {
  return {
    id: freshBlockId("field_group", "new_container"),
    kind: "field_group",
    name: "New Container",
    props: {
      key: "new_container",
      order: 1,
      notes: [],
    },
    children: [],
  };
}

function makeBlankField() {
  return {
    id: freshBlockId("field", "new_field"),
    kind: "field",
    name: "New Field",
    props: {
      key: "new_field",
      order: 1,
      control: "input",
      data_type: "text",
      unit_hint: "",
      reference_text: "",
      normal_min: "",
      normal_max: "",
      notes: [],
      options: [],
    },
    children: [],
  };
}

function makeBlankSection() {
  return {
    id: freshBlockId("section", "new_container"),
    kind: "section",
    name: "New Container",
    props: {
      key: "new_container",
      order: 1,
      notes: [],
    },
    children: [],
  };
}

function makeBlankNote() {
  return {
    id: freshBlockId("note", "note"),
    kind: "note",
    name: "Note",
    props: {
      key: "note",
      order: 1,
      content: "Add note text here.",
      notes: [],
    },
    children: [],
  };
}

function makeBlankDivider() {
  return {
    id: freshBlockId("divider", "divider"),
    kind: "divider",
    name: "Divider",
    props: {
      key: "divider",
      order: 1,
      content: "",
      notes: [],
    },
    children: [],
  };
}

function makeBlankTable() {
  return {
    id: freshBlockId("table", "results_table"),
    kind: "table",
    name: "Results Table",
    props: {
      key: "results_table",
      order: 1,
      columns: ["Test", "Result", "Reference Range"],
      sample_rows: 3,
      notes: [],
    },
    children: [],
  };
}

function makeDefaultPatientInfoBlock() {
  const children = DEFAULT_PATIENT_INFO_FIELDS.map((field, index) => {
    const props = {
      key: field.key,
      order: index + 1,
      control: field.control || "input",
      data_type: field.dataType,
      unit_hint: "",
      reference_text: "",
      normal_min: "",
      normal_max: "",
      notes: [],
      options: normalizeArray(field.options).map((option, optionIndex) => {
        const optionName = option && typeof option === "object"
          ? compactText(option.name || option.label || option.value)
          : compactText(option);
        return {
          name: optionName,
          key: slugify(optionName || `option_${optionIndex + 1}`),
          order: optionIndex + 1,
          is_normal: false,
        };
      }),
    };
    if (field.required) {
      props.required = true;
    }
    return {
      id: freshBlockId("field", `patient_${field.key}`),
      kind: "field",
      name: field.name,
      props,
      children: [],
    };
  });

  return {
    id: freshBlockId("field_group", "patient_information"),
    kind: "field_group",
    name: "Patient Information",
    props: {
      key: "patient_information",
      order: 1,
      notes: [],
    },
    children,
  };
}

function makeBlankBlock(kind) {
  if (kind === "section") {
    return makeBlankSection();
  }
  if (kind === "note") {
    return makeBlankNote();
  }
  if (kind === "divider") {
    return makeBlankDivider();
  }
  if (kind === "table") {
    return makeBlankTable();
  }
  if (kind === "field_group") {
    return makeBlankGroup();
  }
  return makeBlankField();
}

function navigateWithIntent(url) {
  allowIntentionalUnload = true;
  window.location.assign(url);
}

function uniqueSlug(base, used) {
  const root = slugify(base || "item");
  let candidate = root;
  let suffix = 2;
  while (used.has(candidate)) {
    candidate = `${root}_${suffix}`;
    suffix += 1;
  }
  used.add(candidate);
  return candidate;
}

function freshBlockId(kind, key) {
  return `blk_${slugify(`${kind}_${key}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`)}`;
}

function makeBlankForm(config = {}) {
  const formName = String(config.name || "").trim() || "Untitled Form";
  const locationName = String(config.locationName || "").trim();
  const patientInfoBlock = makeDefaultPatientInfoBlock();
  const patientNameField = patientInfoBlock.children.find((field) => getNodeProps(field).key === "name");
  const caseNumberField = patientInfoBlock.children.find((field) => getNodeProps(field).key === "case_number");

  const draft = {
    slug: null,
    name: formName,
    location_name: locationName || "Top level",
    location_path_label: isTopLevelLocationName(locationName) ? "Top level" : locationName,
    location_node_key: String(config.libraryParentNodeKey || "").trim() || null,
    location_kind: isTopLevelLocationName(locationName) ? "top_level" : "folder",
    library_parent_node_key: String(config.libraryParentNodeKey || "").trim() || null,
    library_new_container_name: String(config.libraryNewContainerName || "").trim() || null,
    current_version_number: 0,
    summary: "",
    block_schema: {
      schema_version: 1,
      source_kind: ACTIVE_BLOCK_SCHEMA_SOURCE,
      meta: {
        form_key: slugify(formName),
        form_order: 1,
        default_patient_info_materialized: true,
        signatories: defaultSignatorySlots(),
        record_identity: {
          primary_field_id: patientNameField?.id || "",
          secondary_field_id: caseNumberField?.id || "",
          searchable_field_ids: [
            patientNameField?.id || "",
            caseNumberField?.id || "",
          ].filter(Boolean),
        },
      },
      blocks: [patientInfoBlock],
    },
  };
  syncDraftLocationState(draft);
  return ensureDraftBlockState(draft);
}

function makeCopyName(name) {
  const base = String(name || "Untitled").trim() || "Untitled";
  return base.endsWith(" Copy") ? `${base} 2` : `${base} Copy`;
}

function cloneNode(node) {
  const copy = deepClone(node);
  copy.name = makeCopyName(copy.name);
  if (isStoredBlockNode(copy)) {
    const props = getNodeProps(copy);
    if (props.key) {
      props.key = `${slugify(props.key)}_copy`;
    }
    refreshClonedBlockIds(copy);
    return copy;
  }
  if (copy.key) {
    copy.key = `${slugify(copy.key)}_copy`;
  }
  return copy;
}

function refreshClonedBlockIds(node) {
  if (!isStoredBlockNode(node)) {
    return;
  }

  const props = getNodeProps(node);
  node.id = freshBlockId(node.kind || "node", props.key || node.name || "copy");

  if (blockKind(node) === "field") {
    const usedOptionKeys = new Set();
    getInputOptions(node).forEach((option, index) => {
      const key = uniqueSlug(option.key || option.name || `option_${index + 1}`, usedOptionKeys);
      option.id = `${node.id}.${key}`;
      option.key = key;
      option.order = index + 1;
    });
  }

  getNodeChildren(node).forEach(refreshClonedBlockIds);
}

function inferInputType(field) {
  if (getInputControl(field) === "select" || getInputDataType(field) === "enum") {
    return "choice";
  }
  const match = INPUT_TYPES.find((item) => item.dataType === getInputDataType(field) && item.control === getInputControl(field));
  return match?.id || "text";
}

function applyInputType(field, typeId) {
  const selected = INPUT_TYPES.find((item) => item.id === typeId) || INPUT_TYPES[0];
  if (!isBlockNode(field)) {
    return;
  }
  const props = getNodeProps(field);
  delete props.field_type;
  props.control = selected.control;
  props.data_type = selected.dataType;
  if (selected.id === "choice") {
    const options = getInputOptions(field);
    if (!options.length) {
      options.push({ name: "Option 1", key: "option_1", order: 1, is_normal: false });
    }
  }
  if (selected.id !== "number") {
    delete props.normal_min;
    delete props.normal_max;
  }
}

function syncNodeKeys(node) {
  if (!isStoredBlockNode(node)) {
    return;
  }
  const props = getNodeProps(node);
  if (node.name && !props.key) {
    props.key = slugify(node.name);
  }
  getNodeChildren(node).forEach(syncNodeKeys);
}

function syncDraftKeys() {
  if (!state.draft) {
    return;
  }
  setDraftFormKey(getDraftFormKey(state.draft), state.draft);
  syncRootMetaToBlockSchema(state.draft);
  topLevelBlocks().forEach(syncNodeKeys);
  syncDraftBlockState();
}

function touch(options = {}) {
  syncDraftBlockState();
  setDirty(true);
  renderShellSummary();
  renderPreview();
  renderJson();
  syncSaveSurface();
  if (options.full) {
    renderEditor();
  }
  if (options.library) {
    renderFormList();
  }
}

function syncSaveSurface() {
  const titleEl = document.getElementById("saveStateTitle");
  const metaEl = document.getElementById("saveStateMeta");
  if (!titleEl || !metaEl || !state.draft) {
    return;
  }

  const dirtyLabel = state.dirty ? "Changes ready" : "Saved";
  const helperCopy = state.dirty
    ? "Save when this version feels right."
    : "Nothing new to save.";

  titleEl.textContent = dirtyLabel;
  metaEl.textContent = `${currentVersionLabel()} | ${helperCopy}`;
}

async function bootstrap() {
  setStatus("Loading builder");
  state.bootstrap = await api("/api/builder/bootstrap");
  renderFormList();
  const draftConfig = {
    name: String(initialQuery.get("draft_name") || "").trim(),
    locationName: String(initialQuery.get("location_name") || "").trim(),
    libraryParentNodeKey: String(initialQuery.get("library_parent_node_key") || "").trim(),
    libraryNewContainerName: String(initialQuery.get("library_new_container_name") || "").trim(),
  };

  if (initialBuilderMode === "new") {
    startNewForm(draftConfig);
  } else if (initialFormSlug) {
    await loadForm(initialFormSlug);
    if (initialBuilderMode === "duplicate") {
      duplicateCurrentForm(draftConfig);
    }
  } else if (state.bootstrap.selected_form_slug) {
    await loadForm(state.bootstrap.selected_form_slug);
  } else {
    startNewForm();
  }
}

async function loadForm(slug) {
  if (slug === state.selectedFormSlug && state.draft) {
    state.ui.libraryOpen = false;
    setStatus(`Still in ${state.draft.name}`);
    renderAll();
    return;
  }

  if (!await resolveDirtyBeforeContinue()) {
    return;
  }

  const form = await api(`/api/forms/${slug}`);
  state.selectedFormSlug = slug;
  state.loadedForm = ensureDraftBlockState(deepClone(form));
  state.draft = ensureDraftBlockState(deepClone(form));
  state.baselineDraft = ensureDraftBlockState(deepClone(form));
  resetPrintPreview();
  resetEditorPanels();
  setDirty(false);
  state.ui.libraryOpen = false;
  setStatus(`${form.name} ready`);
  renderAll();
}

function startNewForm(config = {}) {
  state.selectedFormSlug = null;
  state.loadedForm = null;
  state.draft = ensureDraftBlockState(makeBlankForm(config));
  state.baselineDraft = ensureDraftBlockState(deepClone(state.draft));
  resetPrintPreview();
  resetEditorPanels();
  setDirty(true);
  state.ui.libraryOpen = false;
  setStatus("Blank draft ready");
  renderAll();
}

function duplicateCurrentForm(overrides = {}) {
  if (!state.draft) {
    startNewForm(overrides);
    return;
  }
  const copy = deepClone(state.draft);
  copy.slug = null;
  copy.current_version_number = 0;
  copy.summary = "";
  copy.name = String(overrides.name || "").trim() || makeCopyName(copy.name);
  const nextLocationName = String(overrides.locationName || "").trim();
  if (nextLocationName) {
    copy.location_name = nextLocationName;
    copy.location_path_label = nextLocationName;
  }
  copy.library_parent_node_key = String(overrides.libraryParentNodeKey || "").trim() || copy.library_parent_node_key || null;
  copy.library_new_container_name = String(overrides.libraryNewContainerName || "").trim() || copy.library_new_container_name || null;
  if (
    !copy.library_parent_node_key
    && !copy.library_new_container_name
    && isTopLevelLocationName(copy.location_name)
  ) {
    copy.location_name = "Top level";
    copy.location_path_label = "Top level";
  }
  syncDraftLocationState(copy);
  setDraftFormKey(slugify(copy.name), copy);
  state.selectedFormSlug = null;
  state.loadedForm = null;
  state.draft = ensureDraftBlockState(copy);
  state.baselineDraft = ensureDraftBlockState(deepClone(copy));
  resetPrintPreview();
  resetEditorPanels();
  setDirty(true);
  state.ui.libraryOpen = false;
  setStatus("New draft copied from the current form");
  renderAll();
}

async function resetCurrentDraft() {
  if (!state.baselineDraft) {
    return;
  }

  const message = state.selectedFormSlug
    ? "Go back to the last saved version of this form."
    : "Clear this draft and go back to its starting point.";
  const decision = await openDecisionDialog({
    eyebrow: "Reset draft",
    title: state.selectedFormSlug ? "Reset to the saved version?" : "Reset this draft?",
    message,
    cancelLabel: "Keep editing",
    confirmLabel: state.selectedFormSlug ? "Reset draft" : "Clear draft",
    destructive: true,
  });
  if (decision !== "confirm") {
    return;
  }

  state.draft = ensureDraftBlockState(deepClone(state.baselineDraft));
  resetEditorPanels();
  setDirty(false);
  setStatus(state.selectedFormSlug ? "Returned to the last saved version" : "Draft reset");
  renderAll();
}

async function confirmDeleteNode(path) {
  const decision = await openDecisionDialog({
    eyebrow: "Remove item",
    title: "Remove this item from the form?",
    message: "This only changes the current draft until you save.",
    cancelLabel: "Keep item",
    confirmLabel: "Remove item",
    destructive: true,
  });

  if (decision === "confirm") {
    deleteAtPath(path);
  }
}

function renderAll() {
  renderShellSummary();
  renderFormList();
  if (state.draft) {
    syncEditorPanels();
  }
  renderOutline();
  renderEditor();
  renderPreview();
  renderJson();
  renderSaveDock();
  syncAdvancedModeUi();
  syncShellState();
}

function renderSaveDock() {
  if (!saveDockEl) {
    return;
  }

  const visible = Boolean(state.draft && state.dirty);
  saveDockEl.hidden = !visible;
  saveDockEl.classList.toggle("hidden", !visible);
  if (!visible) {
    return;
  }

  const note = String(state.draft.summary || "").trim();
  saveDockTitleEl.textContent = state.selectedFormSlug ? "Changes ready" : "Ready to save";
  saveDockMetaEl.textContent = note
    ? `Note: ${note}`
    : "Save now or keep editing.";
}

function renderFormList() {
  const query = formSearchEl.value.trim().toLowerCase();
  formListEl.innerHTML = "";

  const matching = quickSwitchForms().filter((form) => {
    if (!query) {
      return true;
    }
    const haystack = [
      compactText(form?.name),
      compactText(form?.form_path_label),
      compactText(form?.location_path_label),
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  });

  matching.forEach((form) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "form-link";
    button.dataset.action = "load-form";
    button.dataset.slug = form.slug;
    if (form.slug === state.selectedFormSlug) {
      button.classList.add("active");
    }
    const versionLabel = `v${Number(form.current_version_number || 1)}`;
    button.innerHTML = `
      <strong>${escapeHtml(form.name || "Untitled Form")}</strong>
      <span class="meta">${escapeHtml(quickSwitchLocationLabel(form))} | ${escapeHtml(versionLabel)}</span>
    `;
    formListEl.appendChild(button);
  });

  if (!formListEl.children.length) {
    formListEl.innerHTML = '<div class="empty-state">No forms match that search yet.</div>';
  }
}

function defaultFocusPane() {
  if (!state.selectedFormSlug) {
    return "setup";
  }
  return "content";
}

function syncFocusPane() {
  const focus = String(state.ui.focusPane || "");
  const valid = new Set(["setup", "content", "signatories", "print"]);
  if (!valid.has(focus)) {
    state.ui.focusPane = defaultFocusPane();
  }
}

function setFocusPane(pane) {
  state.ui.focusPane = pane;
  renderAll();
}

function renderOutline() {
  if (!builderOutlineEl) {
    return;
  }

  if (!state.draft) {
    builderOutlineEl.innerHTML = '<div class="empty-state">Open a form to start editing.</div>';
    return;
  }

  const focusPane = String(state.ui.focusPane || defaultFocusPane());

  builderOutlineEl.innerHTML = `
      <div class="outline-head">
        <p class="eyebrow">Workspace</p>
        <h3>${escapeHtml(state.draft.name || "Untitled Form")}</h3>
      </div>

      <nav class="outline-nav">
        <button class="outline-item ${focusPane === "setup" ? "active" : ""}" type="button" data-action="focus-pane" data-pane="setup">
          <span>Basics</span>
        </button>
        <button class="outline-item ${focusPane === "content" ? "active" : ""}" type="button" data-action="focus-pane" data-pane="content">
          <span>Content</span>
        </button>
        <button class="outline-item ${focusPane === "signatories" ? "active" : ""}" type="button" data-action="focus-pane" data-pane="signatories">
          <span>Signatories</span>
        </button>
        <button class="outline-item ${focusPane === "print" ? "active" : ""}" type="button" data-action="focus-pane" data-pane="print">
          <span>Print</span>
        </button>
      </nav>
    `;
  }

function renderEditor() {
  destroySortables();

  if (!state.draft) {
    formEditorEl.innerHTML = '<div class="empty-state">Choose a form to start editing.</div>';
    return;
  }

  syncEditorPanels();
  const focusPane = String(state.ui.focusPane || defaultFocusPane());

  if (focusPane === "setup") {
    formEditorEl.innerHTML = renderFormSetupCard({ focusMode: true });
  } else if (focusPane === "content") {
    formEditorEl.innerHTML = renderContentCard();
  } else if (focusPane === "signatories") {
    formEditorEl.innerHTML = renderSignatoriesCard();
  } else if (focusPane === "print") {
    formEditorEl.innerHTML = renderPrintCard({ focusMode: true });
  } else if (focusPane === "save") {
    formEditorEl.innerHTML = renderSaveCard({ focusMode: true });
  } else {
    formEditorEl.innerHTML = renderContentCard();
  }

  formEditorEl.classList.remove("pane-setup", "pane-content", "pane-signatories", "pane-print", "pane-save");
  formEditorEl.classList.add(`pane-${focusPane}`);

  setupSortableCollections();
  syncPrintPreviewFrame();
}

function renderRecordIdentitySettings() {
  const fields = collectIdentityFieldOptions();
  const identity = getDraftRecordIdentity(state.draft);
  const searchableIds = new Set(identity.searchable_field_ids);
  const fieldOptions = [
    '<option value="">Not set</option>',
    ...fields.map((field) => `
      <option value="${escapeHtml(field.id)}"${identity.primary_field_id === field.id ? " selected" : ""}>${escapeHtml(field.pathLabel)}</option>
    `),
  ].join("");
  const secondaryOptions = [
    '<option value="">Not set</option>',
    ...fields.map((field) => `
      <option value="${escapeHtml(field.id)}"${identity.secondary_field_id === field.id ? " selected" : ""}>${escapeHtml(field.pathLabel)}</option>
    `),
  ].join("");

  return `
    <details class="identity-editor identity-editor--advanced">
      <summary class="identity-editor-summary">
        <span>
          <strong>Record list labels</strong>
          <small>Optional search and display setup</small>
        </span>
      </summary>
      ${fields.length ? `
        <div class="identity-editor-body">
          <div class="inline-grid identity-grid">
            <label>
              <span>Primary</span>
              <select data-bind="record_identity.primary_field_id">
                ${fieldOptions}
              </select>
            </label>
            <label>
              <span>Secondary</span>
              <select data-bind="record_identity.secondary_field_id">
                ${secondaryOptions}
              </select>
            </label>
          </div>
          <div class="identity-search-list">
            <span>Search fields</span>
            <div>
              ${fields.map((field) => `
                <label class="identity-check">
                  <input type="checkbox" data-action="identity-search-field" data-field-id="${escapeHtml(field.id)}" ${searchableIds.has(field.id) ? "checked" : ""}>
                  <span>${escapeHtml(field.pathLabel)}</span>
                </label>
              `).join("")}
            </div>
          </div>
        </div>
      ` : '<div class="empty-state">Add fields in Content first.</div>'}
    </details>
  `;
}

function renderPrintSummarySourceOptions(selectedSource) {
  return PRINT_SUMMARY_SOURCES.map((source) => `
    <option value="${escapeHtml(source.id)}"${selectedSource === source.id ? " selected" : ""}>${escapeHtml(source.label)}</option>
  `).join("");
}

function renderPrintSummaryFieldOptions(fields, selectedFieldId) {
  return [
    '<option value="">Not set</option>',
    ...fields.map((field) => `
      <option value="${escapeHtml(field.id)}"${selectedFieldId === field.id ? " selected" : ""}>${escapeHtml(field.pathLabel)}</option>
    `),
  ].join("");
}

function renderPrintSignatureSourceOptions(selectedSource) {
  return PRINT_SIGNATURE_SOURCES.map((source) => `
    <option value="${escapeHtml(source.id)}"${selectedSource === source.id ? " selected" : ""}>${escapeHtml(source.label)}</option>
  `).join("");
}

function renderPrintFontOptions(selectedFont) {
  return PRINT_FONT_FAMILIES.map((font) => `
    <option value="${escapeHtml(font.id)}"${selectedFont === font.id ? " selected" : ""}>${escapeHtml(font.label)} - ${escapeHtml(font.description)}</option>
  `).join("");
}

function printFontClass(fontFamily) {
  return `print-font-${normalizePrintFontFamily(fontFamily).replaceAll("_", "-")}`;
}

function renderPrintSignatureConfig(side, config, fields) {
  const sideLabel = side === "left" ? "Left signature" : "Right signature";
  const labelKey = `signature_${side}_label`;
  const sourceKey = `signature_${side}_source`;
  const nameKey = `signature_${side}_name`;
  const fieldKey = `signature_${side}_field_id`;
  const source = normalizePrintSignatureSource(config[sourceKey], side === "left" ? "prepared_by" : "blank");
  const manualDisabled = source === "manual" ? "" : " disabled";
  const fieldDisabled = source === "field" ? "" : " disabled";
  return `
    <div class="print-signature-config">
      <div class="print-signature-config__title">
        <strong>${escapeHtml(sideLabel)}</strong>
        <span>${escapeHtml(source === "blank" ? "blank line" : PRINT_SIGNATURE_SOURCES.find((item) => item.id === source)?.label || "blank line")}</span>
      </div>
      <div class="setup-grid">
        <label>
          <span>Role label</span>
          <input data-bind="print_config.${labelKey}" value="${escapeHtml(config[labelKey])}">
        </label>
        <label>
          <span>Name source</span>
          <select data-bind="print_config.${sourceKey}">
            ${renderPrintSignatureSourceOptions(source)}
          </select>
        </label>
      </div>
      <div class="setup-grid">
        <label>
          <span>Manual name</span>
          <input data-bind="print_config.${nameKey}" value="${escapeHtml(config[nameKey])}"${manualDisabled}>
        </label>
        <label>
          <span>Form field</span>
          <select data-bind="print_config.${fieldKey}"${fieldDisabled}>
            ${renderPrintSummaryFieldOptions(fields, config[fieldKey])}
          </select>
        </label>
      </div>
    </div>
  `;
}

function renderPrintSummaryRow(item, index, fields, totalCount) {
  const fieldSelectDisabled = item.source !== "field" ? " disabled" : "";
  return `
    <div class="print-summary-row">
      <div class="print-summary-row__order">
        <button class="ghost mini" type="button" data-action="move-print-summary" data-id="${escapeHtml(item.id)}" data-direction="up" ${index === 0 ? "disabled" : ""}>Up</button>
        <button class="ghost mini" type="button" data-action="move-print-summary" data-id="${escapeHtml(item.id)}" data-direction="down" ${index === totalCount - 1 ? "disabled" : ""}>Down</button>
      </div>
      <label>
        <span>Label</span>
        <input data-action="print-summary-label" data-id="${escapeHtml(item.id)}" value="${escapeHtml(item.label)}">
      </label>
      <label>
        <span>Source</span>
        <select data-action="print-summary-source" data-id="${escapeHtml(item.id)}">
          ${renderPrintSummarySourceOptions(item.source)}
        </select>
      </label>
      <label>
        <span>Field</span>
        <select data-action="print-summary-field" data-id="${escapeHtml(item.id)}"${fieldSelectDisabled}>
          ${renderPrintSummaryFieldOptions(fields, item.field_id)}
        </select>
      </label>
      <button class="ghost mini danger" type="button" data-action="remove-print-summary" data-id="${escapeHtml(item.id)}">Remove</button>
    </div>
  `;
}

function renderPrintSummaryPreview(config) {
  const rows = config.summary_items.map((item) => {
    const sourceLabel = item.source === "field"
      ? defaultPrintSummaryLabel(item.source, item.field_id)
      : printSummarySourceLabel(item.source);
    return `
      <div>
        <span>${escapeHtml(item.label)}</span>
        <strong>${escapeHtml(sourceLabel)}</strong>
      </div>
    `;
  }).join("");

  return `
    <div class="print-mini-preview ${escapeHtml(printFontClass(config.font_family))}" style="--preview-accent: ${escapeHtml(config.accent_color)}; --preview-accent-ink: ${escapeHtml(printAccentInkColor(config.accent_color))}">
      <div class="print-mini-preview__head">
        <span></span>
        <strong>${escapeHtml(state.draft.name || "Untitled Form")}</strong>
      </div>
      ${config.show_summary ? `
        <div class="print-mini-preview__meta">
          ${rows}
        </div>
      ` : `
        <div class="print-mini-preview__patient-first">
          Patient information prints from the form body.
        </div>
      `}
    </div>
  `;
}

function renderPrintPreviewPanel() {
  const preview = state.ui.printPreview;
  const statusCopy = printPreviewStatusCopy();
  const isLoading = preview.status === "loading";
  const hasHtml = Boolean(preview.html);
  const isCurrent = printPreviewIsCurrent();
  const tone = preview.status === "error" ? "error" : (!hasHtml || isCurrent ? "normal" : "stale");
  return `
    <section class="print-live-preview" data-state="${escapeHtml(tone)}">
      <div class="print-live-preview__head">
        <div>
          <p class="eyebrow">Preview</p>
          <h4>Sample print output</h4>
          <span>${escapeHtml(statusCopy)}</span>
        </div>
        <button class="secondary mini" type="button" data-action="refresh-print-preview" ${isLoading ? "disabled" : ""}>
          ${isLoading ? "Updating" : (hasHtml ? "Update" : "Generate")}
        </button>
      </div>
      ${preview.error ? `<div class="error-banner">${escapeHtml(preview.error)}</div>` : ""}
      ${hasHtml ? `
        <div class="print-preview-frame-shell${isCurrent ? "" : " is-stale"}">
          <iframe id="printPreviewFrame" title="Builder print preview"></iframe>
        </div>
      ` : `
        <div class="print-preview-empty">
          <strong>No preview yet</strong>
          <span>Generate a sample A4 result using the current unsaved builder draft.</span>
        </div>
      `}
    </section>
  `;
}

function renderSignatoryTypeOptions(selectedType) {
  return SIGNATORY_INPUT_TYPES.map((type) => `
    <option value="${escapeHtml(type.id)}"${selectedType === type.id ? " selected" : ""}>${escapeHtml(type.label)}</option>
  `).join("");
}

function renderSignatoryDefaultOptions(slot) {
  return [
    '<option value="">No default</option>',
    ...normalizeArray(slot.options).map((option) => `
      <option value="${escapeHtml(option.id)}"${slot.default_option_id === option.id ? " selected" : ""}>${escapeHtml(option.name)}</option>
    `),
  ].join("");
}

function renderSignatoryCard(slot, index, totalCount) {
  const optionsText = signatoryOptionsToText(slot);
  const isManual = slot.input_type === "manual";
  const isStampImage = slot.input_type === "stamp_image";
  const usesOptions = slot.input_type === "person_dropdown" || slot.input_type === "fixed";
  return `
    <details class="signatory-config-card signatory-config-details" data-signatory-id="${escapeHtml(slot.id)}">
      <summary class="signatory-config-summary">
        <div>
          <span class="signatory-index">Signature ${index + 1}</span>
          <strong>${escapeHtml(slot.label || "Signatory")}</strong>
        </div>
        <span class="signatory-summary-meta">${renderSignatoryCompactSummary(slot)}</span>
      </summary>

      <div class="signatory-config-body">
        <div class="row-actions signatory-config-actions">
          <button class="ghost mini" type="button" data-action="move-signatory" data-id="${escapeHtml(slot.id)}" data-direction="up" ${index === 0 ? "disabled" : ""}>Up</button>
          <button class="ghost mini" type="button" data-action="move-signatory" data-id="${escapeHtml(slot.id)}" data-direction="down" ${index === totalCount - 1 ? "disabled" : ""}>Down</button>
          <button class="ghost mini warn" type="button" data-action="remove-signatory" data-id="${escapeHtml(slot.id)}">Remove</button>
        </div>

        <div class="setup-grid">
          <label>
            <span>Role label</span>
            <input data-action="signatory-field" data-id="${escapeHtml(slot.id)}" data-key="label" value="${escapeHtml(slot.label)}" placeholder="Example: Medical Technologist">
          </label>
          <label>
            <span>Type</span>
            <select data-action="signatory-field" data-id="${escapeHtml(slot.id)}" data-key="input_type">
              ${renderSignatoryTypeOptions(slot.input_type)}
            </select>
          </label>
        </div>

        <div class="print-toggle-grid signatory-toggle-grid${isStampImage ? " is-compact" : ""}">
          ${isStampImage ? "" : `
          <label class="identity-check">
            <input type="checkbox" data-action="signatory-toggle" data-id="${escapeHtml(slot.id)}" data-key="required" ${slot.required ? "checked" : ""}>
            <span>Required</span>
          </label>
          `}
          <label class="identity-check">
            <input type="checkbox" data-action="signatory-toggle" data-id="${escapeHtml(slot.id)}" data-key="show_on_print" ${slot.show_on_print ? "checked" : ""}>
            <span>Show on print</span>
          </label>
          ${isStampImage ? "" : `
          <label class="identity-check">
            <input type="checkbox" data-action="signatory-toggle" data-id="${escapeHtml(slot.id)}" data-key="show_license" ${slot.show_license ? "checked" : ""}>
            <span>Show license</span>
          </label>
          <label class="identity-check">
            <input type="checkbox" data-action="signatory-toggle" data-id="${escapeHtml(slot.id)}" data-key="signature_line" ${slot.signature_line ? "checked" : ""}>
            <span>Signature line</span>
          </label>
          `}
        </div>

        ${isStampImage ? `
          <div class="signatory-stamp-editor">
            <div class="signatory-stamp-preview-frame">
              ${slot.stamp_image_url
                ? `<img class="signatory-stamp-preview" src="${escapeHtml(slot.stamp_image_url)}" alt="${escapeHtml(slot.stamp_image_filename || slot.label || "Signatory stamp")}">`
                : `<span>No stamp image uploaded</span>`}
            </div>
            <label class="stacked-input">
              <span>Stamp image</span>
              <input type="file" accept="image/png,image/jpeg,image/webp" data-action="signatory-stamp-upload" data-id="${escapeHtml(slot.id)}">
            </label>
            <p class="signatory-upload-note">Use a cropped image that already contains the signature, printed name, and license text.</p>
          </div>
        ` : ""}

        ${usesOptions ? `
          <div class="setup-grid">
            <label>
              <span>Default</span>
              <select data-action="signatory-field" data-id="${escapeHtml(slot.id)}" data-key="default_option_id">
                ${renderSignatoryDefaultOptions(slot)}
              </select>
            </label>
          </div>
          <label class="stacked-input">
            <span>People</span>
            <textarea data-action="signatory-options" data-id="${escapeHtml(slot.id)}" rows="6" placeholder="One person per line: Name | License">${escapeHtml(optionsText)}</textarea>
          </label>
        ` : ""}

        ${isManual ? `
          <div class="setup-grid">
            <label>
              <span>Default name</span>
              <input data-action="signatory-field" data-id="${escapeHtml(slot.id)}" data-key="manual_name" value="${escapeHtml(slot.manual_name)}">
            </label>
            <label>
              <span>Default license</span>
              <input data-action="signatory-field" data-id="${escapeHtml(slot.id)}" data-key="manual_license" value="${escapeHtml(slot.manual_license)}">
            </label>
          </div>
        ` : ""}
        </div>
    </details>
  `;
}

function renderSignatoriesCard() {
  const slots = getDraftSignatories(state.draft);
  return `
    <section class="editor-card signatories-editor-card">
      <div class="card-head">
        <div>
          <p class="eyebrow">Signatories</p>
          <div class="card-title-row">
            <h3 class="card-title">Print signatories</h3>
            ${renderHelpPopover("Signatories help", "These are selected during record entry and printed as signature lines.")}
          </div>
        </div>
        <div class="top-actions">
          <button class="ghost mini" type="button" data-action="add-signatory">Add signatory</button>
        </div>
      </div>

      <div class="editor-spotlight signatory-spotlight">
        <div>
          <strong>${escapeHtml(slots.length ? `${slots.length} configured` : "No signatories")}</strong>
          <span>Kept separate from normal result fields.</span>
        </div>
      </div>

      <div class="signatory-config-list">
        ${slots.length
          ? slots.map((slot, index) => renderSignatoryCard(slot, index, slots.length)).join("")
          : '<div class="empty-state">No signatory lines yet.</div>'}
      </div>
    </section>
  `;
}

function renderPrintCard() {
  const fields = collectIdentityFieldOptions();
  const config = getDraftPrintConfig(state.draft);
  const summaryItems = normalizePrintSummaryItems(config.summary_items);
  config.summary_items = summaryItems;
  return `
    <section class="editor-card print-config-card">
      <div class="card-head">
        <div>
          <p class="eyebrow">Print</p>
          <div class="card-title-row">
            <h3 class="card-title">Print</h3>
            ${renderHelpPopover("Print help", "Configure the printed result for this form version.")}
          </div>
        </div>
        <div class="editor-spotlight-meta">
          <span class="chip">A4 portrait</span>
        </div>
      </div>

      <div class="print-config-layout">
        <div class="print-config-controls">
          <details class="print-settings-section" open>
            <summary class="print-settings-summary">
              <span>
                <strong>Header and style</strong>
                <small>Color, density, font, and header visibility</small>
              </span>
            </summary>
            <div class="print-settings-body">
              <div class="setup-grid">
                <label>
                  <span>Header color</span>
                  <input class="print-color-input" type="color" data-action="print-config-color" data-key="accent_color" value="${escapeHtml(config.accent_color)}">
                </label>
                <label>
                  <span>Density</span>
                  <select data-bind="print_config.density">
                    <option value="compact"${config.density === "compact" ? " selected" : ""}>Compact</option>
                    <option value="comfortable"${config.density === "comfortable" ? " selected" : ""}>Comfortable</option>
                  </select>
                </label>
                <label>
                  <span>Font</span>
                  <select data-bind="print_config.font_family">
                    ${renderPrintFontOptions(config.font_family)}
                  </select>
                </label>
              </div>

              <div class="print-toggle-grid">
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="show_logo" ${config.show_logo ? "checked" : ""}>
                  <span>Logo</span>
                </label>
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="show_clinic_info" ${config.show_clinic_info ? "checked" : ""}>
                  <span>Clinic details</span>
                </label>
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="show_status" ${config.show_status ? "checked" : ""}>
                  <span>Status</span>
                </label>
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="show_summary" ${config.show_summary ? "checked" : ""}>
                  <span>Top summary</span>
                </label>
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="show_signatures" ${config.show_signatures ? "checked" : ""}>
                  <span>Signatures</span>
                </label>
              </div>
            </div>
          </details>

          <details class="print-settings-section print-body-options">
            <summary class="print-settings-summary">
              <span>
                <strong>Result body</strong>
                <small>Rows, containers, images, and tables</small>
              </span>
            </summary>
            <div class="print-settings-body">
              <div class="print-toggle-grid">
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="hide_empty_fields" ${config.hide_empty_fields ? "checked" : ""}>
                  <span>Hide empty fields</span>
                </label>
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="show_section_titles" ${config.show_section_titles ? "checked" : ""}>
                  <span>Top container headings</span>
                </label>
                <label class="identity-check">
                  <input type="checkbox" data-action="print-config-toggle" data-key="show_group_titles" ${config.show_group_titles ? "checked" : ""}>
                  <span>Nested container headings</span>
                </label>
              </div>
              <div class="setup-grid">
                <label>
                  <span>Image size</span>
                  <select data-bind="print_config.image_size">
                    <option value="small"${config.image_size === "small" ? " selected" : ""}>Small</option>
                    <option value="medium"${config.image_size === "medium" ? " selected" : ""}>Medium</option>
                    <option value="large"${config.image_size === "large" ? " selected" : ""}>Large</option>
                  </select>
                </label>
                <label>
                  <span>Table density</span>
                  <select data-bind="print_config.table_density">
                    <option value="compact"${config.table_density === "compact" ? " selected" : ""}>Compact</option>
                    <option value="comfortable"${config.table_density === "comfortable" ? " selected" : ""}>Comfortable</option>
                  </select>
                </label>
                <label>
                  <span>Result layout</span>
                  <select data-bind="print_config.result_layout">
                    <option value="compact_grid"${config.result_layout === "compact_grid" ? " selected" : ""}>Compact grid</option>
                    <option value="rows"${config.result_layout === "rows" ? " selected" : ""}>Rows</option>
                  </select>
                </label>
              </div>
            </div>
          </details>

          <details class="print-settings-section" ${config.show_summary ? "open" : ""}>
            <summary class="print-settings-summary">
              <span>
                <strong>Signatures and summary</strong>
                <small>${config.show_summary ? `${summaryItems.length} summary rows` : "Summary hidden"}</small>
              </span>
            </summary>
            <div class="print-settings-body">
              <section class="print-signature-editor">
                <div class="reference-editor-head">
                  <span class="reference-range-title">Signatories</span>
                </div>
                <button class="ghost mini" type="button" data-action="focus-pane" data-pane="signatories">Edit signatories</button>
              </section>

              ${config.show_summary ? `
                <section class="print-summary-editor">
                  <div class="reference-editor-head print-summary-head">
                    <span class="reference-range-title">Top summary</span>
                    <button class="ghost mini" type="button" data-action="add-print-summary">Add row</button>
                  </div>
                  <div class="print-summary-list">
                    ${summaryItems.map((item, index) => renderPrintSummaryRow(item, index, fields, summaryItems.length)).join("")}
                  </div>
                </section>
              ` : `
                <section class="print-summary-editor print-summary-editor--quiet">
                  <div class="reference-editor-head">
                    <span class="reference-range-title">Top summary hidden</span>
                  </div>
                </section>
              `}
            </div>
          </details>
        </div>

        ${renderPrintSummaryPreview(config)}
      </div>

      ${renderPrintPreviewPanel()}
    </section>
  `;
}

function renderFormSetupCard(options = {}) {
  const focusMode = Boolean(options.focusMode);
  const setupOpen = focusMode ? true : state.ui.setupOpen;
  const formName = state.draft.name || "Untitled Form";
  const locationName = displayLocationName(state.draft);
  const locationInputValue = editableLocationValue(state.draft);
  const currentVersion = currentVersionLabel();
  return `
    <section class="editor-card">
      <div class="card-head">
        <div>
          <p class="eyebrow">Basics</p>
          <div class="card-title-row">
            <h3 class="card-title">Basics</h3>
            ${renderHelpPopover("Basics help", "Set the name and location. Advanced details are optional.")}
          </div>
        </div>
        ${focusMode ? "" : `
        <div class="top-actions">
          <button class="ghost mini" type="button" data-action="toggle-setup">${setupOpen ? "Hide" : "Show"}</button>
        </div>
        `}
      </div>

      ${setupOpen ? `
        <div class="editor-spotlight">
          <div>
            <strong>${escapeHtml(formName)}</strong>
            <span>${escapeHtml(locationName)}</span>
          </div>
          <div class="editor-spotlight-meta">
            <span class="chip">${escapeHtml(currentVersion)}</span>
          </div>
        </div>
        <div class="setup-grid">
          <label>
            <span>Name</span>
            <input data-bind="name" value="${escapeHtml(formName)}" placeholder="Example: Urinalysis">
          </label>
          <label>
            <span>Location</span>
            <input list="locationSuggestions" data-bind="location_name" value="${escapeHtml(locationInputValue)}" placeholder="Top level or choose a folder">
          </label>
        </div>
        ${renderLocationSuggestions()}
        ${renderRecordIdentitySettings()}
        ${state.ui.advancedMode ? `
          <details class="advanced">
            <summary>Advanced</summary>
            <div class="advanced-grid">
              <label>
                <span>Key</span>
                <input data-bind="form_key" value="${escapeHtml(getDraftFormKey(state.draft))}">
              </label>
              <label style="grid-column: 1 / -1;">
                <span>Notes</span>
                <textarea data-bind="form_notes" data-format="lines">${escapeHtml(getDraftFormNotes(state.draft).join("\n"))}</textarea>
              </label>
            </div>
          </details>
        ` : ""}
      ` : `
        <div class="collapsed-copy">
          <strong>${escapeHtml(formName)}</strong>
          ${escapeHtml(locationName)}
        </div>
      `}
    </section>
  `;
}

function renderSaveCard(options = {}) {
  const focusMode = Boolean(options.focusMode);
  const saveOpen = focusMode ? true : state.ui.saveOpen;
  const note = String(state.draft.summary || "").trim();
  const dirtyLabel = state.dirty ? "Changes ready" : "Saved";
  const helperCopy = state.dirty
    ? "Save when this version feels right."
    : "Nothing new to save.";
  return `
    <section class="editor-card">
      <div class="card-head">
        <div>
          <p class="eyebrow">Save</p>
          <div class="card-title-row">
            <h3 class="card-title">Save</h3>
            ${renderHelpPopover("Save help", "Notes are optional.")}
          </div>
        </div>
        ${focusMode ? "" : `
        <div class="top-actions">
          <button class="ghost mini" type="button" data-action="toggle-save-step">${saveOpen ? "Hide" : "Show"}</button>
        </div>
        `}
      </div>

      ${saveOpen ? `
        <div class="save-spotlight">
          <div>
            <strong id="saveStateTitle">${escapeHtml(dirtyLabel)}</strong>
            <span id="saveStateMeta">${escapeHtml(currentVersionLabel())} | ${escapeHtml(helperCopy)}</span>
          </div>
        </div>
        <div class="save-step-inline">
          <label>
            <span>Note</span>
            <input data-bind="summary" value="${escapeHtml(state.draft.summary || "")}" placeholder="Optional note for this version">
          </label>
          <button class="secondary" type="button" data-action="save-draft">Save</button>
        </div>
      ` : `
        <div class="collapsed-copy">
          <strong>${note ? "Saved note" : "Note is optional"}</strong>
          ${note ? escapeHtml(note) : "You can save without adding one."}
        </div>
      `}
    </section>
  `;
}

function renderNodeActionMenu(path) {
    return `
      <details class="action-details">
        <summary aria-label="More" title="More">...</summary>
        <div class="action-menu">
          <button class="ghost mini" type="button" data-action="duplicate-node" data-path="${encodePath(path)}">Copy</button>
          <button class="ghost mini warn" type="button" data-action="delete-node" data-path="${encodePath(path)}">Remove</button>
        </div>
      </details>
    `;
  }

function renderAddMenu(items, label = "Add") {
    const entries = normalizeArray(items).filter((item) => item?.action && item?.label);
    if (!entries.length) {
      return "";
    }
    return `
      <details class="action-details add-details">
        <summary aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${escapeHtml(label)}</summary>
        <div class="action-menu">
          ${entries.map((item) => `
            <button
              class="ghost mini"
              type="button"
              data-action="${escapeHtml(item.action)}"
              ${item.path ? `data-path="${encodePath(item.path)}"` : ""}
            >${escapeHtml(item.label)}</button>
          `).join("")}
        </div>
      </details>
    `;
  }

function organizerSecondaryLabel(node, title) {
    const kind = blockKind(node);
    const normalizedTitle = compactText(title).toLowerCase();
    if (kind === "section") {
      return compactText(node?.name || "") ? "" : "Container";
    }
    if (kind === "field_group") {
      return compactText(node?.name || "") ? "" : "Container";
    }
    const label = kind === "note"
      ? "Note"
      : kind === "divider"
        ? "Divider"
        : kind === "table"
          ? "Table"
          : summarizeItem(node);
    return label && normalizedTitle !== label.toLowerCase() ? label : "";
  }

function itemOrganizerSecondaryLabel(item, title) {
    if (item.kind === "field_group") {
      return compactText(item.name || "") ? "" : "Container";
    }
    if (isUtilityBlockNode(item)) {
      const summary = summarizeItem(item);
      return summary && compactText(title).toLowerCase() !== summary.toLowerCase() ? summary : "";
    }
    const inputType = inferInputType(item);
    if (!["choice", "image", "date", "time", "datetime"].includes(inputType)) {
      return "";
    }
    const summary = summarizeItem(item);
    return summary && compactText(title).toLowerCase() !== summary.toLowerCase() ? summary : "";
  }

function renderManageFooter(path) {
    return `
      <details class="manage-details">
        <summary>More</summary>
        <div class="manage-actions">
          <button class="ghost mini" type="button" data-action="duplicate-node" data-path="${encodePath(path)}">Copy</button>
          <button class="ghost mini warn" type="button" data-action="delete-node" data-path="${encodePath(path)}">Remove</button>
        </div>
      </details>
    `;
  }

function renderOptionManageFooter(path, index) {
    return `
      <details class="manage-details">
        <summary>More</summary>
        <div class="manage-actions">
          <button class="ghost mini" type="button" data-action="duplicate-option" data-path="${encodePath(path)}" data-index="${index}">Copy</button>
          <button class="ghost mini warn" type="button" data-action="delete-option" data-path="${encodePath(path)}" data-index="${index}">Remove</button>
        </div>
      </details>
    `;
  }

function renderContentOrganizerItem(entry, active) {
  const title = compactText(entry.node?.name) || "Untitled item";
  const secondaryLabel = organizerSecondaryLabel(entry.node, title);

  return `
    <div class="section-organizer-item ${active ? "active" : ""}">
      <button class="drag-handle" type="button" title="Drag to reorder" aria-label="Drag to reorder">
        <span class="drag-dots" aria-hidden="true"></span>
      </button>
      <button class="section-organizer-select" type="button" data-action="focus-content-block" data-path="${encodePath(entry.path)}">
        <span class="section-organizer-copy">
          <strong>${escapeHtml(title)}</strong>
          ${secondaryLabel ? `<span>${escapeHtml(secondaryLabel)}</span>` : ""}
        </span>
      </button>
    </div>
  `;
}

function renderOutlineContentItem(entry, active) {
  const title = compactText(entry.node?.name) || "Untitled item";
  const secondaryLabel = organizerSecondaryLabel(entry.node, title);

  return `
    <button class="outline-subitem ${active ? "active" : ""}" type="button" data-action="focus-content-block" data-path="${encodePath(entry.path)}">
      <span class="outline-copy">
        <strong>${escapeHtml(title)}</strong>
        ${secondaryLabel ? `<span>${escapeHtml(secondaryLabel)}</span>` : ""}
      </span>
    </button>
  `;
}

function renderContentCard() {
  const entries = topLevelContentEntries();
  const hiddenBlockCount = Math.max(0, topLevelBlockEntries().length - entries.length);
  const helpCopy = state.ui.advancedMode
    ? "Add, edit, and order everything here."
    : "Add containers and fields here.";
  const addItems = [
    { action: "add-content-container", label: "Container" },
    { action: "add-content-field", label: "Field" },
    ...(state.ui.advancedMode
      ? [
          { action: "add-content-note", label: "Note" },
          { action: "add-content-table", label: "Table" },
          { action: "add-content-divider", label: "Divider" },
        ]
      : []),
  ];

  return `
    <section class="editor-card content-editor-card">
      <div class="card-head">
        <div>
          <div class="card-title-row">
            <h3 class="card-title">Content</h3>
            ${renderHelpPopover("Content help", helpCopy)}
          </div>
        </div>
        <div class="top-actions">
          ${renderAddMenu(addItems)}
        </div>
      </div>
      <div class="content-workspace-grid">
        <div class="recursive-content-canvas">
          ${entries.length ? `
            <div class="content-tree-list" data-collection-path="${encodePath(["block_schema", "blocks"])}">
              ${entries.map((entry) => renderContentNode(entry.node, entry.path, 0)).join("")}
            </div>
          ` : '<div class="empty-state">No content yet. Add what you need when you are ready.</div>'}
          ${!state.ui.advancedMode && hiddenBlockCount ? '<div class="collapsed-copy">Some advanced items stay hidden until you turn on Advanced.</div>' : ""}
        </div>
        ${renderInlineInputPreview()}
      </div>
    </section>
  `;
}

function renderContentNode(node, path, depth = 0) {
  if (blockKind(node) === "section") {
    return renderSectionCard(node, path, { recursive: true, depth });
  }
  if (blockKind(node) === "field_group" || blockKind(node) === "field") {
    return renderItemCard(node, path, { recursive: true, depth });
  }
  return renderUtilityBlockCard(node, path, { recursive: true, depth });
}

function renderInlineInputPreview() {
  if (!state.draft) {
    return "";
  }

  const previewSegments = topLevelPreviewSegments().filter((segment) => normalizeArray(segment.items).length);
  return `
    <aside class="content-input-preview" aria-label="Input form preview">
      <div class="content-input-preview-head">
        <div>
          <p class="eyebrow">Input preview</p>
          <h4>${escapeHtml(state.draft.name || "Untitled Form")}</h4>
        </div>
        <span class="live-pill compact">
          <span class="live-dot"></span>
          Live
        </span>
      </div>
      ${previewSegments.length ? `
        <div class="content-input-preview-paper">
          ${previewSegments.map((segment) => renderPreviewSection(segment.title, segment.items, `inline_${segment.id}`)).join("")}
        </div>
      ` : '<div class="empty-state">Add fields to see the input form.</div>'}
    </aside>
  `;
}

function resolveFocusedTopLevelBlockEntry(entries) {
  if (!entries.length) {
    return null;
  }

  const activeItemPath = state.ui.activeItemPath ? parsePathKey(state.ui.activeItemPath) : null;
  if (activeItemPath) {
    const matchingItemEntry = entries.find((entry) => pathStartsWith(activeItemPath, entry.path));
    if (matchingItemEntry) {
      return matchingItemEntry;
    }
  }

  const openSectionPath = normalizeArray(state.ui.openSectionPaths)[0] ? parsePathKey(normalizeArray(state.ui.openSectionPaths)[0]) : null;
  if (openSectionPath) {
    const sectionMatch = entries.find((entry) => pathKey(entry.path) === pathKey(openSectionPath));
    if (sectionMatch) {
      return sectionMatch;
    }
  }

  return entries[0];
}

function utilityBlockContent(node) {
  return String(getNodeProps(node).content || "").trim();
}

function getTableColumns(node) {
  const columns = normalizeArray(getNodeProps(node).columns)
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  return columns.length ? columns : ["Column 1", "Column 2"];
}

function getTableSampleRows(node) {
  return Math.max(1, Math.min(parsePositiveInt(getNodeProps(node).sample_rows, 3), 6));
}

function renderUtilityBlockCard(node, path) {
  const kind = blockKind(node);
  const isNote = kind === "note";
  const isTable = kind === "table";
  const title = isNote ? "Note" : isTable ? "Table" : "Divider";
  const namePlaceholder = isNote
    ? "Example: Preparation Note"
    : isTable
      ? "Example: Results Table"
      : "Optional divider label";
  const content = utilityBlockContent(node);
  const columns = getTableColumns(node);
  const sampleRows = getTableSampleRows(node);

  return `
    <article class="item-card utility-card is-open is-focused" data-node-path="${encodePath(path)}" data-parent-path="${encodePath(path.slice(0, -1))}">
      <div class="item-head item-head-focused">
        <div>
          <h4 class="item-display-title">${escapeHtml(node.name || title)}</h4>
        </div>
        <div class="row-actions">
          <button class="drag-handle" type="button" title="Drag to reorder" aria-label="Drag to reorder">
            <span class="drag-dots" aria-hidden="true"></span>
          </button>
        </div>
      </div>
      <p class="item-focus-copy">${escapeHtml(
        isNote
          ? "Appears in the preview."
          : isTable
            ? "Shows a sample table."
            : "Adds a visual break."
      )}</p>

      <div class="inline-grid item-basics-grid compact">
        <label>
          <span>Name</span>
          <input class="item-title-input" data-path="${encodePath(path)}" data-bind="name" value="${escapeHtml(node.name || "")}" placeholder="${escapeHtml(namePlaceholder)}">
        </label>
      </div>

      ${isNote ? `
        <label class="stacked-input">
          <span>Text</span>
          <textarea data-path="${encodePath(path)}" data-bind="content" rows="5" placeholder="Write the note shown in the preview.">${escapeHtml(content)}</textarea>
        </label>
      ` : isTable ? `
        <label class="stacked-input">
          <span>Columns</span>
          <textarea data-path="${encodePath(path)}" data-bind="columns" data-format="lines" rows="4" placeholder="One column name per line">${escapeHtml(columns.join("\n"))}</textarea>
        </label>
        <div class="inline-grid item-basics-grid compact">
          <label>
            <span>Rows</span>
            <input type="number" min="1" max="6" data-path="${encodePath(path)}" data-bind="sample_rows" value="${escapeHtml(sampleRows)}">
          </label>
        </div>
      ` : `
        <label class="stacked-input">
          <span>Caption</span>
          <input data-path="${encodePath(path)}" data-bind="content" value="${escapeHtml(content)}" placeholder="Optional short caption">
        </label>
      `}

      ${state.ui.advancedMode ? `
        <details class="advanced">
          <summary>Advanced</summary>
          <div class="advanced-grid">
            <label>
              <span>Key</span>
              <input data-path="${encodePath(path)}" data-bind="key" value="${escapeHtml(getNodeKey(node) || "")}">
            </label>
            <label style="grid-column: 1 / -1;">
              <span>Notes</span>
              <textarea data-path="${encodePath(path)}" data-bind="notes" data-format="lines">${escapeHtml(getNodeNotes(node).join("\n"))}</textarea>
            </label>
          </div>
        </details>
      ` : ""}
      ${renderManageFooter(path)}
    </article>
  `;
}


function renderSectionCard(section, path, options = {}) {
  const focusedCard = Boolean(options.focusedCard);
  const recursive = Boolean(options.recursive);
  const depth = Number(options.depth || 0);
  const open = recursive ? isContainerOpen(path) : Boolean(options.forceOpen) || isSectionOpen(path);
  const showHeaderActions = !focusedCard || !options.hideToggle;
  const childCount = getNodeChildren(section).length;
  const addItems = [
    { action: "add-field", label: "Field", path: [...path, "children"] },
    { action: "add-container", label: "Container", path: [...path, "children"] },
    ...(state.ui.advancedMode
      ? [
          { action: "add-note", label: "Note", path: [...path, "children"] },
          { action: "add-table", label: "Table", path: [...path, "children"] },
          { action: "add-divider", label: "Divider", path: [...path, "children"] },
        ]
      : []),
  ];

  return `
    <article class="section-card ${open ? "is-open" : ""} ${focusedCard ? "is-focused" : ""} ${recursive ? "recursive-container-card" : ""}" data-node-path="${encodePath(path)}" data-parent-path="${encodePath(path.slice(0, -1))}" ${recursive ? `style="--content-depth:${Math.min(depth, 6)}"` : ""}>
      <div class="section-head ${focusedCard ? "section-head-focused" : ""}">
        ${recursive ? `
          <button class="container-toggle" type="button" data-action="toggle-container" data-path="${encodePath(path)}" aria-expanded="${open ? "true" : "false"}" aria-label="${open ? "Collapse container" : "Expand container"}">${open ? "-" : "+"}</button>
        ` : ""}
        <div>
          <div class="item-meta">
            <span class="item-summary">Container</span>
            <span class="item-summary">${childCount} ${childCount === 1 ? "item" : "items"}</span>
          </div>
          <h4 class="section-display-title">${escapeHtml(section.name || "Untitled Container")}</h4>
        </div>
        ${showHeaderActions ? `
        <div class="row-actions">
          ${focusedCard ? "" : `
          <button class="drag-handle" type="button" title="Drag to reorder" aria-label="Drag to reorder">
            <span class="drag-dots" aria-hidden="true"></span>
          </button>
          `}
          ${options.hideToggle || recursive ? "" : `<button class="ghost mini" type="button" data-action="toggle-section" data-path="${encodePath(path)}">${open ? "Hide" : "Show"}</button>`}
          ${renderNodeActionMenu(path)}
        </div>
        ` : ""}
      </div>

      ${open ? `
        <div class="section-builder-head ${focusedCard ? "compact" : ""}">
          <label class="section-title-wrap">
            <span>Name</span>
            <input class="section-title-input" data-path="${encodePath(path)}" data-bind="name" value="${escapeHtml(section.name || "")}" placeholder="Example: Patient Information">
          </label>
          <div class="section-quick-actions">
            ${renderAddMenu(addItems)}
          </div>
        </div>

        <div class="nested-items">
          ${renderItemCollection(getNodeChildren(section), [...path, "children"], recursive ? { recursive: true, depth: depth + 1 } : { focused: true })}
        </div>

        ${state.ui.advancedMode ? `
          <details class="advanced">
            <summary>Advanced</summary>
            <div class="advanced-grid">
            <label>
              <span>Key</span>
              <input data-path="${encodePath(path)}" data-bind="key" value="${escapeHtml(getNodeKey(section) || "")}">
            </label>
            <label style="grid-column: 1 / -1;">
              <span>Notes</span>
              <textarea data-path="${encodePath(path)}" data-bind="notes" data-format="lines">${escapeHtml(getNodeNotes(section).join("\n"))}</textarea>
            </label>
            </div>
          </details>
        ` : ""}
        ${focusedCard ? renderManageFooter(path) : ""}
      ` : ""}
    </article>
  `;
  }

function renderItemCollection(items, collectionPath, options = {}) {
    const entries = normalizeArray(items).map((item, index) => {
      if (item?.path && item?.node) {
        return item;
      }
      return {
        node: item,
        path: [...collectionPath, index],
      };
    });
    const showUtility = options.showUtility ?? state.ui.advancedMode;
    const hiddenUtilityCount = showUtility ? 0 : entries.filter((entry) => isUtilityBlockNode(entry.node)).length;
    const visibleEntries = showUtility
      ? entries
      : entries.filter((entry) => !isUtilityBlockNode(entry.node));
    if (!visibleEntries.length) {
      if (hiddenUtilityCount) {
        return '<div class="empty-state">Some advanced items stay hidden here. Turn on Advanced to edit them.</div>';
      }
      return '<div class="empty-state">No content here yet. Add something when you are ready.</div>';
    }
  if (options.recursive) {
    const nextDepth = Number(options.depth || 0);
    return `
      <div class="item-list recursive-child-list" data-collection-path="${encodePath(collectionPath)}">
        ${visibleEntries.map((entry) => renderContentNode(entry.node, entry.path, nextDepth)).join("")}
      </div>
      ${hiddenUtilityCount ? '<div class="collapsed-copy">Some advanced items stay hidden here. Turn on Advanced to edit them.</div>' : ""}
    `;
  }
  if (options.focused) {
    const selectedIndex = resolveFocusedItemIndex(collectionPath, visibleEntries);
    const selectedEntry = visibleEntries[selectedIndex] || null;
    return `
      <div class="item-organizer" data-collection-path="${encodePath(collectionPath)}">
        ${visibleEntries.map((entry, index) => renderItemOrganizerItem(entry.node, entry.path, index, index === selectedIndex)).join("")}
      </div>
      <div class="item-focus-stage">
        ${selectedEntry
          ? (isUtilityBlockNode(selectedEntry.node)
            ? renderUtilityBlockCard(selectedEntry.node, selectedEntry.path)
            : renderItemCard(selectedEntry.node, selectedEntry.path, { forceOpen: true, hideToggle: true, focusedCard: true }))
          : '<div class="empty-state">Choose an item.</div>'}
      </div>
      ${hiddenUtilityCount ? '<div class="collapsed-copy">Some advanced items stay hidden here. Turn on Advanced to edit them.</div>' : ""}
    `;
  }
  return `
    <div class="item-list" data-collection-path="${encodePath(collectionPath)}">
      ${visibleEntries.map((entry) => (
        isUtilityBlockNode(entry.node)
          ? renderUtilityBlockCard(entry.node, entry.path)
          : renderItemCard(entry.node, entry.path)
      )).join("")}
    </div>
    ${hiddenUtilityCount ? '<div class="collapsed-copy">Some advanced items stay hidden here. Turn on Advanced to edit them.</div>' : ""}
  `;
}

function resolveFocusedItemIndex(collectionPath, items) {
  if (!items.length) {
    return 0;
  }

  if (!state.ui.activeItemPath) {
    return 0;
  }

  const activePath = parsePathKey(state.ui.activeItemPath);
  const matchIndex = items.findIndex((entry, index) => {
    const entryPath = entry?.path || [...collectionPath, index];
    return pathStartsWith(activePath, entryPath);
  });
  return matchIndex >= 0 ? matchIndex : 0;
}

function optionToken(path, index) {
  return `${pathKey(path)}::${index}`;
}

function parseOptionToken(token) {
  const marker = String(token || "");
  const splitIndex = marker.lastIndexOf("::");
  if (splitIndex <= 0) {
    return null;
  }
  const path = parsePathKey(marker.slice(0, splitIndex));
  const index = Number(marker.slice(splitIndex + 2));
  if (!path.length || Number.isNaN(index)) {
    return null;
  }
  return { path, index };
}

function resolveFocusedOptionIndex(path, options) {
  if (!options.length) {
    return -1;
  }
  const parsed = parseOptionToken(state.ui.activeOptionToken);
  if (parsed && pathKey(parsed.path) === pathKey(path) && options[parsed.index]) {
    return parsed.index;
  }
  return 0;
}

function summarizeItem(item) {
  if (item.kind === "note") {
    return "Note";
  }
  if (item.kind === "divider") {
    return "Divider";
  }
  if (item.kind === "table") {
    return "Table";
  }
  if (item.kind === "field_group") {
    return "Container";
  }
  const inputType = inferInputType(item);
  if (inputType === "choice") {
    return "Choice";
  }
  return INPUT_TYPES.find((item) => item.id === inputType)?.label || "Text";
}

function inputTypeLabel(inputType) {
  return INPUT_TYPES.find((item) => item.id === inputType)?.label || "Text";
}

function renderFieldCompactSummary(item, inputType) {
  const props = getNodeProps(item);
  const meta = [];
  const reference = compactText(getInputReferenceText(item));
  const unit = compactText(getInputUnitHint(item));
  const range = inputNormalRangeLabel(item);

  if (props.required) {
    meta.push("Required");
  }
  if (inputType === "choice") {
    const optionCount = getInputOptions(item).length;
    meta.push(`${optionCount} ${optionCount === 1 ? "choice" : "choices"}`);
  }
  if (inputType === "number" && range) {
    meta.push(range);
  } else if (reference) {
    meta.push(`Ref ${reference}`);
  }
  if (unit) {
    meta.push(unit);
  }

  return `
    <div class="field-compact-summary" aria-label="Field summary">
      ${meta.length
        ? meta.slice(0, 4).map((item) => `<span>${escapeHtml(item)}</span>`).join("")
        : '<span>Optional</span>'}
    </div>
  `;
}

function signatoryInputTypeLabel(inputType) {
  return SIGNATORY_INPUT_TYPES.find((item) => item.id === inputType)?.label || "Person choice";
}

function renderSignatoryCompactSummary(slot) {
  const meta = [signatoryInputTypeLabel(slot.input_type)];
  const optionCount = normalizeArray(slot.options).length;
  if (slot.input_type === "person_dropdown" || slot.input_type === "fixed") {
    meta.push(`${optionCount} ${optionCount === 1 ? "person" : "people"}`);
  }
  if (slot.input_type === "stamp_image") {
    meta.push(slot.stamp_image_url ? "Stamp uploaded" : "No stamp");
  }
  if (slot.required && slot.input_type !== "stamp_image") {
    meta.push("Required");
  }
  meta.push(slot.show_on_print ? "Prints" : "Hidden on print");

  return meta.map((item) => `<span>${escapeHtml(item)}</span>`).join("");
}

function renderItemOrganizerItem(item, path, index, active) {
    const isGroup = item.kind === "field_group";
    const isUtility = isUtilityBlockNode(item);
    const title = item.name || (isUtility ? summarizeItem(item) : isGroup ? `Container ${index + 1}` : `Field ${index + 1}`);
    const secondaryLabel = itemOrganizerSecondaryLabel(item, title);
    return `
      <div class="item-organizer-item ${active ? "active" : ""}">
        <button class="drag-handle" type="button" title="Drag to reorder" aria-label="Drag to reorder">
          <span class="drag-dots" aria-hidden="true"></span>
        </button>
        <button class="item-organizer-select" type="button" data-action="focus-item" data-path="${encodePath(path)}">
          <span class="item-organizer-copy">
            <strong>${escapeHtml(title)}</strong>
            ${secondaryLabel ? `<span>${escapeHtml(secondaryLabel)}</span>` : ""}
          </span>
        </button>
      </div>
    `;
  }

function renderItemCard(item, path, options = {}) {
    const isGroup = item.kind === "field_group";
    const open = Boolean(options.forceOpen) || isItemOpen(path);
    const summary = summarizeItem(item);
    const inputType = inferInputType(item);
    const focusedCard = Boolean(options.focusedCard);
    const recursive = Boolean(options.recursive);
    const depth = Number(options.depth || 0);
    const showHeaderActions = !focusedCard || !options.hideToggle;
    const compactReference = compactText(getInputReferenceText(item));
    const compactUnit = compactText(getInputUnitHint(item));
    const focusCopy = isGroup
      ? "Nested content"
      : inputType === "image"
        ? "One image will be uploaded when this form is filled up."
      : [
          compactReference ? `Reference ${compactReference}` : "",
          compactUnit ? `Unit ${compactUnit}` : "",
          inputNormalRangeLabel(item),
        ].filter(Boolean).join(" | ");
    const addItems = isGroup
      ? [
          { action: "add-field", label: "Field", path: [...path, "children"] },
          { action: "add-container", label: "Container", path: [...path, "children"] },
          ...(state.ui.advancedMode
            ? [
                { action: "add-note", label: "Note", path: [...path, "children"] },
                { action: "add-table", label: "Table", path: [...path, "children"] },
                { action: "add-divider", label: "Divider", path: [...path, "children"] },
              ]
            : []),
        ]
      : [];

    if (recursive) {
      const childCount = isGroup ? getNodeChildren(item).length : 0;
      return `
        <article class="item-card ${isGroup ? "group-card recursive-container-card" : "field-card"} ${open ? "is-open" : ""}" data-node-path="${encodePath(path)}" data-parent-path="${encodePath(path.slice(0, -1))}" style="--content-depth:${Math.min(depth, 6)}">
          <div class="item-head">
            <button
              class="${isGroup ? "container-toggle" : "field-details-toggle"}"
              type="button"
              data-action="${isGroup ? "toggle-container" : "toggle-field-details"}"
              data-path="${encodePath(path)}"
              aria-expanded="${open ? "true" : "false"}"
              aria-label="${isGroup ? (open ? "Collapse container" : "Expand container") : (open ? "Hide field details" : "Show field details")}"
            >${open ? "-" : "+"}</button>
            <div>
              <div class="item-meta">
                <span class="item-summary">${escapeHtml(summary)}</span>
                ${isGroup ? `<span class="item-summary">${childCount} ${childCount === 1 ? "item" : "items"}</span>` : ""}
                ${!isGroup && getNodeProps(item).required ? '<span class="item-summary">Required</span>' : ""}
              </div>
              <h4 class="item-display-title">${escapeHtml(item.name || (isGroup ? "Untitled Container" : "Untitled Field"))}</h4>
            </div>
            <div class="row-actions">
              <button class="drag-handle" type="button" title="Drag to reorder" aria-label="Drag to reorder">
                <span class="drag-dots" aria-hidden="true"></span>
              </button>
              ${renderNodeActionMenu(path)}
            </div>
          </div>

          ${isGroup ? `
            ${open ? `
              <div class="section-builder-head">
                <label class="section-title-wrap">
                  <span>Name</span>
                  <input class="section-title-input" data-path="${encodePath(path)}" data-bind="name" value="${escapeHtml(item.name || "")}" placeholder="Example: Microscopic Findings">
                </label>
                <div class="section-quick-actions">
                  ${renderAddMenu(addItems)}
                </div>
              </div>
              <div class="nested-items">
                ${renderItemCollection(getNodeChildren(item), [...path, "children"], { recursive: true, depth: depth + 1 })}
              </div>
              ${state.ui.advancedMode ? `
                <details class="advanced">
                  <summary>Advanced</summary>
                  <div class="advanced-grid">
                    <label>
                      <span>Key</span>
                      <input data-path="${encodePath(path)}" data-bind="key" value="${escapeHtml(getNodeKey(item) || "")}">
                    </label>
                    <label style="grid-column: 1 / -1;">
                      <span>Notes</span>
                      <textarea data-path="${encodePath(path)}" data-bind="notes" data-format="lines">${escapeHtml(getNodeNotes(item).join("\n"))}</textarea>
                    </label>
                  </div>
                </details>
              ` : ""}
            ` : ""}
          ` : `
            ${open ? `
              <div class="field-detail-panel">
                <div class="field-inline-editor">
                  <div class="inline-grid item-basics-grid compact">
                    <label>
                      <span>Name</span>
                      <input class="item-title-input" data-path="${encodePath(path)}" data-bind="name" value="${escapeHtml(item.name || "")}" placeholder="Example: Color">
                    </label>
                    <label>
                      <span>Input</span>
                      <select data-action="item-input-type" data-path="${encodePath(path)}">
                        ${INPUT_TYPES.map((item) => `<option value="${item.id}"${item.id === inputType ? " selected" : ""}>${item.label}</option>`).join("")}
                      </select>
                    </label>
                  </div>
                </div>

                <label class="field-required-toggle">
                  <span>Required before completion</span>
                  <input type="checkbox" data-action="field-required" data-path="${encodePath(path)}" ${getNodeProps(item).required ? "checked" : ""}>
                </label>

                ${inputType === "image" ? `
                  <section class="reference-editor image-answer-editor">
                    <div class="reference-editor-head">
                      <p>One image will be uploaded when this form is filled up.</p>
                    </div>
                  </section>
                ` : `
                  <section class="reference-editor">
                    <div class="inline-grid item-basics-grid compact">
                      <label>
                        <span>Reference</span>
                        <input data-path="${encodePath(path)}" data-bind="reference_text" value="${escapeHtml(getInputReferenceText(item) || "")}" placeholder="${inputType === "choice" ? "Example: Negative" : "Example: 4.5 - 11.0"}">
                      </label>
                      <label>
                        <span>Unit</span>
                        <input data-path="${encodePath(path)}" data-bind="unit_hint" value="${escapeHtml(getInputUnitHint(item) || "")}" placeholder="Example: mg/dL">
                      </label>
                    </div>
                    ${inputType === "number" ? `
                      <div class="reference-range">
                        <div class="reference-range-head">
                          <span class="reference-range-title">Normal range</span>
                          <p>Used for abnormal highlighting in print.</p>
                        </div>
                        <div class="inline-grid reference-range-grid">
                          <label>
                            <span>From</span>
                            <input type="number" step="any" data-path="${encodePath(path)}" data-bind="normal_min" value="${escapeHtml(getInputNormalMin(item) || "")}" placeholder="Example: 4.5">
                          </label>
                          <label>
                            <span>To</span>
                            <input type="number" step="any" data-path="${encodePath(path)}" data-bind="normal_max" value="${escapeHtml(getInputNormalMax(item) || "")}" placeholder="Example: 11.0">
                          </label>
                        </div>
                      </div>
                    ` : ""}
                  </section>
                `}

                ${inputType === "choice" ? renderOptionsEditor(item, path) : ""}

                ${state.ui.advancedMode ? `
                  <details class="advanced">
                    <summary>Advanced</summary>
                    <div class="advanced-grid">
                      <label>
                        <span>Key</span>
                        <input data-path="${encodePath(path)}" data-bind="key" value="${escapeHtml(getNodeKey(item) || "")}">
                      </label>
                      <label style="grid-column: 1 / -1;">
                        <span>Notes</span>
                        <textarea data-path="${encodePath(path)}" data-bind="notes" data-format="lines">${escapeHtml(getNodeNotes(item).join("\n"))}</textarea>
                      </label>
                    </div>
                  </details>
                ` : ""}
              </div>
            ` : renderFieldCompactSummary(item, inputType)}
          `}
        </article>
      `;
    }
  
    return `
      <article class="item-card ${isGroup ? "group-card" : ""} ${open ? "is-open" : ""} ${focusedCard ? "is-focused" : ""}" data-node-path="${encodePath(path)}" data-parent-path="${encodePath(path.slice(0, -1))}">
        <div class="item-head ${focusedCard ? "item-head-focused" : ""}">
          <div>
            ${!focusedCard ? `
            <div class="item-meta">
              <span class="item-summary">${escapeHtml(summary)}</span>
            </div>
            ` : ""}
            <h4 class="item-display-title">${escapeHtml(item.name || (isGroup ? "Untitled Container" : "Untitled Field"))}</h4>
          </div>
          ${showHeaderActions ? `
          <div class="row-actions">
            ${focusedCard ? "" : `
            <button class="drag-handle" type="button" title="Drag to reorder" aria-label="Drag to reorder">
              <span class="drag-dots" aria-hidden="true"></span>
            </button>
            `}
            ${options.hideToggle ? "" : `<button class="ghost mini" type="button" data-action="toggle-item" data-path="${encodePath(path)}">${open ? "Hide" : "Edit"}</button>`}
            ${renderNodeActionMenu(path)}
          </div>
          ` : ""}
        </div>
  
        ${open ? `
          ${focusedCard && focusCopy ? `<p class="item-focus-copy">${escapeHtml(focusCopy)}</p>` : ""}

          <div class="inline-grid item-basics-grid ${focusedCard ? "compact" : ""} ${isGroup ? "single" : ""}">
            <label>
              <span>Name</span>
              <input class="item-title-input" data-path="${encodePath(path)}" data-bind="name" value="${escapeHtml(item.name || "")}" placeholder="${isGroup ? "Example: Vital Signs" : "Example: Color"}">
            </label>
              ${isGroup ? "" : `
                <label>
                  <span>Input</span>
                  <select data-action="item-input-type" data-path="${encodePath(path)}">
                    ${INPUT_TYPES.map((item) => `<option value="${item.id}"${item.id === inputType ? " selected" : ""}>${item.label}</option>`).join("")}
                  </select>
                </label>
              `}
          </div>

          ${isGroup ? "" : `
            <label class="field-required-toggle">
              <span>Required before completion</span>
              <input type="checkbox" data-action="field-required" data-path="${encodePath(path)}" ${getNodeProps(item).required ? "checked" : ""}>
            </label>
          `}

          ${isGroup ? "" : inputType === "image" ? `
            <section class="reference-editor image-answer-editor">
              <div class="reference-editor-head">
                <p>One image will be uploaded when this form is filled up.</p>
              </div>
            </section>
          ` : `
            <section class="reference-editor">
              <div class="reference-editor-head">
                <p>Shown beside the result.</p>
              </div>
              <div class="inline-grid item-basics-grid compact">
                <label>
                  <span>Reference</span>
                  <input data-path="${encodePath(path)}" data-bind="reference_text" value="${escapeHtml(getInputReferenceText(item) || "")}" placeholder="${inputType === "choice" ? "Example: Negative" : "Example: 4.5 - 11.0"}">
                </label>
                <label>
                  <span>Unit</span>
                  <input data-path="${encodePath(path)}" data-bind="unit_hint" value="${escapeHtml(getInputUnitHint(item) || "")}" placeholder="Example: mg/dL">
                </label>
              </div>
              ${inputType === "number" ? `
                <div class="reference-range">
                  <div class="reference-range-head">
                    <span class="reference-range-title">Normal range</span>
                    <p>Used for normal checks.</p>
                  </div>
                  <div class="inline-grid reference-range-grid">
                    <label>
                      <span>From</span>
                      <input type="number" step="any" data-path="${encodePath(path)}" data-bind="normal_min" value="${escapeHtml(getInputNormalMin(item) || "")}" placeholder="Example: 4.5">
                    </label>
                    <label>
                      <span>To</span>
                      <input type="number" step="any" data-path="${encodePath(path)}" data-bind="normal_max" value="${escapeHtml(getInputNormalMax(item) || "")}" placeholder="Example: 11.0">
                    </label>
                  </div>
                </div>
              ` : ""}
            </section>
          `}

        ${isGroup ? `
          <div class="nested-items">
            ${renderItemCollection(getNodeChildren(item), [...path, "children"], focusedCard ? { focused: true } : {})}
          </div>
          <div class="section-actions">
            ${renderAddMenu(addItems)}
          </div>
        ` : ""}

        ${!isGroup && inferInputType(item) === "choice" ? renderOptionsEditor(item, path) : ""}

          ${state.ui.advancedMode ? `
            <details class="advanced">
              <summary>Advanced</summary>
              <div class="advanced-grid">
              <label>
                <span>Key</span>
                <input data-path="${encodePath(path)}" data-bind="key" value="${escapeHtml(getNodeKey(item) || "")}">
              </label>
              <label style="grid-column: 1 / -1;">
                <span>Notes</span>
                <textarea data-path="${encodePath(path)}" data-bind="notes" data-format="lines">${escapeHtml(getNodeNotes(item).join("\n"))}</textarea>
              </label>
              </div>
            </details>
          ` : ""}
          ${focusedCard ? renderManageFooter(path) : ""}
        ` : ""}
      </article>
    `;
  }

function renderOptionsEditor(field, path) {
    const options = getInputOptions(field);
    return `
      <details class="item-stack options-editor options-editor-details" ${options.length ? "" : "open"}>
        <summary class="options-editor-summary">
          <span>
            <strong>Choices</strong>
            <small>${options.length ? `${options.length} configured` : "No choices yet"}</small>
          </span>
        </summary>
        <div class="options-editor-body">
          <div class="option-actions">
            <button class="ghost mini" type="button" data-action="add-option" data-path="${encodePath(path)}">Add option</button>
          </div>
          ${options.length ? `
            <div class="options-list">
              ${options.map((option, index) => `
                <div class="option-row">
                  <label class="option-focus-input">
                    <span>Choice ${index + 1}</span>
                    <input data-action="option-name" data-path="${encodePath(path)}" data-index="${index}" value="${escapeHtml(option.name || "")}" placeholder="Example: Positive">
                  </label>
                  <label class="option-focus-toggle">
                    <span>Normal</span>
                    <input type="checkbox" data-action="option-normal" data-path="${encodePath(path)}" data-index="${index}" ${option.is_normal ? "checked" : ""}>
                  </label>
                  <div class="row-actions option-inline-actions">
                    <button class="ghost mini" type="button" data-action="duplicate-option" data-path="${encodePath(path)}" data-index="${index}">Copy</button>
                    <button class="ghost mini warn" type="button" data-action="delete-option" data-path="${encodePath(path)}" data-index="${index}">Remove</button>
                  </div>
                </div>
              `).join("")}
            </div>
          ` : '<div class="empty-state">Add the choices shown in the dropdown.</div>'}
              </div>
      </details>
  `;
}

function renderPreview() {
  if (!state.draft) {
    previewCanvasEl.innerHTML = '<div class="empty-state">Your preview will appear here.</div>';
    return;
  }

  const previewSegments = topLevelPreviewSegments();
  const previewTargets = previewSegments.map((segment) => ({
    id: segment.id,
    label: segment.label,
  }));
  const activePreviewSectionId = previewTargets.some((item) => item.id === state.ui.activePreviewSectionId)
    ? state.ui.activePreviewSectionId
    : (previewTargets[0]?.id || null);
  state.ui.activePreviewSectionId = activePreviewSectionId;
  previewCanvasEl.innerHTML = `
    <section class="preview-card">
      <div class="preview-shell">
        <div class="preview-head">
          <div>
            <div class="preview-live-row">
              <span class="live-pill">
                <span class="live-dot"></span>
                Live
              </span>
              <span class="preview-sync-copy">Sample</span>
            </div>
            <h3 class="preview-title">${escapeHtml(state.draft.name || "Untitled Form")}</h3>
            <p class="panel-copy">${escapeHtml(displayLocationName(state.draft))} | ${escapeHtml(currentVersionLabel())}</p>
          </div>
        </div>
        <div class="preview-index">
          ${previewTargets.map((item) => `
            <button
              class="preview-index-chip ${item.id === activePreviewSectionId ? "active" : ""}"
              type="button"
              data-preview-target="${escapeHtml(item.id)}"
              aria-pressed="${item.id === activePreviewSectionId ? "true" : "false"}"
            >${escapeHtml(item.label)}</button>
          `).join("")}
        </div>
        <div class="preview-paper">
          ${previewSegments.map((segment) => renderPreviewSection(segment.title, segment.items, segment.id)).join("")}
        </div>
      </div>
    </section>
  `;
  syncPreviewIndexSelection();
}

function previewSectionId(title, index) {
  return `preview_section_${slugify(title)}_${index}`;
}

function renderPreviewSection(title, items, previewId) {
  const normalizedItems = normalizeArray(items);
  if (!normalizedItems.length) {
    return "";
  }

  return `
    <section class="preview-section" id="${escapeHtml(previewId)}">
      <div class="preview-section-head">
        <h4>${escapeHtml(title)}</h4>
      </div>
      <div class="preview-grid">
        ${normalizedItems.map(renderPreviewItem).join("")}
      </div>
    </section>
  `;
}

function previewRichText(value) {
  return escapeHtml(String(value || "")).replaceAll("\n", "<br>");
}

function previewInputType(field) {
  const inputType = inferInputType(field);
  if (inputType === "number") {
    return "number";
  }
  if (inputType === "date") {
    return "date";
  }
  if (inputType === "time") {
    return "time";
  }
  if (inputType === "datetime") {
    return "datetime-local";
  }
  return "text";
}

function previewPlaceholder(field) {
  const unitHint = getInputUnitHint(field);
  if (unitHint) {
    return unitHint;
  }
  if (inferInputType(field) === "number") {
    return "Enter value";
  }
  return "Sample input";
}

function renderPreviewItem(item) {
  if (item.kind === "note") {
    const title = String(item.name || "").trim();
    const content = utilityBlockContent(item);
    const showTitle = title && title.toLowerCase() !== "note";
    return `
      <div class="preview-note">
        ${showTitle ? `<div class="preview-note-title">${escapeHtml(title)}</div>` : ""}
        <div class="preview-note-body">${previewRichText(content || "Note text")}</div>
      </div>
    `;
  }

  if (item.kind === "divider") {
    const label = String(item.name || "").trim();
    const caption = utilityBlockContent(item);
    const showLabel = label && label.toLowerCase() !== "divider";
    return `
      <div class="preview-divider">
        <div class="preview-divider-line"></div>
        ${(showLabel || caption) ? `
          <div class="preview-divider-copy">
            ${showLabel ? `<span class="preview-divider-label">${escapeHtml(label)}</span>` : ""}
            ${caption ? `<span class="preview-divider-caption">${escapeHtml(caption)}</span>` : ""}
          </div>
        ` : ""}
      </div>
    `;
  }

  if (item.kind === "field_group") {
    return `
      <div class="preview-group">
        <div class="preview-group-head">
          <div class="preview-group-title">${escapeHtml(item.name || "Container")}</div>
        </div>
        <div class="preview-grid">
          ${getNodeChildren(item).map((child) => renderPreviewItem(child)).join("")}
        </div>
      </div>
    `;
  }

  if (item.kind === "table") {
    const title = String(item.name || "").trim();
    const columns = getTableColumns(item);
    const sampleRows = getTableSampleRows(item);
    const showTitle = title && title.toLowerCase() !== "table";
    return `
      <div class="preview-table">
        ${showTitle ? `<div class="preview-table-title">${escapeHtml(title)}</div>` : ""}
        <div class="preview-table-shell">
          <table>
            <thead>
              <tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>
            </thead>
            <tbody>
              ${Array.from({ length: sampleRows }, () => `
                <tr>
                  ${columns.map(() => '<td><span class="preview-table-placeholder"></span></td>').join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  const hints = [];
  if (getInputUnitHint(item)) hints.push(getInputUnitHint(item));
  if (getInputReferenceText(item)) hints.push(`reference ${getInputReferenceText(item)}`);
  const inputType = inferInputType(item);

  if (inputType === "image") {
    return `
      <label class="preview-field">
        <span>${escapeHtml(item.name || "Untitled Field")}</span>
        <div class="preview-image-upload">
          <strong>Add image</strong>
          <span>One image will be uploaded here.</span>
        </div>
        ${hints.length ? `<div class="preview-hint">${escapeHtml(hints.join(" | "))}</div>` : ""}
      </label>
    `;
  }

  return `
    <label class="preview-field">
      <span>${escapeHtml(item.name || "Untitled Field")}</span>
      ${getInputControl(item) === "select" ? `
        <select disabled>
          ${getInputOptions(item).map((option) => `<option>${escapeHtml(option.name || "Option")}</option>`).join("")}
        </select>
      ` : `<input type="${previewInputType(item)}" placeholder="${escapeHtml(previewPlaceholder(item))}" disabled>`}
      ${hints.length ? `<div class="preview-hint">${escapeHtml(hints.join(" | "))}</div>` : ""}
    </label>
  `;
}

function countItems(container) {
  let count = 0;
  normalizeArray(container?.blocks).forEach((block) => {
    count += countItems(block);
  });
  getNodeChildren(container).forEach((item) => {
    if (String(item?.kind || "").trim() === "field_group" || String(item?.kind || "").trim() === "section") {
      count += countItems(item);
    } else {
      count += 1;
    }
  });
  return count;
}

function renderJson() {
  jsonOutputEl.textContent = state.draft ? JSON.stringify(state.draft, null, 2) : "{}";
}

function moveWithinCollection(collectionPath, fromIndex, toIndex) {
  const collection = getNodeByPath(collectionPath);
  if (!Array.isArray(collection)) {
    return;
  }

  const boundedTarget = Math.max(0, Math.min(toIndex, collection.length - 1));
  if (fromIndex === boundedTarget) {
    return;
  }

  const [item] = collection.splice(fromIndex, 1);
  collection.splice(boundedTarget, 0, item);
  remapUiStateAfterMove(collectionPath, fromIndex, boundedTarget);
  touch({ full: true, source: "blocks" });
}

function duplicateAtPath(path) {
  const { collection, index } = getParentCollection(path);
  if (!Array.isArray(collection)) {
    return;
  }
  collection.splice(index + 1, 0, cloneNode(collection[index]));
  const duplicatedPath = [...path.slice(0, -1), index + 1];
  const duplicatedNode = getNodeByPath(duplicatedPath);
  if (isContainerBlockNode(duplicatedNode)) {
    ensureAncestorContainersOpen(duplicatedPath);
    setContainerOpen(duplicatedPath, true);
    state.ui.focusPane = "content";
    state.ui.activeItemPath = null;
  } else if (blockKind(duplicatedNode) === "field") {
    ensureAncestorContainersOpen(duplicatedPath);
    state.ui.activeItemPath = pathKey(duplicatedPath);
    setFieldDetailsOpen(duplicatedPath, true);
    state.ui.focusPane = "content";
  } else {
    ensureAncestorContainersOpen(duplicatedPath);
    state.ui.activeItemPath = pathKey(duplicatedPath);
    state.ui.focusPane = "content";
  }
  if (path.includes("children")) {
    state.ui.activeItemPath = pathKey([...path.slice(0, -1), index + 1]);
  }
  touch({ full: true, source: "blocks" });
}

function deleteAtPath(path) {
  const { collection, index } = getParentCollection(path);
  if (!Array.isArray(collection)) {
    return;
  }
  if (state.ui.activeItemPath && pathStartsWith(parsePathKey(state.ui.activeItemPath), path)) {
    state.ui.activeItemPath = null;
  }
  state.ui.openSectionPaths = normalizeArray(state.ui.openSectionPaths).filter((serialized) => !pathStartsWith(parsePathKey(serialized), path));
  state.ui.openFieldDetailPaths = normalizeArray(state.ui.openFieldDetailPaths).filter((serialized) => !pathStartsWith(parsePathKey(serialized), path));
  if (state.ui.activeOptionToken) {
    const parsed = parseOptionToken(state.ui.activeOptionToken);
    if (parsed && pathStartsWith(parsed.path, path)) {
      state.ui.activeOptionToken = null;
    }
  }
  collection.splice(index, 1);
  touch({ full: true, source: "blocks" });
}

function addItemAt(path, kind) {
  const collection = getNodeByPath(path);
  if (!Array.isArray(collection)) {
    return;
  }
  const insertAt = insertChildNodeAtSelection(path, makeBlankBlock(kind));
  const insertedPath = [...path, insertAt];
  ensureAncestorContainersOpen(insertedPath);
  if (kind === "field_group") {
    setContainerOpen(insertedPath, true);
    state.ui.activeItemPath = null;
  } else if (kind === "field") {
    setFieldDetailsOpen(insertedPath, true);
    state.ui.activeItemPath = pathKey(insertedPath);
  } else {
    state.ui.activeItemPath = pathKey(insertedPath);
  }
  state.ui.activeOptionToken = null;
  touch({ full: true, source: "blocks" });
}

function addUtilityAt(path, kind) {
  const collection = getNodeByPath(path);
  if (!Array.isArray(collection)) {
    return;
  }
  const insertAt = insertChildNodeAtSelection(
    path,
    kind === "divider"
      ? makeBlankDivider()
      : kind === "table"
        ? makeBlankTable()
        : makeBlankNote()
  );
  const insertedPath = [...path, insertAt];
  ensureAncestorContainersOpen(insertedPath);
  state.ui.activeItemPath = pathKey(insertedPath);
  state.ui.activeOptionToken = null;
  touch({ full: true, source: "blocks" });
}

function insertChildNodeAtSelection(collectionPath, node) {
  const collection = getNodeByPath(collectionPath);
  if (!Array.isArray(collection)) {
    return -1;
  }

  const activePath = state.ui.activeItemPath ? parsePathKey(state.ui.activeItemPath) : null;
  if (activePath && pathStartsWith(activePath, collectionPath)) {
    const nextSegment = activePath[collectionPath.length];
    if (Number.isInteger(nextSegment)) {
      const insertAt = Math.max(0, Math.min(nextSegment + 1, collection.length));
      collection.splice(insertAt, 0, node);
      return insertAt;
    }
  }

  collection.push(node);
  return collection.length - 1;
}

function addSection() {
  topLevelBlocks().push(makeBlankSection());
  setContainerOpen(["block_schema", "blocks", topLevelBlocks().length - 1], true);
  state.ui.activeItemPath = null;
  state.ui.focusPane = "content";
  touch({ full: true, source: "blocks" });
}

function insertTopLevelContentBlock(kind) {
  const blocks = topLevelBlocks();
  const nextNode = makeBlankBlock(kind);

  if (kind === "section") {
    addSection();
    return;
  }

  if (kind === "field" || kind === "field_group") {
    blocks.push(nextNode);
    const actualIndex = blocks.length - 1;
    const insertedPath = ["block_schema", "blocks", actualIndex];
    if (kind === "field_group") {
      setContainerOpen(insertedPath, true);
      state.ui.activeItemPath = null;
    } else {
      setFieldDetailsOpen(insertedPath, true);
      state.ui.activeItemPath = pathKey(insertedPath);
    }
    state.ui.activeOptionToken = null;
    state.ui.focusPane = "content";
    touch({ full: true, source: "blocks" });
    return;
  }

  blocks.push(nextNode);
  const insertedPath = ["block_schema", "blocks", blocks.length - 1];
  state.ui.activeItemPath = pathKey(insertedPath);
  state.ui.activeOptionToken = null;
  state.ui.focusPane = "content";
  touch({ full: true, source: "blocks" });
}

function addOption(path) {
  const field = getNodeByPath(path);
  const options = getInputOptions(field);
  options.push({ name: `Option ${options.length + 1}`, key: `option_${options.length + 1}`, order: options.length + 1, is_normal: false });
  state.ui.activeOptionToken = optionToken(path, options.length - 1);
  touch({ full: true, source: "blocks" });
}

function duplicateOption(path, index) {
  const field = getNodeByPath(path);
  const options = getInputOptions(field);
  const source = options[index];
  if (!source) {
    return;
  }
  const duplicate = deepClone(source);
  const baseName = String(duplicate.name || "").trim() || "Untitled option";
  duplicate.name = `${baseName} Copy`;
  duplicate.key = slugify(duplicate.name);
  duplicate.is_normal = Boolean(source.is_normal);
  options.splice(index + 1, 0, duplicate);
  state.ui.activeOptionToken = optionToken(path, index + 1);
  touch({ full: true, source: "blocks" });
}

function deleteOption(path, index) {
  const field = getNodeByPath(path);
  const options = getInputOptions(field);
  options.splice(index, 1);
  if (options.length) {
    state.ui.activeOptionToken = optionToken(path, Math.max(0, Math.min(index, options.length - 1)));
  } else {
    state.ui.activeOptionToken = null;
  }
  touch({ full: true, source: "blocks" });
}

async function confirmDeleteOption(path, index) {
  const field = getNodeByPath(path);
  const options = getInputOptions(field);
  const option = options[index];
  if (!option) {
    return;
  }

  const optionName = String(option.name || "").trim() || "this option";
  const decision = await openDecisionDialog({
    eyebrow: "Remove option",
    title: `Remove ${optionName}?`,
    message: "This option will be removed from the choice field.",
    cancelLabel: "Keep option",
    confirmLabel: "Remove option",
    destructive: true,
  });

  if (decision !== "confirm") {
    return;
  }

  deleteOption(path, index);
}

function destroySortables() {
  while (sortableInstances.length) {
    sortableInstances.pop()?.destroy();
  }
}

function setupSortableCollections() {
  if (!window.Sortable) {
    return;
  }

  formEditorEl.querySelectorAll("[data-collection-path]").forEach((collectionEl) => {
    if (!(collectionEl instanceof HTMLElement)) {
      return;
    }

    const collectionPath = decodePath(collectionEl.dataset.collectionPath);
    const items = getNodeByPath(collectionPath);
    if (!Array.isArray(items) || items.length < 2) {
      return;
    }

    const sortable = window.Sortable.create(collectionEl, {
      animation: 160,
      handle: ".drag-handle",
      chosenClass: "is-dragging",
      dragClass: "is-dragging",
      ghostClass: "sortable-ghost",
      onEnd(event) {
        if (event.oldIndex == null || event.newIndex == null || event.oldIndex === event.newIndex) {
          return;
        }

        moveCollectionElementByVisibleOrder(collectionPath, event);
      },
    });

    sortableInstances.push(sortable);
  });
}

function collectionIndexFromElement(element, collectionPath) {
  if (!(element instanceof HTMLElement)) {
    return null;
  }

  const nodePath = decodePath(element.dataset.nodePath || "");
  if (!pathStartsWith(nodePath, collectionPath)) {
    return null;
  }

  const index = nodePath[collectionPath.length];
  return Number.isInteger(index) ? index : null;
}

function moveCollectionElementByVisibleOrder(collectionPath, event) {
  const fromIndex = collectionIndexFromElement(event.item, collectionPath);
  if (fromIndex == null || !(event.to instanceof HTMLElement)) {
    return;
  }

  const visibleElements = [...event.to.children].filter((element) => collectionIndexFromElement(element, collectionPath) != null);
  const visibleIndex = visibleElements.indexOf(event.item);
  if (visibleIndex < 0) {
    return;
  }

  const nextIndex = collectionIndexFromElement(visibleElements[visibleIndex + 1], collectionPath);
  if (nextIndex != null) {
    moveWithinCollection(collectionPath, fromIndex, nextIndex - (fromIndex < nextIndex ? 1 : 0));
    return;
  }

  const previousIndex = collectionIndexFromElement(visibleElements[visibleIndex - 1], collectionPath);
  if (previousIndex != null) {
    moveWithinCollection(collectionPath, fromIndex, previousIndex + (fromIndex < previousIndex ? 0 : 1));
  }
}

async function saveDraft() {
  if (!state.draft) {
    return;
  }

  syncDraftKeys();
  const payload = {
    slug: state.selectedFormSlug,
    name: state.draft.name,
    location_name: displayLocationName(state.draft),
    library_parent_node_key: state.draft.library_parent_node_key || null,
    library_new_container_name: state.draft.library_new_container_name || null,
    summary: state.draft.summary || "",
    form_schema: state.draft.block_schema,
  };

  const saved = state.selectedFormSlug
    ? await api(`/api/forms/${state.selectedFormSlug}`, { method: "PUT", body: JSON.stringify(payload) })
    : await api("/api/forms", { method: "POST", body: JSON.stringify(payload) });

  state.selectedFormSlug = saved.slug;
  state.loadedForm = ensureDraftBlockState(deepClone(saved));
  state.draft = ensureDraftBlockState(deepClone(saved));
  state.baselineDraft = ensureDraftBlockState(deepClone(saved));
  state.bootstrap = await api("/api/builder/bootstrap");
  if (saved.slug && window.location.pathname !== `/forms/${saved.slug}/builder`) {
    window.history.replaceState({}, "", `/forms/${saved.slug}/builder`);
  }
  setDirty(false);
  setStatus(`${saved.name} saved as Version ${saved.current_version_number}`);
  renderAll();
}

function handleRootInput(event) {
  const bind = event.target.dataset.bind;
  if (!bind || !state.draft) {
    return;
  }

  if (event.target.dataset.action === "option-name") {
    return;
  }

  const rawValue = event.target.value;
  if (event.target.dataset.path) {
    const node = getNodeByPath(decodePath(event.target.dataset.path));
    if (!node) {
      return;
    }
    const previousName = bind === "name" ? node.name : "";
    if (event.target.dataset.format === "lines") {
      setBoundValue(node, bind, splitLines(rawValue));
    } else {
      setBoundValue(node, bind, rawValue);
    }
    if (bind === "name") {
      const currentKey = getNodeKey(node);
      if (!currentKey || currentKey === slugify(previousName)) {
        setBoundValue(node, "key", slugify(rawValue));
      }
    }
  } else {
    const previousName = bind === "name" ? state.draft.name : "";
    const previousDraftKey = bind === "name" ? getDraftFormKey(state.draft) : "";
    if (event.target.dataset.format === "lines") {
      setBoundValue(state.draft, bind, splitLines(rawValue));
    } else {
      setBoundValue(state.draft, bind, rawValue);
    }
    if (bind === "name") {
      if (!previousDraftKey || previousDraftKey === slugify(previousName)) {
        setDraftFormKey(slugify(rawValue), state.draft);
      }
      syncDraftLocationState(state.draft);
    } else if (bind === "location_name") {
      if (state.draft.library_new_container_name) {
        state.draft.library_new_container_name = compactText(rawValue) || null;
        state.draft.location_name = compactText(rawValue);
        state.draft.location_path_label = compactText(rawValue);
      } else {
        const matchedLocation = findLocationOptionByFolderPathLabel(rawValue);
        if (matchedLocation) {
          state.draft.library_parent_node_key = matchedLocation.node_key;
          state.draft.location_name = matchedLocation.name;
          state.draft.location_path_label = matchedLocation.folder_path_label;
        } else if (isTopLevelLocationName(rawValue)) {
          state.draft.library_parent_node_key = null;
          state.draft.location_name = "Top level";
          state.draft.location_path_label = "Top level";
        } else {
          state.draft.library_parent_node_key = null;
          state.draft.location_name = compactText(rawValue);
          state.draft.location_path_label = compactText(rawValue);
        }
      }
      syncDraftLocationState(state.draft);
    }
  }

  touch({ source: "blocks", full: bind.startsWith("print_config.") });
}

function handleOptionInput(event) {
  const path = event.target.dataset.path;
  const index = Number(event.target.dataset.index);
  if (!path || Number.isNaN(index)) {
    return;
  }
  const field = getNodeByPath(decodePath(path));
  const options = getInputOptions(field);
  if (!options[index]) {
    return;
  }
  if (event.target.dataset.action === "option-normal") {
    options[index].is_normal = Boolean(event.target.checked);
    touch({ source: "blocks" });
    return;
  }
  options[index].name = event.target.value;
  options[index].key = slugify(event.target.value);
  touch({ source: "blocks" });
}

async function handleEditorClick(event) {
  const actionTarget = event.target.closest("[data-action]");
  if (!actionTarget) {
    return;
  }

  const action = actionTarget.dataset.action;
  if (action === "option-name" || action === "load-form") {
    return;
  }

  if (actionTarget.tagName === "SUMMARY") {
    return;
  }

  const path = actionTarget.dataset.path ? decodePath(actionTarget.dataset.path) : null;

  if (action === "focus-pane") {
    setFocusPane(actionTarget.dataset.pane || defaultFocusPane());
    return;
  }
  if (action === "add-section") {
    addSection();
    return;
  }
  if (action === "add-content-container") {
    insertTopLevelContentBlock("section");
    return;
  }
  if (action === "add-content-section") {
    insertTopLevelContentBlock("section");
    return;
  }
  if (action === "add-content-field") {
    insertTopLevelContentBlock("field");
    return;
  }
  if (action === "add-content-group") {
    insertTopLevelContentBlock("field_group");
    return;
  }
  if (action === "add-content-note") {
    insertTopLevelContentBlock("note");
    return;
  }
  if (action === "add-content-divider") {
    insertTopLevelContentBlock("divider");
    return;
  }
  if (action === "add-content-table") {
    insertTopLevelContentBlock("table");
    return;
  }
  if (action === "toggle-setup") {
    state.ui.focusPane = "setup";
    toggleSetup();
    return;
  }
  if (action === "toggle-save-step") {
    state.ui.focusPane = "save";
    toggleSaveStep();
    return;
  }
  if (action === "focus-option" && path) {
    state.ui.activeOptionToken = optionToken(path, Number(actionTarget.dataset.index));
    renderAll();
    return;
  }
  if (action === "focus-content-block" && path) {
    state.ui.focusPane = "content";
    setContentSelection(path);
    renderAll();
    return;
  }
  if (action === "focus-item" && path) {
    state.ui.activeItemPath = pathKey(path);
    state.ui.activeOptionToken = null;
    renderAll();
    return;
  }
  if (action === "toggle-section" && path) {
    state.ui.focusPane = "content";
    toggleSection(path);
    return;
  }
  if (action === "toggle-container" && path) {
    state.ui.focusPane = "content";
    toggleContainer(path);
    return;
  }
  if (action === "toggle-item" && path) {
    toggleItem(path);
    return;
  }
  if (action === "toggle-field-details" && path) {
    toggleFieldDetails(path);
    return;
  }
  if (action === "add-field" && path) {
    addItemAt(path, "field");
    return;
  }
  if (action === "add-container" && path) {
    addItemAt(path, "field_group");
    return;
  }
  if (action === "add-group" && path) {
    addItemAt(path, "field_group");
    return;
  }
  if (action === "add-note" && path) {
    addUtilityAt(path, "note");
    return;
  }
  if (action === "add-divider" && path) {
    addUtilityAt(path, "divider");
    return;
  }
  if (action === "add-table" && path) {
    addUtilityAt(path, "table");
    return;
  }
  if (action === "duplicate-node" && path) {
    duplicateAtPath(path);
    return;
  }
  if (action === "delete-node" && path) {
    await confirmDeleteNode(path);
    return;
  }
  if (action === "add-option" && path) {
    addOption(path);
    return;
  }
  if (action === "duplicate-option" && path) {
    duplicateOption(path, Number(actionTarget.dataset.index));
    return;
  }
  if (action === "delete-option" && path) {
    await confirmDeleteOption(path, Number(actionTarget.dataset.index));
    return;
  }
  if (action === "add-signatory") {
    addDraftSignatorySlot();
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (action === "remove-signatory") {
    removeDraftSignatorySlot(compactText(actionTarget.dataset.id));
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (action === "move-signatory") {
    moveDraftSignatorySlot(compactText(actionTarget.dataset.id), compactText(actionTarget.dataset.direction));
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (action === "add-print-summary") {
    addDraftPrintSummaryItem();
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (action === "remove-print-summary") {
    removeDraftPrintSummaryItem(compactText(actionTarget.dataset.id));
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (action === "move-print-summary") {
    moveDraftPrintSummaryItem(compactText(actionTarget.dataset.id), compactText(actionTarget.dataset.direction));
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (action === "refresh-print-preview") {
    void refreshPrintPreview();
    return;
  }
  if (action === "save-draft") {
    void saveDraft().catch((error) => {
      console.error(error);
      setStatus(`Save failed: ${error.message}`, true);
    });
  }
}

function handleEditorChange(event) {
  if (event.target.dataset.action === "signatory-field") {
    updateDraftSignatorySlot(
      compactText(event.target.dataset.id),
      compactText(event.target.dataset.key),
      event.target.value
    );
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "signatory-toggle") {
    setDraftSignatoryToggle(
      compactText(event.target.dataset.id),
      compactText(event.target.dataset.key),
      event.target.checked
    );
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "field-required") {
    const field = getNodeByPath(decodePath(event.target.dataset.path));
    if (isStoredBlockNode(field)) {
      const props = getNodeProps(field);
      if (event.target.checked) {
        props.required = true;
      } else {
        delete props.required;
      }
      touch({ full: true, source: "blocks" });
    }
    return;
  }
  if (event.target.dataset.action === "identity-search-field") {
    const fieldId = compactText(event.target.dataset.fieldId);
    const identity = getDraftRecordIdentity(state.draft);
    const nextIds = new Set(identity.searchable_field_ids);
    if (event.target.checked) {
      nextIds.add(fieldId);
    } else {
      nextIds.delete(fieldId);
    }
    setDraftRecordIdentityValue("searchable_field_ids", [...nextIds]);
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "print-config-toggle") {
    setDraftPrintConfigValue(compactText(event.target.dataset.key), event.target.checked);
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "print-config-color") {
    setDraftPrintConfigValue(compactText(event.target.dataset.key), event.target.value);
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "print-summary-source") {
    updateDraftPrintSummaryItem(compactText(event.target.dataset.id), "source", event.target.value);
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "print-summary-field") {
    updateDraftPrintSummaryItem(compactText(event.target.dataset.id), "field_id", event.target.value);
    syncRootMetaToBlockSchema();
    touch({ full: true, source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "item-input-type") {
    const field = getNodeByPath(decodePath(event.target.dataset.path));
    applyInputType(field, event.target.value);
    state.ui.activeOptionToken = event.target.value === "choice"
      ? optionToken(decodePath(event.target.dataset.path), 0)
      : null;
    touch({ full: true, source: "blocks" });
    return;
  }
  handleRootInput(event);
}

function handleOutlineClick(event) {
  const actionTarget = event.target.closest("[data-action]");
  if (!actionTarget) {
    return;
  }

  const action = actionTarget.dataset.action;
  if (action === "focus-pane") {
    setFocusPane(actionTarget.dataset.pane || defaultFocusPane());
    return;
  }

  if (action === "focus-content-block" && actionTarget.dataset.path) {
    state.ui.focusPane = "content";
    setContentSelection(decodePath(actionTarget.dataset.path));
    renderAll();
  }
}

function handlePreviewClick(event) {
  const target = event.target.closest("[data-preview-target]");
  if (!target || !(target instanceof HTMLElement) || !previewCanvasEl) {
    return;
  }

  const previewTarget = String(target.dataset.previewTarget || "");
  if (!previewTarget) {
    return;
  }

  const sectionEl = previewCanvasEl.querySelector(`#${CSS.escape(previewTarget)}`);
  if (!(sectionEl instanceof HTMLElement)) {
    return;
  }

  state.ui.activePreviewSectionId = previewTarget;
  syncPreviewIndexSelection();
  sectionEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

function syncPreviewIndexSelection() {
  if (!previewCanvasEl) {
    return;
  }

  previewCanvasEl.querySelectorAll("[data-preview-target]").forEach((item) => {
    if (!(item instanceof HTMLElement)) {
      return;
    }
    const isActive = item.dataset.previewTarget === state.ui.activePreviewSectionId;
    item.classList.toggle("active", isActive);
    item.setAttribute("aria-pressed", String(isActive));
  });
}

formListEl.addEventListener("click", (event) => {
  const button = event.target.closest('[data-action="load-form"]');
  if (!button) {
    return;
  }
  void loadForm(button.dataset.slug);
});

formEditorEl.addEventListener("click", handleEditorClick);
formEditorEl.addEventListener("input", (event) => {
  if (event.target.dataset.action === "option-name") {
    handleOptionInput(event);
    return;
  }
  if (event.target.dataset.action === "signatory-field") {
    updateDraftSignatorySlot(
      compactText(event.target.dataset.id),
      compactText(event.target.dataset.key),
      event.target.value
    );
    syncRootMetaToBlockSchema();
    touch({ source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "signatory-options") {
    updateDraftSignatoryOptions(compactText(event.target.dataset.id), event.target.value);
    syncRootMetaToBlockSchema();
    touch({ source: "blocks" });
    return;
  }
  if (event.target.dataset.action === "print-summary-label") {
    updateDraftPrintSummaryItem(compactText(event.target.dataset.id), "label", event.target.value);
    syncRootMetaToBlockSchema();
    touch({ source: "blocks" });
    return;
  }
  if (event.target.matches("input, textarea")) {
    handleRootInput(event);
  }
});
formEditorEl.addEventListener("change", (event) => {
  if (event.target.dataset.action === "option-normal") {
    handleOptionInput(event);
    return;
  }
  if (event.target.dataset.action === "signatory-stamp-upload") {
    void uploadSignatoryStamp(event.target);
    return;
  }
  if (event.target.matches("select, input[type='checkbox'], input[type='color']")) {
    handleEditorChange(event);
  }
});
builderOutlineEl?.addEventListener("click", handleOutlineClick);
previewCanvasEl?.addEventListener("click", handlePreviewClick);
formEditorEl.addEventListener("toggle", (event) => {
  const details = event.target;
  if (!(details instanceof HTMLDetailsElement) || !details.open) {
    return;
  }

  if (details.classList.contains("action-details") || details.classList.contains("manage-details")) {
    formEditorEl.querySelectorAll(".action-details[open], .manage-details[open]").forEach((item) => {
      if (item !== details) {
        item.open = false;
      }
    });
  }

  if (details.classList.contains("inline-help")) {
    formEditorEl.querySelectorAll(".inline-help[open]").forEach((item) => {
      if (item !== details) {
        item.open = false;
      }
    });
  }
}, true);

document.addEventListener("click", (event) => {
  if (isDialogOpen()) {
    return;
  }

  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }

  if (target.closest(".action-details, .manage-details, .inline-help")) {
    return;
  }

  closeTransientDetails();
});

document.getElementById("openLibraryBtn").addEventListener("click", () => {
  openLibrary();
});

document.getElementById("closeLibraryBtn").addEventListener("click", () => {
  closeDrawers();
});

if (toggleAdvancedBtnEl) {
  toggleAdvancedBtnEl.addEventListener("click", () => {
    state.ui.advancedMode = !state.ui.advancedMode;
    closeTransientDetails();
    renderAll();
  });
}

drawerScrimEl.addEventListener("click", () => {
  closeDrawers();
});

document.getElementById("newFormBtn").addEventListener("click", async () => {
  if (!await resolveDirtyBeforeContinue()) {
    return;
  }
  navigateWithIntent("/forms/new");
});

document.getElementById("duplicateFormBtn").addEventListener("click", async () => {
  if (!await resolveDirtyBeforeContinue()) {
    return;
  }

  if (state.selectedFormSlug) {
    navigateWithIntent(`/forms/new?source=${encodeURIComponent(state.selectedFormSlug)}`);
    return;
  }

  navigateWithIntent("/forms/new");
});

document.getElementById("saveBtn").addEventListener("click", () => {
  void saveDraft().catch((error) => {
    console.error(error);
    setStatus(`Save failed: ${error.message}`, true);
  });
});

saveDockBtnEl.addEventListener("click", () => {
  void saveDraft().catch((error) => {
    console.error(error);
    setStatus(`Save failed: ${error.message}`, true);
  });
});

resetDraftBtnEl.addEventListener("click", () => {
  void resetCurrentDraft();
});

if (dialogScrimEl) {
  dialogScrimEl.addEventListener("click", () => {
    closeDecisionDialog("cancel");
  });
}

if (confirmDialogCancelBtnEl) {
  confirmDialogCancelBtnEl.addEventListener("click", () => {
    closeDecisionDialog("cancel");
  });
}

if (confirmDialogAltBtnEl) {
  confirmDialogAltBtnEl.addEventListener("click", () => {
    closeDecisionDialog("alt");
  });
}

if (confirmDialogConfirmBtnEl) {
  confirmDialogConfirmBtnEl.addEventListener("click", () => {
    closeDecisionDialog("confirm");
  });
}

formSearchEl.addEventListener("input", renderFormList);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && isDialogOpen()) {
    closeDecisionDialog("cancel");
    return;
  }
  if (event.key === "Escape") {
    closeDrawers();
  }
});

openPreviewBtnEl?.addEventListener("click", () => {
  togglePreview();
});

closePreviewBtnEl?.addEventListener("click", () => {
  state.ui.previewOpen = false;
  renderShellSummary();
  syncShellState();
});

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty || allowIntentionalUnload) {
    return;
  }

  event.preventDefault();
  event.returnValue = "";
});

void bootstrap().catch((error) => {
  console.error(error);
  setStatus(`Unable to load builder: ${error.message}`, true);
});

