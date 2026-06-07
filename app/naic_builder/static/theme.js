(() => {
  const storageKey = "naic-theme";
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

  const allToggleButtons = () =>
    Array.from(document.querySelectorAll("[data-theme-toggle]"));

  applyTheme(getActiveTheme());

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

  const mountToggle = () => {
    if (!document.body) {
      return;
    }

    const inlineButtons = document.querySelectorAll("[data-theme-toggle]");
    inlineButtons.forEach(bindToggle);
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
})();
