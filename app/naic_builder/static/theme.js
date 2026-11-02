(() => {
  const storageKey = "naic-theme";
  const contrastStorageKey = "naic-contrast";
  const root = document.documentElement;

  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
  };

  const getStoredTheme = () => {
    try {
      const value = window.localStorage.getItem(storageKey);
      return value === "light" || value === "dark" ? value : null;
    } catch (error) {
      return null;
    }
  };

  const getSystemTheme = () =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

  const getActiveTheme = () => getStoredTheme() || getSystemTheme();

  const getStoredContrast = () => {
    try {
      const value = window.localStorage.getItem(contrastStorageKey);
      return value === "normal" || value === "high" ? value : null;
    } catch (_error) {
      return null;
    }
  };
  const getSystemContrast = () => window.matchMedia("(prefers-contrast: more)").matches ? "high" : "normal";
  const applyContrast = (contrast) => { root.dataset.contrast = contrast; };

  const allToggleButtons = () =>
    Array.from(document.querySelectorAll("[data-theme-toggle]"));

  applyTheme(getActiveTheme());
  applyContrast(getStoredContrast() || getSystemContrast());

  const themeIcon = (theme) => {
    if (theme === "dark") {
      return `
        <svg class="theme-toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M18.25 15.75A7.25 7.25 0 0 1 8.25 5.75a7.5 7.5 0 1 0 10 10Z" />
        </svg>
      `;
    }
    return `
      <svg class="theme-toggle-icon" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="3.25" />
        <path d="M12 3.75v1.5M12 18.75v1.5M5.64 5.64l1.06 1.06M17.3 17.3l1.06 1.06M3.75 12h1.5M18.75 12h1.5M5.64 18.36l1.06-1.06M17.3 6.7l1.06-1.06" />
      </svg>
    `;
  };

  const updateToggleCopy = (button) => {
    const theme = root.dataset.theme === "dark" ? "dark" : "light";
    const next = theme === "dark" ? "light" : "dark";
    button.setAttribute("aria-label", `Switch to ${next} mode`);
    button.setAttribute("title", `Switch to ${next} mode`);
    if (button.classList.contains("shell-theme-toggle--icon")) {
      button.innerHTML = themeIcon(next);
      return;
    }
    if (button.classList.contains("shell-theme-toggle--inline")) {
      button.innerHTML = `
        ${themeIcon(next)}
        <span class="theme-toggle-fab__label">
          <span>${next === "dark" ? "Dark" : "Light"}</span>
        </span>
      `;
      return;
    }
    button.innerHTML = `
      ${themeIcon(next)}
      <span class="theme-toggle-fab__label">
        <span class="theme-toggle-fab__meta">Theme</span>
        <span>${next === "dark" ? "Dark mode" : "Light mode"}</span>
      </span>
    `;
  };

  const refreshToggleCopy = () => {
    allToggleButtons().forEach(updateToggleCopy);
    refreshDisplayCopy();
  };

  const bindToggle = (button) => {
    if (button.dataset.themeToggleBound === "true") {
      updateToggleCopy(button);
      return;
    }

    button.dataset.themeToggleBound = "true";
    button.addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        window.localStorage.setItem(storageKey, next);
      } catch (error) {
        // Ignore storage failures and keep the session theme.
      }
      refreshToggleCopy();
    });

    updateToggleCopy(button);
  };

  const refreshDisplayCopy = () => {
    document.querySelectorAll('[data-display-theme]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.displayTheme === root.dataset.theme));
    });
    document.querySelectorAll('[data-display-contrast]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.displayContrast === root.dataset.contrast));
    });
    document.querySelectorAll('[data-display-toggle]').forEach(button => {
      button.title = `Display: ${root.dataset.theme}, ${root.dataset.contrast} contrast`;
    });
  };

  const bindDisplay = (control) => {
    if (control.dataset.displayReady === 'true') return;
    control.dataset.displayReady = 'true';
    const button = control.querySelector('[data-display-toggle]');
    const panel = control.querySelector('[data-display-panel]');
    const nativePopover = typeof panel.showPopover === 'function';
    if (!nativePopover) panel.removeAttribute('popover');
    const isOpen = () => nativePopover ? panel.matches(':popover-open') : !panel.hidden;
    const position = () => {
      const anchor = button.getBoundingClientRect();
      const box = panel.getBoundingClientRect();
      panel.style.left = `${Math.max(12, Math.min(innerWidth - box.width - 12, anchor.right - box.width))}px`;
      panel.style.top = `${anchor.bottom + box.height + 20 <= innerHeight ? anchor.bottom + 8 : Math.max(12, anchor.top - box.height - 8)}px`;
    };
    const close = (restoreFocus = false) => {
      if (nativePopover && isOpen()) panel.hidePopover();
      panel.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      if (restoreFocus) button.focus();
    };
    button.addEventListener('click', () => {
      if (isOpen()) { close(); return; }
      panel.hidden = false;
      if (nativePopover) panel.showPopover();
      position();
      button.setAttribute('aria-expanded', 'true');
      panel.querySelector('[aria-pressed="true"]')?.focus({preventScroll:true});
    });
    panel.addEventListener('toggle', () => {
      if (!isOpen()) close();
    });
    control.querySelector('[data-display-close]').addEventListener('click', () => close(true));
    control.querySelectorAll('[data-display-theme]').forEach(choice => {
      choice.addEventListener('click', () => {
        applyTheme(choice.dataset.displayTheme);
        try { window.localStorage.setItem(storageKey, root.dataset.theme); } catch (_error) { /* Keep session choice. */ }
        refreshToggleCopy();
      });
    });
    control.querySelectorAll('[data-display-contrast]').forEach(choice => {
      choice.addEventListener('click', () => {
        applyContrast(choice.dataset.displayContrast);
        try { window.localStorage.setItem(contrastStorageKey, root.dataset.contrast); } catch (_error) { /* Keep session choice. */ }
        refreshDisplayCopy();
      });
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && isOpen()) {
        event.preventDefault();
        close(true);
      }
    });
    document.addEventListener('click', event => {
      if (isOpen() && !control.contains(event.target)) close();
    });
    window.addEventListener('resize', () => { if (isOpen()) position(); });
  };

  const mountToggle = () => {
    if (!document.body) {
      return;
    }

    const inlineButtons = document.querySelectorAll("[data-theme-toggle]");
    inlineButtons.forEach(bindToggle);
    document.querySelectorAll('[data-display-control]').forEach(bindDisplay);
    refreshDisplayCopy();
  };

  const syncToSystemIfNeeded = () => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => {
      if (!getStoredTheme()) {
        applyTheme(getSystemTheme());
        refreshToggleCopy();
      }
    };

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", listener);
    } else if (typeof media.addListener === "function") {
      media.addListener(listener);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountToggle, { once: true });
  } else {
    mountToggle();
  }

  syncToSystemIfNeeded();
  const contrastMedia = window.matchMedia('(prefers-contrast: more)');
  const syncContrast = () => {
    if (!getStoredContrast()) {
      applyContrast(getSystemContrast());
      refreshDisplayCopy();
    }
  };
  if (typeof contrastMedia.addEventListener === 'function') contrastMedia.addEventListener('change', syncContrast);
  else if (typeof contrastMedia.addListener === 'function') contrastMedia.addListener(syncContrast);
  window.addEventListener('storage', event => {
    if (event.key === storageKey || event.key === contrastStorageKey || event.key === null) {
      applyTheme(getActiveTheme());
      applyContrast(getStoredContrast() || getSystemContrast());
      refreshToggleCopy();
    }
  });
})();
