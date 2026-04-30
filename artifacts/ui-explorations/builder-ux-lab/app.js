const BLOCK_TYPES = [
  { kind: "container", label: "Container", isContainer: true },
  { kind: "field", label: "Field", isContainer: false },
];

const FIELD_TYPES = ["Text", "Long text", "Number", "Choice", "Date", "Time", "Date & time", "Image"];
const WORKSPACES = [
  { id: "basics", label: "Basics", description: "Form identity and location" },
  { id: "content", label: "Content", description: "Containers and fields" },
  { id: "signatories", label: "Signatories", description: "Special print footer roles" },
  { id: "print", label: "Print", description: "Patient-facing output" },
];
const NORMAL_RULE_OPERATORS = [
  { id: "between", label: "Between" },
  { id: "gt", label: "Greater than" },
  { id: "gte", label: "Greater than or equal" },
  { id: "lt", label: "Less than" },
  { id: "lte", label: "Less than or equal" },
  { id: "eq", label: "Equal to" },
];

const state = {
  activeWorkspace: "content",
  selectedBlockId: "lab_result",
  collapsedBlockIds: new Set(["patient_info"]),
  openFieldDetailIds: new Set(["rbc"]),
  basics: {
    name: "Blood Bank",
    location: "Laboratory Forms",
    description: "Routine blood bank result form.",
  },
  signatories: [
    { id: "medtech_1", label: "Medical Technologist", type: "Choice", required: true, showOnPrint: true },
    { id: "pathologist", label: "Pathologist", type: "Fixed stamp image", required: false, showOnPrint: true },
  ],
  print: {
    accentColor: "#cc3399",
    density: "Compact",
    font: "Arial Narrow",
    showLogo: true,
    showClinicInfo: true,
    showSignatories: true,
    hideEmpty: false,
    resultLayout: "Compact rows",
  },
  root: {
    id: "root",
    kind: "root",
    name: "Blood Bank Form",
    children: [
      {
        id: "patient_info",
        kind: "container",
        name: "Patient Info",
        children: [
          { id: "patient_name", kind: "field", name: "Name", fieldType: "Text", required: true },
          { id: "case_number", kind: "field", name: "Case Number", fieldType: "Text", required: true },
          {
            id: "demographics",
            kind: "container",
            name: "Demographics",
            children: [
              { id: "age", kind: "field", name: "Age", fieldType: "Text", required: false },
              {
                id: "sex",
                kind: "field",
                name: "Sex",
                fieldType: "Choice",
                required: false,
                options: [
                  { label: "Male", isNormal: true },
                  { label: "Female", isNormal: true },
                ],
              },
            ],
          },
        ],
      },
      {
        id: "lab_result",
        kind: "container",
        name: "Lab Result",
        children: [
          {
            id: "microscopic_findings",
            kind: "container",
            name: "Microscopic Findings",
            children: [
              {
                id: "rbc",
                kind: "field",
                name: "RBC",
                fieldType: "Number",
                required: false,
                unit: "/hpf",
                normalRule: { operator: "between", min: "0", max: "2", value: "" },
                referenceText: "Report per high power field.",
              },
              {
                id: "wbc",
                kind: "field",
                name: "WBC",
                fieldType: "Number",
                required: false,
                unit: "/hpf",
                normalRule: { operator: "between", min: "0", max: "5", value: "" },
                referenceText: "Report per high power field.",
              },
            ],
          },
          { id: "remarks", kind: "field", name: "Remarks", fieldType: "Long text", required: false },
        ],
      },
    ],
  },
};

const workspaceNav = document.querySelector("#workspaceNav");
const workspaceEditor = document.querySelector("#workspaceEditor");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function blockType(kind) {
  return BLOCK_TYPES.find((type) => type.kind === kind) || { kind, label: kind, isContainer: false };
}

function isContainerBlock(block) {
  return block && (block.kind === "root" || block.kind === "container");
}

function walkBlocks(block, visitor, depth = 0, parent = null) {
  visitor(block, depth, parent);
  if (Array.isArray(block.children)) {
    block.children.forEach((child) => walkBlocks(child, visitor, depth + 1, block));
  }
}

function findBlock(blockId) {
  let found = null;
  walkBlocks(state.root, (block, depth, parent) => {
    if (block.id === blockId) {
      found = { block, parent, depth };
    }
  });
  return found;
}

function uniqueId(prefix) {
  return `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
}

function countChildren(block) {
  return Array.isArray(block.children) ? block.children.length : 0;
}

function countDescendants(block) {
  let containers = 0;
  let fields = 0;
  if (!Array.isArray(block.children)) {
    return { containers, fields };
  }
  block.children.forEach((child) => {
    if (isContainerBlock(child)) {
      containers += 1;
      const nested = countDescendants(child);
      containers += nested.containers;
      fields += nested.fields;
    } else {
      fields += 1;
    }
  });
  return { containers, fields };
}

function isCollapsed(blockId) {
  return state.collapsedBlockIds.has(blockId);
}

function isFieldDetailsOpen(blockId) {
  return state.openFieldDetailIds.has(blockId);
}

function renderWorkspaceNav() {
  workspaceNav.innerHTML = WORKSPACES.map((workspace) => `
    <button
      class="workspace-nav-item ${state.activeWorkspace === workspace.id ? "active" : ""}"
      type="button"
      data-action="select-workspace"
      data-workspace="${escapeHtml(workspace.id)}"
    >
      <strong>${escapeHtml(workspace.label)}</strong>
      <span>${escapeHtml(workspace.description)}</span>
    </button>
  `).join("");
}

function renderWorkspaceEditor() {
  if (state.activeWorkspace === "content") {
    workspaceEditor.innerHTML = renderContentWorkspace();
    return;
  }
  if (state.activeWorkspace === "basics") {
    workspaceEditor.innerHTML = renderBasicsWorkspace();
    return;
  }
  if (state.activeWorkspace === "signatories") {
    workspaceEditor.innerHTML = renderSignatoriesWorkspace();
    return;
  }
  if (state.activeWorkspace === "print") {
    workspaceEditor.innerHTML = renderPrintWorkspace();
    return;
  }
  workspaceEditor.innerHTML = renderContentWorkspace();
}

function renderContentWorkspace() {
  return `
    <div class="content-workspace-grid">
      <article class="form-canvas-card">
        <div class="form-title-row">
          <label>
            <p class="eyebrow">Content canvas</p>
            <input value="${escapeHtml(state.root.name)}" data-action="rename-block" data-block-id="root" aria-label="Form name">
          </label>
          <div class="canvas-actions">
            <button class="ghost" type="button" data-action="expand-all">Expand all</button>
            <button class="ghost" type="button" data-action="collapse-all">Collapse all</button>
          </div>
        </div>
        <div class="block-tree">
          ${renderChildren(state.root, 0)}
        </div>
        ${renderAddContent(state.root)}
      </article>
      ${renderInputPreview()}
    </div>
  `;
}

function renderBasicsWorkspace() {
  return `
    <article class="workspace-card">
      <p class="eyebrow">Basics</p>
      <h2>Form identity</h2>
      <div class="workspace-form-grid">
        ${renderBasicField("Form name", "name", state.basics.name)}
        ${renderBasicField("Location", "location", state.basics.location)}
        ${renderBasicField("Description", "description", state.basics.description)}
      </div>
    </article>
  `;
}

function renderBasicField(label, key, value) {
  return `
    <label class="workspace-field">
      ${escapeHtml(label)}
      <input value="${escapeHtml(value)}" data-action="basic-field" data-key="${escapeHtml(key)}">
    </label>
  `;
}

function renderSignatoriesWorkspace() {
  return `
    <article class="workspace-card">
      <p class="eyebrow">Signatories</p>
      <h2>Special print footer slots</h2>
      <div class="signatory-list">
        ${state.signatories.map((item) => `
          <article class="signatory-row">
            <label>
              Label
              <input value="${escapeHtml(item.label)}" data-action="signatory-label" data-id="${escapeHtml(item.id)}">
            </label>
            <label>
              Type
              <select data-action="signatory-type" data-id="${escapeHtml(item.id)}">
                ${["Choice", "Fixed stamp image", "Manual text"].map((type) => `
                  <option value="${escapeHtml(type)}" ${item.type === type ? "selected" : ""}>${escapeHtml(type)}</option>
                `).join("")}
              </select>
            </label>
            <label class="inline-check">
              <input type="checkbox" data-action="signatory-required" data-id="${escapeHtml(item.id)}" ${item.required ? "checked" : ""}>
              Required
            </label>
            <label class="inline-check">
              <input type="checkbox" data-action="signatory-print" data-id="${escapeHtml(item.id)}" ${item.showOnPrint ? "checked" : ""}>
              Show on print
            </label>
            ${item.type === "Fixed stamp image" ? `
              <div class="stamp-placeholder">
                <strong>Stamp image</strong>
                <span>Upload area placeholder</span>
              </div>
            ` : ""}
          </article>
        `).join("")}
      </div>
      <button class="add-content-button" type="button" data-action="add-signatory">Add signatory</button>
    </article>
  `;
}

function renderPrintWorkspace() {
  return `
    <article class="workspace-card print-workspace">
      <div>
        <p class="eyebrow">Print</p>
        <h2>Patient-facing output</h2>
      </div>
      <div class="print-layout">
        <div class="print-settings">
          <label class="workspace-field">
            Accent color
            <input type="color" value="${escapeHtml(state.print.accentColor)}" data-action="print-field" data-key="accentColor">
          </label>
          <label class="workspace-field">
            Density
            <select data-action="print-field" data-key="density">
              ${["Compact", "Comfortable"].map((density) => `<option ${state.print.density === density ? "selected" : ""}>${density}</option>`).join("")}
            </select>
          </label>
          <label class="workspace-field">
            Font
            <select data-action="print-field" data-key="font">
              ${["Arial Narrow", "Arial", "Times New Roman"].map((font) => `<option ${state.print.font === font ? "selected" : ""}>${font}</option>`).join("")}
            </select>
          </label>
          <label class="inline-check">
            <input type="checkbox" data-action="print-toggle" data-key="showLogo" ${state.print.showLogo ? "checked" : ""}>
            Show clinic logo
          </label>
          <label class="inline-check">
            <input type="checkbox" data-action="print-toggle" data-key="showClinicInfo" ${state.print.showClinicInfo ? "checked" : ""}>
            Show clinic info
          </label>
          <label class="inline-check">
            <input type="checkbox" data-action="print-toggle" data-key="showSignatories" ${state.print.showSignatories ? "checked" : ""}>
            Show signatories
          </label>
          <label class="inline-check">
            <input type="checkbox" data-action="print-toggle" data-key="hideEmpty" ${state.print.hideEmpty ? "checked" : ""}>
            Hide empty fields
          </label>
          <label class="workspace-field">
            Result layout
            <select data-action="print-field" data-key="resultLayout">
              ${["Compact rows", "Spacious rows"].map((layout) => `<option ${state.print.resultLayout === layout ? "selected" : ""}>${layout}</option>`).join("")}
            </select>
          </label>
        </div>
        ${renderPrintPreview()}
      </div>
    </article>
  `;
}

function renderPrintPreview() {
  return `
    <div class="fake-print-preview" style="--print-accent:${escapeHtml(state.print.accentColor)}">
      <div class="fake-print-header">
        <div class="fake-logo">${state.print.showLogo ? "N" : ""}</div>
        <div>
          <strong>NAIC Medtech</strong>
          <span>${state.print.showClinicInfo ? "Patient-facing laboratory result" : ""}</span>
        </div>
      </div>
      <div class="fake-print-band">Blood Bank</div>
      <div class="fake-print-table">
        <div><span>Patient's Blood Type</span><strong>A+</strong></div>
        <div><span>Blood Component</span><strong>Packed RBC</strong></div>
        <div><span>RBC</span><strong class="abnormal">8 /hpf</strong></div>
      </div>
      ${state.print.showSignatories ? `<div class="fake-print-footer">
        <span>Medical Technologist</span>
        <span>Pathologist</span>
      </div>` : ""}
    </div>
  `;
}

function renderInputPreview() {
  return `
    <section class="input-preview">
      <div class="input-preview-head">
        <strong>Input preview</strong>
        <span>How medtech staff will fill this content.</span>
      </div>
      ${renderInputPreviewBlocks(state.root.children || [])}
    </section>
  `;
}

function renderInputPreviewBlocks(blocks) {
  return blocks.map((block) => {
    if (isContainerBlock(block)) {
      return `
        <div class="input-preview-container">
          <h3>${escapeHtml(block.name)}</h3>
          ${renderInputPreviewBlocks(block.children || [])}
        </div>
      `;
    }
    return `
      <label class="input-preview-field">
        ${escapeHtml(block.name)}${block.required ? " *" : ""}
        <input placeholder="${escapeHtml(block.fieldType || "Text")}">
      </label>
    `;
  }).join("");
}

function renderChildren(block, depth) {
  if (!Array.isArray(block.children) || block.children.length === 0) {
    return `
      <div class="empty-drop-zone">
        <strong>Empty container</strong>
        <span>Add a container or field here.</span>
      </div>
    `;
  }
  return block.children.map((child) => renderBlock(child, depth)).join("");
}

function renderBlock(block, depth) {
  const selected = block.id === state.selectedBlockId;
  const type = blockType(block.kind);
  const isContainer = isContainerBlock(block);
  const collapsed = isContainer && isCollapsed(block.id);
  const detailsOpen = block.kind === "field" && isFieldDetailsOpen(block.id);
  const descendantCount = isContainer ? countDescendants(block) : { containers: 0, fields: 0 };
  return `
    <article class="lego-block lego-block--${escapeHtml(block.kind)} ${selected ? "active" : ""} ${collapsed ? "is-collapsed" : ""}" style="--depth: ${depth}" data-block-id="${escapeHtml(block.id)}">
      <div class="block-main-row">
        ${isContainer ? `
          <button class="collapse-button" type="button" data-action="toggle-collapse" data-block-id="${escapeHtml(block.id)}" aria-label="${collapsed ? "Expand" : "Collapse"} ${escapeHtml(block.name)}" aria-expanded="${collapsed ? "false" : "true"}">
            ${collapsed ? ">" : "v"}
          </button>
        ` : `
          <span class="collapse-placeholder" aria-hidden="true"></span>
        `}
        <button class="block-grip" type="button" data-action="select-block" data-block-id="${escapeHtml(block.id)}" aria-label="Select ${escapeHtml(block.name)}">::</button>
        <label class="block-name">
          <span>${escapeHtml(type.label)}</span>
          <input value="${escapeHtml(block.name)}" data-action="rename-block" data-block-id="${escapeHtml(block.id)}" aria-label="${escapeHtml(type.label)} name">
        </label>
        ${block.kind === "field" ? renderFieldControls(block, detailsOpen) : `<span class="block-count">${descendantCount.containers} containers / ${descendantCount.fields} fields</span>`}
        <button class="icon-button" type="button" data-action="remove-block" data-block-id="${escapeHtml(block.id)}" aria-label="Remove ${escapeHtml(block.name)}">x</button>
      </div>
      ${isContainer ? (collapsed ? "" : `
        <div class="block-children">
          ${renderChildren(block, depth + 1)}
        </div>
        ${renderAddContent(block)}
      `) : renderFieldDetails(block)}
    </article>
  `;
}

function renderFieldControls(block, detailsOpen) {
  return `
    <div class="field-compact-controls">
      <select class="field-type-select" data-action="change-field-type" data-block-id="${escapeHtml(block.id)}" aria-label="Field type">
        ${FIELD_TYPES.map((type) => `
          <option value="${escapeHtml(type)}" ${block.fieldType === type ? "selected" : ""}>${escapeHtml(type)}</option>
        `).join("")}
      </select>
      <button class="details-button" type="button" data-action="toggle-field-details" data-block-id="${escapeHtml(block.id)}" aria-expanded="${detailsOpen ? "true" : "false"}">
        ${detailsOpen ? "Hide details" : "Details"}
      </button>
    </div>
  `;
}

function normalizedChoiceOptions(block) {
  if (!Array.isArray(block.options)) {
    block.options = [];
  }
  block.options = block.options.map((option) => {
    if (typeof option === "string") {
      return { label: option, isNormal: false };
    }
    return {
      label: String(option?.label ?? ""),
      isNormal: Boolean(option?.isNormal),
    };
  });
  return block.options;
}

function renderFieldDetails(block) {
  const detailsOpen = isFieldDetailsOpen(block.id);
  return `
    <div class="field-inline-settings">
      <label>
        <input type="checkbox" data-action="toggle-required" data-block-id="${escapeHtml(block.id)}" ${block.required ? "checked" : ""}>
        Required
      </label>
      <span>${detailsOpen ? "Details are open for this field." : "Open details for choices, normal rules, reference, and unit."}</span>
    </div>
    ${detailsOpen ? `
      ${renderReferenceText(block)}
      ${block.fieldType === "Choice" ? renderChoiceOptions(block) : ""}
      ${block.fieldType === "Number" ? renderNormalRange(block) : ""}
    ` : ""}
  `;
}

function renderReferenceText(block) {
  return `
    <div class="reference-text-editor">
      <label>
        Reference text
        <input value="${escapeHtml(block.referenceText || "")}" data-action="field-reference-text" data-block-id="${escapeHtml(block.id)}" placeholder="Optional display-only guidance">
      </label>
    </div>
  `;
}

function renderChoiceOptions(block) {
  const options = normalizedChoiceOptions(block);
  return `
    <div class="choice-options">
      <div class="choice-options-head">
        <strong>Choices</strong>
        <button type="button" data-action="add-choice-option" data-block-id="${escapeHtml(block.id)}">Add choice</button>
      </div>
      <div class="choice-option-list">
        ${options.length ? options.map((option, index) => `
          <div class="choice-option-row">
            <span>${index + 1}</span>
            <input value="${escapeHtml(option.label)}" data-action="rename-choice-option" data-block-id="${escapeHtml(block.id)}" data-option-index="${index}" aria-label="Choice ${index + 1}">
            <label class="choice-normal-check">
              <input type="checkbox" data-action="toggle-choice-normal" data-block-id="${escapeHtml(block.id)}" data-option-index="${index}" ${option.isNormal ? "checked" : ""}>
              Normal
            </label>
            <button type="button" data-action="remove-choice-option" data-block-id="${escapeHtml(block.id)}" data-option-index="${index}" aria-label="Remove choice ${index + 1}">x</button>
          </div>
        `).join("") : `
          <div class="choice-empty">No choices yet.</div>
        `}
      </div>
    </div>
  `;
}

function renderNormalRange(block) {
  const rule = normalizedNormalRule(block);
  return `
    <div class="normal-range-editor">
      <div class="normal-range-head">
        <strong>Normal rule</strong>
        <span>Shown as reference and can flag abnormal values later.</span>
      </div>
      <div class="normal-range-grid">
        <label>
          Unit
          <input value="${escapeHtml(block.unit || "")}" data-action="field-unit" data-block-id="${escapeHtml(block.id)}" placeholder="Example: /hpf">
        </label>
        <label>
          Rule
          <select data-action="field-normal-operator" data-block-id="${escapeHtml(block.id)}">
            ${NORMAL_RULE_OPERATORS.map((operator) => `
              <option value="${escapeHtml(operator.id)}" ${rule.operator === operator.id ? "selected" : ""}>${escapeHtml(operator.label)}</option>
            `).join("")}
          </select>
        </label>
        ${renderNormalRuleValueInputs(block, rule)}
      </div>
    </div>
  `;
}

function normalizedNormalRule(block) {
  const rule = block.normalRule && typeof block.normalRule === "object" ? block.normalRule : {};
  const operator = NORMAL_RULE_OPERATORS.some((item) => item.id === rule.operator) ? rule.operator : "between";
  block.normalRule = {
    operator,
    min: String(rule.min ?? ""),
    max: String(rule.max ?? ""),
    value: String(rule.value ?? ""),
  };
  return block.normalRule;
}

function renderNormalRuleValueInputs(block, rule) {
  if (rule.operator === "between") {
    return `
      <label>
        Minimum
        <input value="${escapeHtml(rule.min)}" data-action="field-normal-min" data-block-id="${escapeHtml(block.id)}" placeholder="0">
      </label>
      <label>
        Maximum
        <input value="${escapeHtml(rule.max)}" data-action="field-normal-max" data-block-id="${escapeHtml(block.id)}" placeholder="5">
      </label>
    `;
  }
  return `
    <label class="normal-range-wide">
      Value
      <input value="${escapeHtml(rule.value)}" data-action="field-normal-value" data-block-id="${escapeHtml(block.id)}" placeholder="100">
    </label>
  `;
}

function renderAddContent(parentBlock) {
  return `
    <div class="add-content-bar" data-parent-id="${escapeHtml(parentBlock.id)}">
      <span>Add content here</span>
      <div>
        ${BLOCK_TYPES.map((type) => `
          <button type="button" data-action="add-block" data-parent-id="${escapeHtml(parentBlock.id)}" data-kind="${escapeHtml(type.kind)}">${escapeHtml(type.label)}</button>
        `).join("")}
      </div>
    </div>
  `;
}

function render() {
  renderWorkspaceNav();
  renderWorkspaceEditor();
}

function addBlock(parentId, kind) {
  const found = findBlock(parentId);
  if (!found || !isContainerBlock(found.block)) {
    return;
  }
  if (!Array.isArray(found.block.children)) {
    found.block.children = [];
  }
  const id = uniqueId(kind);
  const nextBlock = kind === "container"
    ? { id, kind, name: "New Container", children: [] }
    : { id, kind, name: "New Field", fieldType: "Text", required: false };
  found.block.children.push(nextBlock);
  state.selectedBlockId = id;
}

function removeBlock(blockId) {
  const found = findBlock(blockId);
  if (!found || !found.parent || !Array.isArray(found.parent.children)) {
    return;
  }
  found.parent.children = found.parent.children.filter((block) => block.id !== blockId);
  state.selectedBlockId = found.parent.id === "root" ? found.parent.children[0]?.id || "root" : found.parent.id;
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) {
    return;
  }

  const action = target.dataset.action;
  if (action === "select-workspace") {
    const workspaceId = target.dataset.workspace;
    if (WORKSPACES.some((workspace) => workspace.id === workspaceId)) {
      state.activeWorkspace = workspaceId;
      render();
    }
  }

  if (action === "select-block") {
    state.activeWorkspace = "content";
    state.selectedBlockId = target.dataset.blockId || state.selectedBlockId;
    render();
  }

  if (action === "toggle-collapse") {
    const blockId = target.dataset.blockId;
    if (state.collapsedBlockIds.has(blockId)) {
      state.collapsedBlockIds.delete(blockId);
    } else if (blockId && blockId !== "root") {
      state.collapsedBlockIds.add(blockId);
    }
    state.selectedBlockId = blockId || state.selectedBlockId;
    render();
  }

  if (action === "toggle-field-details") {
    const blockId = target.dataset.blockId;
    if (state.openFieldDetailIds.has(blockId)) {
      state.openFieldDetailIds.delete(blockId);
    } else if (blockId) {
      state.openFieldDetailIds.add(blockId);
    }
    state.selectedBlockId = blockId || state.selectedBlockId;
    render();
  }

  if (action === "collapse-all") {
    walkBlocks(state.root, (block) => {
      if (block.kind === "container") {
        state.collapsedBlockIds.add(block.id);
      }
    });
    render();
  }

  if (action === "expand-all") {
    state.collapsedBlockIds.clear();
    render();
  }

  if (action === "add-root-container") {
    addBlock("root", "container");
    render();
  }

  if (action === "add-block") {
    addBlock(target.dataset.parentId, target.dataset.kind);
    render();
  }

  if (action === "remove-block") {
    removeBlock(target.dataset.blockId);
    render();
  }

  if (action === "add-choice-option") {
    const found = findBlock(target.dataset.blockId);
    if (found?.block?.kind === "field") {
      const options = normalizedChoiceOptions(found.block);
      options.push({ label: `Option ${options.length + 1}`, isNormal: false });
      state.selectedBlockId = found.block.id;
      render();
    }
  }

  if (action === "remove-choice-option") {
    const found = findBlock(target.dataset.blockId);
    const optionIndex = Number(target.dataset.optionIndex);
    if (found?.block?.kind === "field" && Number.isInteger(optionIndex)) {
      normalizedChoiceOptions(found.block).splice(optionIndex, 1);
      state.selectedBlockId = found.block.id;
      render();
    }
  }

  if (action === "add-signatory") {
    state.signatories.push({
      id: uniqueId("signatory"),
      label: "Signatory",
      type: "Choice",
      required: false,
      showOnPrint: true,
    });
    render();
  }
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (
    !(target instanceof HTMLInputElement)
    || ![
      "rename-block",
      "rename-choice-option",
      "field-unit",
      "field-normal-min",
      "field-normal-max",
      "field-normal-value",
      "field-reference-text",
      "basic-field",
      "signatory-label",
    ].includes(target.dataset.action)
  ) {
    return;
  }

  if (target.dataset.action === "basic-field") {
    state.basics[target.dataset.key] = target.value;
    return;
  }
  if (target.dataset.action === "signatory-label") {
    const item = state.signatories.find((signatory) => signatory.id === target.dataset.id);
    if (item) {
      item.label = target.value;
    }
    return;
  }

  const found = findBlock(target.dataset.blockId);
  if (found) {
    if (target.dataset.action === "rename-choice-option") {
      const optionIndex = Number(target.dataset.optionIndex);
      if (Number.isInteger(optionIndex)) {
        normalizedChoiceOptions(found.block)[optionIndex].label = target.value;
      }
      return;
    }
    if (target.dataset.action === "field-unit") {
      found.block.unit = target.value;
      return;
    }
    if (target.dataset.action === "field-normal-min") {
      normalizedNormalRule(found.block).min = target.value;
      return;
    }
    if (target.dataset.action === "field-normal-max") {
      normalizedNormalRule(found.block).max = target.value;
      return;
    }
    if (target.dataset.action === "field-normal-value") {
      normalizedNormalRule(found.block).value = target.value;
      return;
    }
    if (target.dataset.action === "field-reference-text") {
      found.block.referenceText = target.value;
      return;
    }
    found.block.name = target.value;
    state.selectedBlockId = found.block.id;
    renderWorkspaceNav();
  }
});

document.addEventListener("focusin", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }
  const blockEl = target.closest("[data-block-id]");
  if (blockEl?.dataset.blockId && blockEl.dataset.blockId !== state.selectedBlockId) {
    state.selectedBlockId = blockEl.dataset.blockId;
    renderWorkspaceNav();
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (target instanceof HTMLSelectElement && target.dataset.action === "change-field-type") {
    const found = findBlock(target.dataset.blockId);
    if (found) {
      found.block.fieldType = target.value;
      if (target.value === "Choice" && normalizedChoiceOptions(found.block).length === 0) {
        found.block.options.push("Option 1", "Option 2");
      }
      render();
    }
  }
  if (target instanceof HTMLSelectElement && target.dataset.action === "field-normal-operator") {
    const found = findBlock(target.dataset.blockId);
    if (found?.block?.kind === "field") {
      normalizedNormalRule(found.block).operator = target.value;
      render();
    }
  }
  if (target instanceof HTMLSelectElement && target.dataset.action === "signatory-type") {
    const item = state.signatories.find((signatory) => signatory.id === target.dataset.id);
    if (item) {
      item.type = target.value;
      render();
    }
  }
  if (target instanceof HTMLSelectElement && target.dataset.action === "print-field") {
    state.print[target.dataset.key] = target.value;
    render();
  }
  if (target instanceof HTMLInputElement && target.dataset.action === "print-field") {
    state.print[target.dataset.key] = target.value;
    render();
  }
  if (target instanceof HTMLInputElement && target.dataset.action === "print-toggle") {
    state.print[target.dataset.key] = target.checked;
    render();
  }
  if (target instanceof HTMLInputElement && target.dataset.action === "signatory-required") {
    const item = state.signatories.find((signatory) => signatory.id === target.dataset.id);
    if (item) {
      item.required = target.checked;
      render();
    }
  }
  if (target instanceof HTMLInputElement && target.dataset.action === "signatory-print") {
    const item = state.signatories.find((signatory) => signatory.id === target.dataset.id);
    if (item) {
      item.showOnPrint = target.checked;
      render();
    }
  }
  if (target instanceof HTMLInputElement && target.dataset.action === "toggle-required") {
    const found = findBlock(target.dataset.blockId);
    if (found) {
      found.block.required = target.checked;
      render();
    }
  }
  if (target instanceof HTMLInputElement && target.dataset.action === "toggle-choice-normal") {
    const found = findBlock(target.dataset.blockId);
    const optionIndex = Number(target.dataset.optionIndex);
    if (found?.block?.kind === "field" && Number.isInteger(optionIndex)) {
      normalizedChoiceOptions(found.block)[optionIndex].isNormal = target.checked;
      render();
    }
  }
});

render();
