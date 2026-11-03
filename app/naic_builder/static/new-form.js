const startFormEl = document.getElementById("startForm");
const formNameEl = document.getElementById("formName");
const formLocationEl = document.getElementById("formLocation");
const existingLocationWrapEl = document.getElementById("existingLocationWrap");
const newLocationWrapEl = document.getElementById("newLocationWrap");
const existingLocationSelectEl = document.getElementById("existingLocationSelect");
const newLocationNameEl = document.getElementById("newLocationName");
const newLocationParentSelectEl = document.getElementById("newLocationParentSelect");
const duplicateSourceWrapEl = document.getElementById("duplicateSourceWrap");
const duplicateSourceSelectEl = document.getElementById("duplicateSourceSelect");
const modeInputEl = document.getElementById("modeInput");
const slugInputEl = document.getElementById("slugInput");
const draftNameInputEl = document.getElementById("draftNameInput");
const locationNameInputEl = document.getElementById("locationNameInput");
const parentNodeKeyInputEl = document.getElementById("parentNodeKeyInput");
const newContainerNameInputEl = document.getElementById("newContainerNameInput");
const summaryLocationEl = document.getElementById("summaryLocation");

function visibleChoice(name) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value || "";
}

function copyName(value) {
  const base = String(value || "").trim();
  if (!base) {
    return "";
  }
  return base.endsWith(" Copy") ? `${base} 2` : `${base} Copy`;
}

function selectedLocationOption() {
  return existingLocationSelectEl?.selectedOptions?.[0] || null;
}

function selectedNewLocationParentOption() {
  return newLocationParentSelectEl?.selectedOptions?.[0] || null;
}

function selectedDuplicateLabel() {
  const option = duplicateSourceSelectEl?.selectedOptions?.[0];
  return String(option?.dataset.formPathLabel || option?.textContent || "").trim() || "existing form";
}

function syncLocationMode() {
  const mode = visibleChoice("location_mode") || "existing";
  const useExistingLocation = mode === "existing";
  const useNewLocation = mode === "new";

  existingLocationWrapEl?.classList.toggle("hidden", !useExistingLocation);
  existingLocationWrapEl && (existingLocationWrapEl.hidden = !useExistingLocation);
  newLocationWrapEl?.classList.toggle("hidden", !useNewLocation);
  newLocationWrapEl && (newLocationWrapEl.hidden = !useNewLocation);

  if (newLocationNameEl) {
    newLocationNameEl.required = useNewLocation;
  }
}

function syncStartMode() {
  const startMode = visibleChoice("start_mode") || "blank";
  const duplicateSelected = startMode === "duplicate";

  duplicateSourceWrapEl?.classList.toggle("hidden", !duplicateSelected);
  duplicateSourceWrapEl && (duplicateSourceWrapEl.hidden = !duplicateSelected);

  if (duplicateSourceSelectEl) {
    duplicateSourceSelectEl.required = duplicateSelected;
  }
}

function updateLocationSummary() {
  const locationMode = visibleChoice("location_mode") || "existing";

  let locationName = "Top level";
  if (locationMode === "new") {
    const parentPath = String(selectedNewLocationParentOption()?.dataset.folderPathLabel || "").trim();
    const newFolderName = String(newLocationNameEl?.value || "").trim();
    locationName = newFolderName ? [parentPath, newFolderName].filter(Boolean).join(" / ") : "Name a folder";
  } else if (locationMode === "existing") {
    locationName = String(selectedLocationOption()?.dataset.folderPathLabel || selectedLocationOption()?.textContent || "").trim();
  }

  if (summaryLocationEl) {
    summaryLocationEl.textContent = locationName || "Choose a folder";
  }
}

function syncHiddenInputs() {
  const locationMode = visibleChoice("location_mode") || "existing";
  const startMode = visibleChoice("start_mode") || "blank";
  const selectedOption = selectedLocationOption();
  const selectedNewParentOption = selectedNewLocationParentOption();

  const usingNewLocation = locationMode === "new";
  const usingRoot = locationMode === "root";
  const parentNodeKey = usingNewLocation
    ? String(selectedNewParentOption?.value || "").trim()
    : usingRoot
      ? ""
      : String(selectedOption?.value || "").trim();
  const locationName = usingRoot
    ? "Top level"
    : usingNewLocation
    ? String(newLocationNameEl?.value || "").trim()
    : String(selectedOption?.dataset.locationName || "").trim();

  if (modeInputEl) {
    modeInputEl.value = startMode === "duplicate" ? "duplicate" : "new";
  }
  if (slugInputEl) {
    slugInputEl.value = startMode === "duplicate" ? String(duplicateSourceSelectEl?.value || "") : "";
  }
  if (draftNameInputEl) {
    draftNameInputEl.value = String(formNameEl?.value || "").trim();
  }
  if (locationNameInputEl) {
    locationNameInputEl.value = locationName;
  }
  if (parentNodeKeyInputEl) {
    parentNodeKeyInputEl.value = parentNodeKey;
  }
  if (newContainerNameInputEl) {
    newContainerNameInputEl.value = usingNewLocation ? String(newLocationNameEl?.value || "").trim() : "";
  }
}

function handleSourceSelectionAutofill() {
  if (!formNameEl || !duplicateSourceSelectEl) {
    return;
  }

  if (document.activeElement === formNameEl) {
    return;
  }

  const currentName = String(formNameEl.value || "").trim();
  if (!currentName || formNameEl.dataset.autofill === "true") {
    formNameEl.value = copyName(selectedDuplicateLabel());
    formNameEl.dataset.autofill = "true";
  }
}

function refreshScreen() {
  syncLocationMode();
  syncStartMode();
  syncHiddenInputs();
  updateLocationSummary();
}

document.querySelectorAll('input[name="location_mode"], input[name="start_mode"]').forEach((input) => {
  input.addEventListener("change", () => {
    if (visibleChoice("start_mode") === "duplicate") {
      handleSourceSelectionAutofill();
    }
    refreshScreen();
  });
});

existingLocationSelectEl?.addEventListener("change", refreshScreen);
newLocationNameEl?.addEventListener("input", refreshScreen);
newLocationParentSelectEl?.addEventListener("change", refreshScreen);
duplicateSourceSelectEl?.addEventListener("change", () => {
  handleSourceSelectionAutofill();
  refreshScreen();
});

formNameEl?.addEventListener("input", () => {
  const value = String(formNameEl.value || "").trim();
  formNameEl.dataset.autofill = value ? "false" : "true";
  refreshScreen();
});

startFormEl?.addEventListener("submit", (event) => {
  syncHiddenInputs();

  if (!String(formNameEl?.value || "").trim()) {
    event.preventDefault();
    formNameEl?.focus();
    formNameEl?.setCustomValidity("Give this form a clear name first.");
    formNameEl?.reportValidity();
    return;
  }

  formNameEl?.setCustomValidity("");

  if (visibleChoice("location_mode") === "new" && !String(newLocationNameEl?.value || "").trim()) {
    event.preventDefault();
    formLocationEl.open = true;
    newLocationNameEl?.focus();
    newLocationNameEl?.setCustomValidity("Name the new folder before you continue.");
    newLocationNameEl?.reportValidity();
    return;
  }

  newLocationNameEl?.setCustomValidity("");
});

startFormEl?.addEventListener("formdata", ({ formData }) => {
  formData.delete("location_mode");
  formData.delete("start_mode");
});

if (visibleChoice("start_mode") === "duplicate") {
  handleSourceSelectionAutofill();
}

refreshScreen();
