(() => {
  const setupConfirmActions = () => {
    document.querySelectorAll("[data-confirm]").forEach((element) => {
      if (element.dataset.confirmReady === "true") {
        return;
      }
      element.dataset.confirmReady = "true";
      element.addEventListener("submit", (event) => {
        const message = String(element.dataset.confirm || "Continue?");
        if (!window.confirm(message)) {
          event.preventDefault();
        }
      });
    });
  };

  const setupAutoSubmitSearch = () => {
    document.querySelectorAll("[data-auto-submit-search]").forEach((form) => {
      if (form.dataset.autoSubmitReady === "true") {
        return;
      }
      form.dataset.autoSubmitReady = "true";

      const input = form.querySelector('input[type="search"]');
      if (!input) {
        return;
      }

      let timer = 0;
      let lastSubmitted = String(input.value || "").trim();

      input.addEventListener("input", () => {
        const nextValue = String(input.value || "").trim();
        window.clearTimeout(timer);
        if (nextValue === lastSubmitted) {
          return;
        }
        timer = window.setTimeout(() => {
          const currentValue = String(input.value || "").trim();
          if (currentValue === lastSubmitted) {
            return;
          }
          lastSubmitted = currentValue;
          form.requestSubmit();
        }, currentValue ? 420 : 180);
      });
    });
  };

  const setupDirtyGuards = () => {
    const guardedForms = document.querySelectorAll("[data-dirty-guard]");
    if (!guardedForms.length) {
      return;
    }

    guardedForms.forEach((form) => {
      const statusEl = form.querySelector("[data-dirty-state]");
      let dirty = false;
      let allowUnload = false;

      const setDirty = (value) => {
        dirty = value;
        if (!statusEl) {
          return;
        }
        statusEl.textContent = dirty ? "Unsaved changes." : "All changes saved.";
        statusEl.classList.toggle("is-dirty", dirty);
      };

      const markDirty = () => {
        if (!dirty) {
          setDirty(true);
        }
      };

      form.addEventListener("input", markDirty);
      form.addEventListener("change", markDirty);

      form.addEventListener("keydown", (event) => {
        const key = String(event.key || "").toLowerCase();
        const isSaveShortcut = (event.ctrlKey || event.metaKey) && key === "s";
        if (!isSaveShortcut) {
          return;
        }

        const saveButton = form.querySelector("[data-save-draft]");
        if (!saveButton) {
          return;
        }

        event.preventDefault();
        allowUnload = true;
        if (statusEl) {
          statusEl.textContent = "Saving...";
          statusEl.classList.remove("is-dirty");
        }
        saveButton.click();
      });

      form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((button) => {
        button.addEventListener("click", () => {
          allowUnload = true;
          if (statusEl) {
            statusEl.textContent = "Saving...";
            statusEl.classList.remove("is-dirty");
          }
        });
      });

      form.addEventListener("submit", () => {
        allowUnload = true;
      });

      window.addEventListener("beforeunload", (event) => {
        if (!dirty || allowUnload) {
          return;
        }
        event.preventDefault();
        event.returnValue = "";
      });
    });
  };

  const isRequiredFieldEmpty = (field) => {
    const hasExistingImage = Boolean(field.querySelector(".entry-image-preview"));
    const fileInput = field.querySelector('input[type="file"]');
    if (fileInput) {
      return !hasExistingImage && !fileInput.files?.length;
    }

    const control = field.querySelector("input, select, textarea");
    if (!control) {
      return false;
    }

    return String(control.value || "").trim() === "";
  };

  const setupRequiredFieldAttention = () => {
    const errorBanner = document.querySelector(".error-banner");
    if (!errorBanner) {
      return;
    }

    const requiredFields = Array.from(document.querySelectorAll("[data-required-field]"));
    const firstMissingField = requiredFields.find(isRequiredFieldEmpty);
    if (!firstMissingField) {
      return;
    }

    firstMissingField.classList.add("entry-field--attention");
    firstMissingField.scrollIntoView({ behavior: "smooth", block: "center" });

    const focusTarget = firstMissingField.querySelector("input, select, textarea");
    window.setTimeout(() => {
      focusTarget?.focus({ preventScroll: true });
    }, 220);
  };

  const setupRecordFormPickers = (root = document) => {
    root.querySelectorAll("[data-record-form-picker]").forEach((picker) => {
      if (picker.dataset.recordFormPickerReady === "true") {
        return;
      }
      picker.dataset.recordFormPickerReady = "true";

      const formSearch = picker.querySelector("[data-record-form-filter]");
      const formOptions = Array.from(picker.querySelectorAll("[data-record-start-option]"));
      const formEmpty = picker.querySelector("[data-record-form-empty]");

      if (!formSearch || !formOptions.length) {
        return;
      }

      const filterForms = () => {
        const query = String(formSearch.value || "").trim().toLowerCase();
        let visibleCount = 0;

        formOptions.forEach((option) => {
          const searchText = String(option.dataset.searchText || "");
          const isVisible = !query || searchText.includes(query);
          option.hidden = !isVisible;
          if (isVisible) {
            visibleCount += 1;
          }
        });

        if (formEmpty) {
          formEmpty.hidden = visibleCount !== 0;
        }
      };

      formSearch.addEventListener("input", filterForms);
      filterForms();
    });
  };

  const setupRecordStartModal = () => {
    const modal = document.querySelector("[data-record-start-modal]");
    if (!modal) {
      return;
    }

    const formSearch = modal.querySelector("[data-record-form-filter]");
    const dialog = modal.querySelector("[data-record-start-dialog]");

    const openModal = () => {
      modal.hidden = false;
      modal.setAttribute("aria-hidden", "false");
      document.body.classList.add("record-start-open");
      window.requestAnimationFrame(() => {
        formSearch?.focus();
      });
    };

    const closeModal = () => {
      modal.hidden = true;
      modal.setAttribute("aria-hidden", "true");
      document.body.classList.remove("record-start-open");
    };

    document.querySelectorAll("[data-record-start-trigger]").forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        openModal();
      });
    });

    modal.querySelectorAll("[data-record-start-close]").forEach((button) => {
      button.addEventListener("click", () => {
        closeModal();
      });
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) {
        closeModal();
      }
    });

    dialog?.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    if (modal.dataset.startOpen === "true") {
      openModal();
    }
  };

  setupDirtyGuards();
  setupRequiredFieldAttention();
  setupRecordFormPickers();
  setupRecordStartModal();
  setupConfirmActions();
  setupAutoSubmitSearch();
})();
