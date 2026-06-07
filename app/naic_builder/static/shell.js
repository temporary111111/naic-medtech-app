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

  let modalResolver = null;
  let modalReturnFocus = null;

  const openClass = "shell-drawer-open";

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

  decisionCancelers.forEach((button) => {
    button.addEventListener("click", () => closeDecisionModal(false));
  });

  decisionConfirm?.addEventListener("click", () => closeDecisionModal(true));

  window.NAICApp = {
    ...(window.NAICApp || {}),
    confirm: openDecisionModal,
  };

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
