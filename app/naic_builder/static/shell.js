(() => {
  const body = document.body;
  if (!body) {
    return;
  }

  const drawer = document.querySelector("[data-shell-drawer]");
  const scrim = document.querySelector("[data-shell-drawer-scrim]");
  const toggles = Array.from(document.querySelectorAll("[data-shell-drawer-toggle]"));
  const closers = Array.from(document.querySelectorAll("[data-shell-drawer-close]"));
  const appFrame = document.querySelector("[data-app-frame]");
  const modalLayer = document.querySelector("[data-app-modal-layer]");
  const decisionModal = document.querySelector("[data-app-decision-modal]");
  const decisionEyebrow = document.getElementById("appDecisionEyebrow");
  const decisionTitle = document.getElementById("appDecisionTitle");
  const decisionMessage = document.getElementById("appDecisionMessage");
  const decisionConfirm = document.querySelector("[data-app-modal-confirm]");
  const decisionCancelers = Array.from(document.querySelectorAll("[data-app-modal-cancel]"));
  const zoomOutput = document.querySelector("[data-app-zoom-output]");
  const zoomInput = document.querySelector("[data-app-zoom-input]");
  const zoomDecrease = document.querySelector("[data-app-zoom-decrease]");
  const zoomIncrease = document.querySelector("[data-app-zoom-increase]");
  const zoomReset = document.querySelector("[data-app-zoom-reset]");

  let modalResolver = null;
  let modalReturnFocus = null;

  const openClass = "shell-drawer-open";
  const zoomStorageKey = "naic.appZoomPercent";
  const minZoom = 50;
  const maxZoom = 200;
  const zoomStep = 5;

  const clampZoom = (value) => {
    const numeric = Number.parseInt(String(value), 10);
    if (!Number.isFinite(numeric)) {
      return 100;
    }
    return Math.min(maxZoom, Math.max(minZoom, Math.round(numeric / zoomStep) * zoomStep));
  };

  const storedZoom = () => {
    try {
      return clampZoom(window.localStorage.getItem(zoomStorageKey) || "100");
    } catch (_error) {
      return 100;
    }
  };

  const persistZoom = (value) => {
    try {
      if (value === 100) {
        window.localStorage.removeItem(zoomStorageKey);
      } else {
        window.localStorage.setItem(zoomStorageKey, String(value));
      }
    } catch (_error) {
      // Local storage can be unavailable in restricted browser modes.
    }
  };

  const applyZoom = (value, { persist = true } = {}) => {
    const zoom = clampZoom(value);
    body.style.setProperty("--app-zoom", String(zoom / 100));
    body.dataset.appZoom = String(zoom);
    if (zoomOutput) {
      zoomOutput.textContent = `${zoom}%`;
    }
    if (zoomInput) {
      zoomInput.value = String(zoom);
    }
    if (zoomDecrease) {
      zoomDecrease.disabled = zoom <= minZoom;
    }
    if (zoomIncrease) {
      zoomIncrease.disabled = zoom >= maxZoom;
    }
    if (persist) {
      persistZoom(zoom);
    }
    return zoom;
  };

  const changeZoomBy = (delta) => {
    const current = clampZoom(body.dataset.appZoom || zoomInput?.value || "100");
    applyZoom(current + delta);
  };

  const syncState = () => {
    if (!drawer) {
      return;
    }

    const isOpen = body.classList.contains(openClass);

    drawer.hidden = !isOpen;
    drawer.toggleAttribute("inert", !isOpen);
    drawer.setAttribute("aria-hidden", isOpen ? "false" : "true");

    if (scrim) {
      scrim.hidden = !isOpen;
    }

    toggles.forEach((button) => {
      button.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  };

  const openDrawer = () => {
    body.classList.add(openClass);
    syncState();
  };

  const closeDrawer = () => {
    body.classList.remove(openClass);
    syncState();
  };

  if (drawer && toggles.length) {
    toggles.forEach((button) => {
      button.addEventListener("click", () => {
        if (body.classList.contains(openClass)) {
          closeDrawer();
        } else {
          openDrawer();
        }
      });
    });

    closers.forEach((button) => {
      button.addEventListener("click", closeDrawer);
    });
  }

  const closeDecisionModal = (value = false) => {
    if (!modalLayer || !decisionModal || !modalResolver) {
      return;
    }

    modalLayer.hidden = true;
    decisionModal.setAttribute("aria-hidden", "true");
    body.classList.remove("app-modal-open");
    appFrame?.toggleAttribute("inert", false);

    const resolve = modalResolver;
    const returnFocus = modalReturnFocus;
    modalResolver = null;
    modalReturnFocus = null;

    resolve(Boolean(value));

    if (returnFocus && typeof returnFocus.focus === "function") {
      window.queueMicrotask(() => returnFocus.focus());
    }
  };

  const focusableSelector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  const trapDecisionFocus = (event) => {
    if (event.key !== "Tab" || !decisionModal || decisionModal.getAttribute("aria-hidden") === "true") {
      return;
    }

    const focusable = Array.from(decisionModal.querySelectorAll(focusableSelector)).filter((element) => {
      return element instanceof HTMLElement && element.offsetParent !== null;
    });

    if (!focusable.length) {
      event.preventDefault();
      decisionModal.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const openDecisionModal = ({
    eyebrow = "Please confirm",
    title = "Continue?",
    message = "Confirm this action before continuing.",
    cancelLabel = "Cancel",
    confirmLabel = "Continue",
    destructive = false,
  } = {}) => {
    if (!modalLayer || !decisionModal || !decisionConfirm) {
      const fallbackMessage = [title, message].filter(Boolean).join("\n\n");
      return Promise.resolve(window.confirm(fallbackMessage || "Continue?"));
    }

    if (modalResolver) {
      closeDecisionModal(false);
    }

    closeDrawer();
    modalReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (decisionEyebrow) {
      decisionEyebrow.textContent = eyebrow;
    }
    if (decisionTitle) {
      decisionTitle.textContent = title;
    }
    if (decisionMessage) {
      decisionMessage.textContent = message;
    }
    decisionCancelers.forEach((button) => {
      button.textContent = button.classList.contains("app-modal-scrim") ? "" : cancelLabel;
    });
    decisionConfirm.textContent = confirmLabel;
    decisionConfirm.classList.toggle("is-destructive", Boolean(destructive));

    modalLayer.hidden = false;
    decisionModal.setAttribute("aria-hidden", "false");
    body.classList.add("app-modal-open");
    appFrame?.toggleAttribute("inert", true);

    return new Promise((resolve) => {
      modalResolver = resolve;
      window.queueMicrotask(() => {
        const firstFocus = destructive
          ? decisionModal.querySelector("[data-app-modal-cancel]:not(.app-modal-scrim)")
          : decisionConfirm;
        if (firstFocus && typeof firstFocus.focus === "function") {
          firstFocus.focus();
        } else {
          decisionModal.focus();
        }
      });
    });
  };

  const confirmOptionsFromElement = (element) => {
    const tone = String(element.dataset.confirmTone || "").toLowerCase();
    return {
      eyebrow: element.dataset.confirmEyebrow || "Please confirm",
      title: element.dataset.confirmTitle || "Continue?",
      message: element.dataset.confirm || "Confirm this action before continuing.",
      cancelLabel: element.dataset.confirmCancelLabel || "Cancel",
      confirmLabel: element.dataset.confirmConfirmLabel || "Continue",
      destructive: tone === "danger" || tone === "destructive",
    };
  };

  const setupConfirmActions = () => {
    document.querySelectorAll("[data-confirm]").forEach((element) => {
      if (element.dataset.confirmReady === "true") {
        return;
      }
      element.dataset.confirmReady = "true";

      element.addEventListener("submit", async (event) => {
        if (element.dataset.confirmSubmitting === "true") {
          element.dataset.confirmSubmitting = "false";
          return;
        }

        event.preventDefault();
        const confirmed = await openDecisionModal(confirmOptionsFromElement(element));
        if (!confirmed) {
          return;
        }

        element.dataset.confirmSubmitting = "true";
        window.dispatchEvent(new CustomEvent("naic:allow-unload"));
        if (event.submitter && event.submitter.form === element) {
          element.requestSubmit(event.submitter);
        } else {
          element.requestSubmit();
        }
      });
    });
  };

  decisionCancelers.forEach((button) => {
    button.addEventListener("click", () => closeDecisionModal(false));
  });

  decisionConfirm?.addEventListener("click", () => closeDecisionModal(true));

  window.NAICApp = {
    ...(window.NAICApp || {}),
    confirm: openDecisionModal,
    setZoom: applyZoom,
    resetZoom: () => applyZoom(100),
  };

  applyZoom(storedZoom(), { persist: false });

  zoomDecrease?.addEventListener("click", () => changeZoomBy(-zoomStep));
  zoomIncrease?.addEventListener("click", () => changeZoomBy(zoomStep));
  zoomReset?.addEventListener("click", () => applyZoom(100));
  zoomInput?.addEventListener("change", () => applyZoom(zoomInput.value));
  zoomInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applyZoom(zoomInput.value);
      zoomInput.blur();
    }
  });

  setupConfirmActions();

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modalResolver) {
      closeDecisionModal(false);
      return;
    }

    trapDecisionFocus(event);

    if (event.key === "Escape" && body.classList.contains(openClass)) {
      closeDrawer();
    }
  });

  syncState();
})();
