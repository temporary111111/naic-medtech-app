/* Layout editing changes presentation only. Keep the saved grid format and
   original document untouched until the user actually moves or resizes an item. */
(() => {
  "use strict";
  window.NAICPrintLayout = {
    create({ activeTextSizes, schedulePrintFitCheck }) {
      const find = (selector) => document.querySelector(selector);
      const editor = find("[data-print-layout-editor]");
      const paper = find(".print-page");
      const grids = Array.from(document.querySelectorAll("[data-print-layout-grid]"));
      const openButton = find("[data-open-layout-editor]");
      const saveButton = find("[data-layout-save]");
      const cancelButton = find("[data-layout-cancel]");
      const undoButton = find("[data-layout-undo]");
      const redoButton = find("[data-layout-redo]");
      const resetButton = find("[data-layout-reset]");
      const restoreButton = find("[data-layout-restore-form]");
      const title = find("#print-layout-editor-title");
      const hint = find("[data-layout-editor-hint]");
      const status = find("[data-layout-editor-status]");
      const notice = find("[data-layout-save-notice]");
      const future = find("[data-layout-future]");
      const widthTools = find("[data-layout-width-tools]");
      const widthLabel = find("[data-layout-width]");
      const zoomLabel = find("[data-layout-zoom-label]");
      const selection = find("[data-layout-selection]");
      const selectionLabel = find("[data-layout-selection-label]");
      const guide = find("[data-layout-guide]");
      const pageEdge = find("[data-layout-page-edge]");
      const discardDialog = find("[data-layout-discard-dialog]");
      const viewport = find(".print-page-viewport");
      const more = find(".print-layout-more");
      const history = [];
      let historyIndex = -1;
      let baseline = null;
      let baselineFuture = true;
      let editing = false;
      let saving = false;
      let selected = null;
      let gesture = null;
      let zoom = 1;
      let overlayFrame = 0;
      let scrollFrame = 0;
      let discardResolve = null;
      let printDraft = null;
      const temporarilyDisabled = new Map();

      const gridCells = (grid) => Array.from(grid.querySelectorAll(":scope > [data-print-grid-cell]"));
      const units = (grid) => Math.max(2, Number.parseInt(grid.dataset.gridUnits || "2", 10));
      const spans = (grid) => [...new Set(units(grid) <= 4 ? [2, units(grid)] : [2, units(grid) / 2, units(grid) - 2, units(grid)])].filter(Number.isInteger).sort((a, b) => a - b);
      const nearestSpan = (grid, value) => spans(grid).reduce((best, item) => Math.abs(item - value) < Math.abs(best - value) ? item : best);
      const itemId = (cell) => cell.dataset.containerId || cell.dataset.layoutItemId || cell.dataset.blockId || cell.dataset.fieldId || "";
      const spanOf = (cell) => Number.parseInt(cell.dataset.printSpan || "2", 10);
      const presentation = (grid) => grid.dataset.layoutPresentation || "grid";
      const labelOf = (cell) => cell.querySelector(".print-section-title, .print-group-title, .print-row-name strong, .print-grid-cell-head strong")?.textContent.trim() || "Untitled item";
      const kindOf = (cell) => cell.dataset.fieldId ? "Field" : "Section";
      const visible = (element) => Boolean(element && element.getBoundingClientRect().width > 0);
      const editable = (cell) => Boolean(cell.dataset.fieldId || cell.dataset.containerId || cell.querySelector(":scope > .print-section, :scope > .print-group"));
      const syncCompactCell = (cell) => {
        const grid = cell.closest("[data-print-layout-grid]");
        // offsetWidth is unscaled: zoom must never change the printed content.
        cell.classList.toggle("is-layout-cell-compact", cell.classList.contains("print-row") && grid.dataset.layoutKind === "field_run" && presentation(grid) === "grid" && cell.offsetWidth < 296);
      };
      const setSpan = (cell, value) => {
        cell.dataset.printSpan = String(value);
        cell.style.setProperty("--print-grid-span", String(value));
        requestAnimationFrame(() => syncCompactCell(cell));
      };
      const setPresentation = (grid, value) => {
        grid.dataset.layoutPresentation = value;
        grid.classList.toggle("print-layout-grid", value === "grid");
        if (value === "grid") grid.style.setProperty("--print-grid-units", units(grid));
        else grid.style.removeProperty("--print-grid-units");
        if (grid.dataset.layoutKind === "block_run") grid.closest("[data-layout-run]")?.classList.toggle("is-layout-run-custom", value === "grid");
        requestAnimationFrame(() => gridCells(grid).forEach(syncCompactCell));
      };
      const updatePlaceholders = (grid) => {
        grid.querySelectorAll(":scope > .print-grid-cell--placeholder, :scope > .print-field-run-placeholder").forEach((cell) => cell.remove());
        if (presentation(grid) !== "grid" || ["container_run", "block_run"].includes(grid.dataset.layoutKind)) return;
        let used = 0;
        gridCells(grid).forEach((cell) => { const span = spanOf(cell); used = used + span > units(grid) ? span : used + span; if (used === units(grid)) used = 0; });
        if (!used) return;
        const remaining = units(grid) - used;
        const fill = grid.dataset.gridMode === "preserve" && remaining % 2 === 0 ? Array(remaining / 2).fill(2) : [remaining];
        fill.forEach((span) => {
          const cell = document.createElement("article");
          cell.className = grid.dataset.layoutKind === "field_run" ? "print-row print-field-run-placeholder" : "print-grid-cell print-grid-cell--placeholder";
          cell.setAttribute("aria-hidden", "true");
          cell.style.setProperty("--print-grid-span", span);
          grid.append(cell);
        });
      };
      const currentPreference = () => {
        const result = { grids: {}, containers: {}, blocks: {} };
        grids.forEach((grid) => {
          const cells = gridCells(grid), order = cells.map(itemId);
          const reordered = cells.some((cell, index) => Number(cell.dataset.originalIndex) !== index);
          const mode = grid.dataset.gridMode || "preserve";
          if (mode === (grid.dataset.defaultMode || "preserve") && !reordered) return;
          const kind = grid.dataset.layoutKind;
          const collection = kind === "container_run" ? "containers" : kind === "block_run" ? "blocks" : "grids";
          const idsKey = kind === "container_run" ? "container_ids" : kind === "block_run" ? "block_ids" : "field_ids";
          result[collection][grid.dataset.gridId] = { [idsKey]: order, mode, spans: Object.fromEntries(cells.map((cell) => [itemId(cell), spanOf(cell)])), order: reordered ? order : [] };
        });
        return result;
      };
      const snapshot = () => grids.map((grid) => ({
        presentation: presentation(grid), mode: grid.dataset.gridMode || "preserve",
        order: gridCells(grid).map(itemId), spans: Object.fromEntries(gridCells(grid).map((cell) => [itemId(cell), spanOf(cell)])),
      }));
      const dirty = () => baseline && (JSON.stringify(snapshot()) !== JSON.stringify(baseline) || Boolean(future?.checked) !== baselineFuture);
      const say = (message, error = false) => { if (status) { status.textContent = message; status.dataset.status = error ? "error" : "success"; } };
      const visualFor = (grid, cell) => {
        if (visible(cell)) return cell;
        const run = grid.closest("[data-layout-run]");
        return Array.from(run?.querySelectorAll(".print-block-run-default [data-layout-source-id]") || []).find((node) => node.dataset.layoutSourceId === itemId(cell) && visible(node)) || null;
      };
      const visualSpan = (grid, cell) => {
        if (presentation(grid) === "grid") return spanOf(cell);
        const width = grid.getBoundingClientRect().width || grid.closest("[data-layout-run]")?.getBoundingClientRect().width || 1;
        return nearestSpan(grid, (visualFor(grid, cell)?.getBoundingClientRect().width || width) / width * units(grid));
      };
      const measurePaper = () => {
        const ruler = document.createElement("div"), style = getComputedStyle(document.body);
        Object.assign(ruler.style, { position: "absolute", visibility: "hidden", width: style.getPropertyValue("--print-page-width"), height: style.getPropertyValue("--print-page-height") });
        document.body.append(ruler);
        const size = { width: ruler.offsetWidth, height: ruler.offsetHeight };
        ruler.remove(); return size;
      };
      const paperSize = editor ? measurePaper() : null;
      const updateOverlay = () => {
        overlayFrame = 0;
        if (!selection) return;
        const paperRect = paper.getBoundingClientRect();
        const paperHeight = paperSize.height * zoom;
        pageEdge.hidden = !editing || paperRect.height <= paperHeight + 2;
        if (!pageEdge.hidden) Object.assign(pageEdge.style, { top: `${paperRect.top + paperHeight}px`, left: `${paperRect.left}px`, width: `${paperRect.width}px` });
        const node = editing && selected ? visualFor(selected.grid, selected.cell) : null;
        selection.hidden = !node || saving;
        selection.style.opacity = gesture?.started && gesture.type === "move" ? "0" : "1";
        if (!node) return;
        const rect = node.getBoundingClientRect();
        Object.assign(selection.style, { left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px` });
        selectionLabel.textContent = `${kindOf(selected.cell)} · ${labelOf(selected.cell)}`;
      };
      const queueOverlay = () => { if (!overlayFrame) overlayFrame = requestAnimationFrame(updateOverlay); };
      const updateControls = () => {
        if (!editor) return;
        undoButton.disabled = saving || historyIndex <= 0;
        redoButton.disabled = saving || historyIndex >= history.length - 1;
        saveButton.disabled = saving || !dirty();
        cancelButton.disabled = saving;
        if (future) future.disabled = saving;
        if (resetButton) resetButton.disabled = saving || !selected;
        widthTools.hidden = !selected;
        if (selected) {
          const span = visualSpan(selected.grid, selected.cell), choices = spans(selected.grid);
          const cells = gridCells(selected.grid), index = cells.indexOf(selected.cell);
          const percent = Math.round(span / units(selected.grid) * 100);
          widthLabel.textContent = `${percent}%`;
          find("[data-layout-narrower]").disabled = saving || span <= choices[0];
          find("[data-layout-wider]").disabled = saving || span >= choices.at(-1);
          find("[data-layout-earlier]").disabled = saving || index <= 0;
          find("[data-layout-later]").disabled = saving || index >= cells.length - 1;
          title.textContent = `${kindOf(selected.cell)}: ${labelOf(selected.cell)}`;
          hint.textContent = "Drag to move within its group. Pull the right handle to resize.";
        } else {
          title.textContent = "Adjust layout";
          hint.textContent = "Select a field or a section on the page.";
        }
        const state = find("[data-layout-dirty]");
        state.textContent = dirty() ? "Unsaved changes" : "No layout changes";
        queueOverlay();
      };
      const select = (next) => { selected = next; updateControls(); };
      const restoreSnapshot = (saved) => {
        saved.forEach((item, index) => {
          const grid = grids[index], cells = new Map(gridCells(grid).map((cell) => [itemId(cell), cell]));
          item.order.forEach((id) => { const cell = cells.get(id); if (cell) grid.append(cell); });
          gridCells(grid).forEach((cell) => setSpan(cell, item.spans[itemId(cell)]));
          grid.dataset.gridMode = item.mode;
          setPresentation(grid, item.presentation);
          updatePlaceholders(grid);
        });
        updateControls(); schedulePrintFitCheck();
      };
      const recordHistory = () => {
        const next = snapshot();
        if (JSON.stringify(history[historyIndex]) !== JSON.stringify(next)) {
          history.splice(historyIndex + 1); history.push(next);
          if (history.length > 50) history.shift();
          historyIndex = history.length - 1;
        }
        updateControls(); schedulePrintFitCheck();
      };
      const undo = () => { if (historyIndex > 0 && !saving && !gesture) { restoreSnapshot(history[--historyIndex]); say("Layout change undone."); } };
      const redo = () => { if (historyIndex < history.length - 1 && !saving && !gesture) { restoreSnapshot(history[++historyIndex]); say("Layout change redone."); } };
      const prepareGrid = (grid) => {
        if (presentation(grid) === "grid") return;
        const available = grid.getBoundingClientRect().width || grid.closest("[data-layout-run]")?.getBoundingClientRect().width || 1;
        const measured = gridCells(grid).map((cell) => [cell, visualFor(grid, cell)?.getBoundingClientRect().width || available]);
        measured.forEach(([cell, width]) => setSpan(cell, nearestSpan(grid, width / available * units(grid))));
        grid.dataset.gridMode = "manual";
        setPresentation(grid, "grid"); updatePlaceholders(grid);
      };
      const targetFrom = (element) => {
        let node = element?.closest("[data-print-grid-cell], [data-layout-source-id]");
        while (node && paper.contains(node)) {
          if (node.hasAttribute("data-print-grid-cell") && editable(node)) return { cell: node, grid: node.closest("[data-print-layout-grid]") };
          let run = node.closest("[data-layout-run]");
          while (run) {
            const grid = run.querySelector(":scope > .print-block-run-grid");
            const cell = grid && gridCells(grid).find((item) => itemId(item) === node.dataset.layoutSourceId);
            if (cell && editable(cell)) return { cell, grid };
            run = run.parentElement?.closest("[data-layout-run]");
          }
          node = node.parentElement?.closest("[data-print-grid-cell], [data-layout-source-id]");
        }
        return null;
      };
      const showGuide = (rect, vertical = false) => {
        guide.hidden = false;
        guide.classList.toggle("is-vertical", vertical);
        Object.assign(guide.style, { left: `${rect.left}px`, top: `${rect.top}px`, width: `${vertical ? 3 : rect.width}px`, height: `${vertical ? rect.height : 3}px` });
      };
      const clearGuide = () => { if (guide) guide.hidden = true; };
      const updateDrop = (x, y) => {
        const move = gesture;
        let cell = document.elementFromPoint(x, y)?.closest("[data-print-grid-cell]");
        while (cell && cell.closest("[data-print-layout-grid]") !== move.grid) cell = cell.parentElement?.closest("[data-print-grid-cell]");
        // Direct children only: a field can never slip into a different section.
        if (!cell || cell === move.cell || cell.closest("[data-print-layout-grid]") !== move.grid) { move.drop = null; clearGuide(); return; }
        const rect = cell.getBoundingClientRect();
        const sameRow = spanOf(move.cell) + spanOf(cell) <= units(move.grid) && Math.abs(y - (rect.top + rect.height / 2)) < Math.min(18, rect.height / 4);
        const after = sameRow ? x > rect.left + rect.width / 2 : y > rect.top + rect.height / 2;
        move.drop = { cell, after };
        showGuide({ left: sameRow && after ? rect.right : rect.left, top: sameRow ? rect.top : after ? rect.bottom : rect.top, width: rect.width, height: rect.height }, sameRow);
      };
      const movePreview = (x, y) => {
        if (!gesture?.preview) return;
        gesture.preview.style.left = `${x + 14}px`; gesture.preview.style.top = `${y + 14}px`;
      };
      const autoScroll = () => {
        if (!gesture?.started || gesture.type !== "move") { scrollFrame = 0; return; }
        const { x, y } = gesture;
        const top = editor.getBoundingClientRect().bottom + 25;
        const delta = y > innerHeight - 50 ? 12 : y < top ? -12 : 0;
        if (delta) { window.scrollBy(0, delta); updateDrop(x, y); }
        if (viewport && viewport.scrollWidth > viewport.clientWidth) {
          const rect = viewport.getBoundingClientRect();
          const previous = viewport.scrollLeft;
          viewport.scrollLeft += x > rect.right - 35 ? 10 : x < rect.left + 35 ? -10 : 0;
          if (viewport.scrollLeft !== previous) updateDrop(x, y);
        }
        scrollFrame = requestAnimationFrame(autoScroll);
      };
      const startGesture = (event, type) => {
        if (!selected || saving || gesture || event.button !== 0 || (type === "move" && gridCells(selected.grid).length < 2)) return;
        event.preventDefault();
        const node = visualFor(selected.grid, selected.cell);
        if (!node) return;
        gesture = { ...selected, type, pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, x: event.clientX, y: event.clientY, width: node.getBoundingClientRect().width, startSpan: visualSpan(selected.grid, selected.cell), before: snapshot(), started: false, drop: null, preview: null };
        selection.setPointerCapture(event.pointerId);
      };
      const finishGesture = (cancel = false) => {
        if (!gesture) return;
        const ended = gesture; gesture = null;
        if (scrollFrame) cancelAnimationFrame(scrollFrame); scrollFrame = 0;
        ended.preview?.remove(); ended.cell.classList.remove("is-layout-cell-moving"); clearGuide();
        document.body.classList.remove("is-layout-moving", "is-layout-resizing");
        if (selection.hasPointerCapture(ended.pointerId)) selection.releasePointerCapture(ended.pointerId);
        if (!ended.started) { queueOverlay(); return; }
        if (cancel || (ended.type === "move" && !ended.drop) || (ended.type === "resize" && spanOf(ended.cell) === ended.startSpan)) { restoreSnapshot(ended.before); return; }
        if (ended.type === "move") {
          ended.grid.insertBefore(ended.cell, ended.drop.after ? ended.drop.cell.nextElementSibling : ended.drop.cell);
          const oldOrder = ended.before[grids.indexOf(ended.grid)].order;
          if (gridCells(ended.grid).every((cell, index) => itemId(cell) === oldOrder[index])) { restoreSnapshot(ended.before); return; }
          updatePlaceholders(ended.grid);
        }
        recordHistory();
        say(ended.type === "move" ? "Item moved. Its group is unchanged." : "Width adjusted. Other items stay aligned.");
      };
      const stepWidth = (direction) => {
        if (!selected || saving || gesture) return;
        const current = visualSpan(selected.grid, selected.cell), choices = spans(selected.grid), index = choices.indexOf(current);
        const next = choices[Math.max(0, Math.min(choices.length - 1, index + direction))];
        if (next === current) return;
        prepareGrid(selected.grid);
        setSpan(selected.cell, next);
        selected.grid.dataset.gridMode = "manual"; updatePlaceholders(selected.grid); recordHistory();
      };
      const stepOrder = (direction) => {
        if (!selected || saving || gesture) return;
        const { grid, cell } = selected, cells = gridCells(grid), index = cells.indexOf(cell), other = cells[index + direction];
        if (!other) return;
        prepareGrid(grid);
        grid.insertBefore(cell, direction < 0 ? other : other.nextElementSibling); updatePlaceholders(grid); recordHistory();
      };
      const confirmDiscard = () => {
        if (!dirty()) return Promise.resolve(true);
        if (discardResolve) return Promise.resolve(false);
        discardDialog.returnValue = "keep";
        discardDialog.showModal();
        return new Promise((resolve) => { discardResolve = resolve; });
      };
      discardDialog?.addEventListener("close", () => { discardResolve?.(discardDialog.returnValue === "discard"); discardResolve = null; });
      const setEditing = (value) => {
        editing = value; editor.hidden = !value;
        document.body.classList.toggle("is-layout-editing", value);
        openButton.disabled = value;
        document.querySelectorAll("[data-print-action], [data-open-print-settings]").forEach((button) => {
          if (value) { temporarilyDisabled.set(button, button.disabled); button.disabled = true; }
          else { button.disabled = temporarilyDisabled.get(button) || false; temporarilyDisabled.delete(button); }
        });
        if (!value) { selected = null; selection.hidden = true; pageEdge.hidden = true; }
      };
      const cancel = () => {
        if (saving) return;
        finishGesture(true); restoreSnapshot(baseline);
        if (future) future.checked = baselineFuture;
        setEditing(false); say(""); openButton.focus({ preventScroll: true });
      };
      const save = async () => {
        if (!editing || saving || gesture || !dirty()) return;
        saving = true; updateControls(); say("Saving layout...");
        try {
          const response = await fetch(document.body.dataset.printLayoutSaveUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
            template_id: document.body.dataset.printTemplateId, text_size: document.body.dataset.printTextSize, paper_size: document.body.dataset.printPaperSize,
            ...activeTextSizes(), layout: currentPreference(), apply_to_future: Boolean(future?.checked),
          }) });
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || "Could not save the layout.");
          baseline = snapshot(); baselineFuture = Boolean(future?.checked);
          if (restoreButton) { restoreButton.hidden = false; restoreButton.disabled = false; }
          setEditing(false); notice.textContent = result.message || "Layout saved."; notice.hidden = false;
          openButton.focus();
        } catch (error) { say(error.message || "Could not save the layout. Your adjustments are still here.", true); }
        finally { saving = false; updateControls(); }
      };
      const setZoom = (value) => {
        zoom = Math.max(.15, Math.min(2, value));
        document.body.classList.add("has-layout-preview-zoom");
        paper.style.setProperty("--layout-preview-zoom", zoom);
        zoomLabel.textContent = `${Math.round(zoom * 100)}%`; queueOverlay();
      };

      if (typeof ResizeObserver !== "undefined") {
        const observer = new ResizeObserver((entries) => { entries.forEach((entry) => syncCompactCell(entry.target)); if (editor) queueOverlay(); });
        grids.forEach((grid) => gridCells(grid).forEach((cell) => observer.observe(cell)));
      }
      if (!editor || !paper) return { currentPreference };
      openButton.addEventListener("click", () => {
        baseline = snapshot(); baselineFuture = Boolean(future?.checked);
        history.splice(0, history.length, baseline); historyIndex = 0; selected = null;
        notice.hidden = true; say(""); setEditing(true); updateControls();
      });
      cancelButton.addEventListener("click", cancel);
      saveButton.addEventListener("click", save);
      undoButton.addEventListener("click", undo); redoButton.addEventListener("click", redo);
      future?.addEventListener("change", updateControls);
      find("[data-layout-narrower]").addEventListener("click", () => stepWidth(-1));
      find("[data-layout-wider]").addEventListener("click", () => stepWidth(1));
      find("[data-layout-earlier]").addEventListener("click", () => stepOrder(-1));
      find("[data-layout-later]").addEventListener("click", () => stepOrder(1));
      find("[data-layout-zoom-out]").addEventListener("click", () => setZoom(zoom - .1));
      find("[data-layout-zoom-in]").addEventListener("click", () => setZoom(zoom + .1));
      find("[data-layout-zoom-reset]").addEventListener("click", () => setZoom(1));
      find("[data-layout-fit]").addEventListener("click", () => {
        window.scrollTo(0, 0);
        viewport.scrollLeft = 0;
        const room = Math.max(200, innerHeight - editor.getBoundingClientRect().bottom - 40);
        setZoom(Math.min((viewport.clientWidth - 20) / paperSize.width, room / paper.offsetHeight, 1));
      });
      resetButton.addEventListener("click", () => {
        if (!selected || saving) return;
        const { grid, cell } = selected, saved = baseline[grids.indexOf(grid)], id = itemId(cell), cells = new Map(gridCells(grid).map((node) => [itemId(node), node]));
        const next = saved.order.slice(saved.order.indexOf(id) + 1).find((key) => cells.has(key));
        grid.insertBefore(cell, cells.get(next) || null); setSpan(cell, saved.spans[id]);
        const same = gridCells(grid).every((node, index) => itemId(node) === saved.order[index] && spanOf(node) === saved.spans[itemId(node)]);
        if (same) { grid.dataset.gridMode = saved.mode; setPresentation(grid, saved.presentation); }
        updatePlaceholders(grid); recordHistory();
      });
      paper.addEventListener("pointerdown", (event) => {
        if (!editing || saving || event.target.closest("button, a")) return;
        select(targetFrom(event.target));
        if (event.pointerType === "mouse") startGesture(event, "move");
      });
      selection.addEventListener("pointerdown", (event) => startGesture(event, event.target.closest("[data-layout-resize-handle]") ? "resize" : "move"));
      selection.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") stepWidth(event.key === "ArrowLeft" ? -1 : 1);
        else stepOrder(event.key === "ArrowUp" ? -1 : 1);
      });
      document.addEventListener("pointermove", (event) => {
        if (!gesture || gesture.pointerId !== event.pointerId) return;
        const current = gesture; current.x = event.clientX; current.y = event.clientY;
        if (!current.started && Math.hypot(event.clientX - current.startX, event.clientY - current.startY) < 5) return;
        if (!current.started) {
          const source = visualFor(current.grid, current.cell), rect = source.getBoundingClientRect();
          if (current.type === "move") {
            const preview = document.createElement("div"); preview.className = "print-layout-drag-preview"; preview.setAttribute("aria-hidden", "true");
            const clone = source.cloneNode(true); clone.querySelectorAll("button").forEach((button) => button.remove());
            preview.style.width = `${Math.min(rect.width, 360)}px`; preview.append(clone); document.body.append(preview); current.preview = preview;
          }
          prepareGrid(current.grid); current.started = true;
          current.cell.classList.toggle("is-layout-cell-moving", current.type === "move");
          document.body.classList.add(current.type === "move" ? "is-layout-moving" : "is-layout-resizing");
          if (current.type === "move") scrollFrame = requestAnimationFrame(autoScroll);
        }
        if (current.type === "move") { movePreview(event.clientX, event.clientY); updateDrop(event.clientX, event.clientY); }
        else {
          const rect = current.grid.getBoundingClientRect(), width = current.width + event.clientX - current.startX;
          const next = nearestSpan(current.grid, width / rect.width * units(current.grid));
          if (next !== spanOf(current.cell)) {
            setSpan(current.cell, next);
            current.grid.dataset.gridMode = "manual"; updatePlaceholders(current.grid); updateControls();
          }
          const cellRect = current.cell.getBoundingClientRect(); showGuide({ left: cellRect.right, top: rect.top, width: 3, height: rect.height }, true);
        }
        queueOverlay();
      });
      document.addEventListener("pointerup", (event) => { if (gesture?.pointerId === event.pointerId) finishGesture(); });
      document.addEventListener("pointercancel", (event) => { if (gesture?.pointerId === event.pointerId) finishGesture(true); });
      selection.addEventListener("lostpointercapture", () => { if (gesture) finishGesture(true); });
      document.addEventListener("keydown", async (event) => {
        if (!editing || saving || event.defaultPrevented || discardDialog.open) return;
        if (event.target instanceof Element && event.target.closest("input, select, textarea")) return;
        const key = event.key.toLowerCase();
        if (key === "escape" && more?.open && !gesture) { more.open = false; return; }
        if (key === "escape") { event.preventDefault(); if (gesture) finishGesture(true); else if (await confirmDiscard()) cancel(); }
        if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
        if (key === "z") { event.preventDefault(); event.shiftKey ? redo() : undo(); }
        else if (key === "y") { event.preventDefault(); redo(); }
        else if (key === "s") { event.preventDefault(); save(); }
        else if (key === "p") { event.preventDefault(); say("Save or cancel your layout changes before printing."); }
      });
      document.addEventListener("click", async (event) => {
        if (more?.open && !more.contains(event.target)) more.open = false;
        const link = event.target.closest("a[href]");
        if (!editing || !link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target === "_blank" || link.hasAttribute("download")) return;
        if (saving) { event.preventDefault(); return; }
        if (!dirty()) return;
        event.preventDefault(); if (await confirmDiscard()) { cancel(); window.location.assign(link.href); }
      });
      find("[data-print-refresh]")?.addEventListener("click", async () => { if (!editing || await confirmDiscard()) { if (editing) cancel(); location.reload(); } });
      restoreButton?.addEventListener("click", async () => {
        if (saving || !window.confirm("Restore the saved form layout? Any unsaved layout adjustments will be discarded.")) return;
        saving = true; updateControls();
        try {
          const response = await fetch(document.body.dataset.printLayoutRestoreUrl, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template_id: document.body.dataset.printTemplateId, paper_size: document.body.dataset.printPaperSize }) });
          const result = await response.json(); if (!response.ok) throw new Error(result.detail || "Could not restore the layout.");
          editing = false; const url = new URL(location.href); url.searchParams.delete("edit_presentation"); location.assign(url);
        } catch (error) { saving = false; updateControls(); say(error.message, true); }
      });
      window.addEventListener("beforeunload", (event) => { if (editing && dirty()) { event.preventDefault(); event.returnValue = ""; } });
      window.addEventListener("beforeprint", () => {
        if (!editing || !baseline || printDraft) return;
        finishGesture(true); printDraft = snapshot(); restoreSnapshot(baseline);
      });
      window.addEventListener("afterprint", () => {
        if (!printDraft) return;
        const draft = printDraft; printDraft = null; restoreSnapshot(draft);
      });
      document.addEventListener("scroll", queueOverlay, true); window.addEventListener("resize", queueOverlay);
      return { currentPreference };
    },
  };
})();
