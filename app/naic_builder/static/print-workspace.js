/* Keep preview magnification separate from the report's printable dimensions. */
(() => {
  "use strict";
  const workspace = document.querySelector(".print-workspace");
  if (!workspace) return;

  const viewport = workspace.querySelector(".print-page-viewport");
  const paper = viewport.querySelector(".print-page");
  const toolbar = workspace.querySelector(".print-command-bar");
  const zoomLabel = workspace.querySelector("[data-preview-zoom-label]");
  const zoomOut = workspace.querySelector("[data-preview-zoom-out]");
  const zoomIn = workspace.querySelector("[data-preview-zoom-in]");
  const fitButton = workspace.querySelector("[data-preview-fit]");
  let zoom = 1;
  let autoFit = true;

  const setZoom = (value) => {
    zoom = Math.max(0.1, Math.min(2, value));
    paper.style.setProperty("--layout-preview-zoom", zoom.toFixed(4));
    zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
    zoomOut.disabled = zoom <= 0.1;
    zoomIn.disabled = zoom >= 2;
    fitButton.setAttribute("aria-pressed", String(autoFit));
  };

  const fitPage = () => {
    const viewportStyle = getComputedStyle(viewport);
    const width = viewport.clientWidth - parseFloat(viewportStyle.paddingLeft) - parseFloat(viewportStyle.paddingRight);
    const height = viewport.clientHeight - parseFloat(viewportStyle.paddingTop) - parseFloat(viewportStyle.paddingBottom);
    const pageHeight = parseFloat(getComputedStyle(paper).minHeight);
    setZoom(Math.min(1, width / paper.offsetWidth, height / pageHeight));
  };

  zoomOut.addEventListener("click", () => { autoFit = false; setZoom(zoom - 0.1); });
  zoomIn.addEventListener("click", () => { autoFit = false; setZoom(zoom + 0.1); });
  zoomLabel.addEventListener("click", () => { autoFit = false; setZoom(1); });
  fitButton.addEventListener("click", () => {
    autoFit = true;
    fitPage();
    viewport.scrollTo(0, 0);
  });

  const observer = new ResizeObserver(() => {
    workspace.style.setProperty("--print-command-height", `${toolbar.offsetHeight}px`);
    if (autoFit) fitPage();
  });
  observer.observe(toolbar);
  observer.observe(viewport);
  fitPage();
})();
