(() => {
  const appConfirm = async (options) => {
    if (window.NAICApp && typeof window.NAICApp.confirm === "function") {
      return window.NAICApp.confirm(options);
    }

    const fallbackMessage = [options.title, options.message].filter(Boolean).join("\n\n");
    return window.confirm(fallbackMessage || "Continue?");
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
        const confirmed = await appConfirm(confirmOptionsFromElement(element));
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

  const setupHistorySearch = () => {
    document.querySelectorAll("[data-history-search]").forEach((form) => {
      if (form.dataset.historySearchReady === "true") {
        return;
      }
      form.dataset.historySearchReady = "true";

      const input = form.querySelector("[data-history-search-input]");
      const clearButton = form.querySelector("[data-history-search-clear]");
      const summaryEl = document.querySelector("[data-history-summary]");
      const filtersEl = document.querySelector("[data-history-filters]");
      const resultsEl = document.querySelector("[data-history-results]");
      const paginationEl = document.querySelector("[data-history-pagination]");
      if (!input) {
        return;
      }

      let timer = 0;
      let currentRequest = null;
      let lastRequestedUrl = "";

      const buildSearchUrl = () => {
        const url = new URL(form.action || window.location.href, window.location.origin);
        const formData = new FormData(form);
        url.search = "";

        formData.forEach((value, key) => {
          const text = String(value || "").trim();
          if (!text) {
            return;
          }
          if (key === "status" && text === "completed") {
            return;
          }
          url.searchParams.set(key, text);
        });

        return url;
      };

      const updateFromDocument = (html) => {
        const nextDoc = new DOMParser().parseFromString(html, "text/html");
        const nextSummary = nextDoc.querySelector("[data-history-summary]");
        const nextFilters = nextDoc.querySelector("[data-history-filters]");
        const nextResults = nextDoc.querySelector("[data-history-results]");
        const nextPagination = nextDoc.querySelector("[data-history-pagination]");

        if (summaryEl && nextSummary) {
          summaryEl.innerHTML = nextSummary.innerHTML;
        }
        if (filtersEl && nextFilters) {
          filtersEl.innerHTML = nextFilters.innerHTML;
        }
        if (resultsEl && nextResults) {
          resultsEl.innerHTML = nextResults.innerHTML;
        }
        if (paginationEl && nextPagination) {
          paginationEl.innerHTML = nextPagination.innerHTML;
        }

        setupConfirmActions();
      };

      const setLoading = (value) => {
        form.classList.toggle("is-loading", value);
        resultsEl?.classList.toggle("is-loading", value);
      };

      const runSearch = async ({ replaceUrl = true } = {}) => {
        const url = buildSearchUrl();
        const urlText = `${url.pathname}${url.search}`;
        if (urlText === lastRequestedUrl) {
          return;
        }
        lastRequestedUrl = urlText;

        if (currentRequest) {
          currentRequest.abort();
        }

        const request = new AbortController();
        currentRequest = request;
        if (clearButton) {
          clearButton.hidden = !String(input.value || "").trim();
        }
        setLoading(true);

        try {
          const response = await fetch(urlText, {
            headers: { "X-Requested-With": "fetch" },
            signal: request.signal,
          });
          if (!response.ok) {
            throw new Error(`History search failed: ${response.status}`);
          }
          updateFromDocument(await response.text());
          if (replaceUrl) {
            window.history.replaceState({}, "", urlText);
          }
        } catch (error) {
          if (error.name !== "AbortError") {
            console.error(error);
          }
        } finally {
          if (currentRequest === request) {
            setLoading(false);
          }
        }
      };

      input.addEventListener("input", () => {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => {
          runSearch();
        }, String(input.value || "").trim() ? 80 : 40);
      });

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        window.clearTimeout(timer);
        runSearch();
      });

      clearButton?.addEventListener("click", () => {
        input.value = "";
        window.clearTimeout(timer);
        runSearch();
        input.focus();
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

      const confirmLeavingDirtyRecord = () => appConfirm({
        eyebrow: "Unsaved changes",
        title: "Leave without saving?",
        message: "This record has changes that have not been saved yet.",
        cancelLabel: "Keep editing",
        confirmLabel: "Leave anyway",
        destructive: true,
      });

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
            statusEl.textContent = button.dataset.submitStatus || "Saving...";
            statusEl.classList.remove("is-dirty");
          }
        });
      });

      form.addEventListener("submit", () => {
        allowUnload = true;
      });

      window.addEventListener("naic:allow-unload", () => {
        allowUnload = true;
      });

      document.addEventListener("click", async (event) => {
        if (!dirty || allowUnload || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }

        const clickTarget = event.target instanceof Element ? event.target : null;
        const link = clickTarget?.closest("a[href]");
        if (!link || form.contains(link) || (link.target && link.target !== "_self") || link.hasAttribute("download")) {
          return;
        }

        const nextUrl = new URL(link.href, window.location.href);
        const currentUrl = new URL(window.location.href);
        const isSamePageHash = nextUrl.origin === currentUrl.origin
          && nextUrl.pathname === currentUrl.pathname
          && nextUrl.search === currentUrl.search
          && nextUrl.hash
          && nextUrl.hash !== currentUrl.hash;
        if (isSamePageHash) {
          return;
        }

        event.preventDefault();
        if (await confirmLeavingDirtyRecord()) {
          allowUnload = true;
          window.location.assign(link.href);
        }
      }, true);

      document.addEventListener("submit", async (event) => {
        if (!dirty || allowUnload) {
          return;
        }

        const targetForm = event.target;
        if (!(targetForm instanceof HTMLFormElement) || targetForm === form || form.contains(targetForm) || targetForm.matches("[data-confirm]")) {
          return;
        }

        event.preventDefault();
        if (await confirmLeavingDirtyRecord()) {
          allowUnload = true;
          if (event.submitter && event.submitter.form === targetForm) {
            targetForm.requestSubmit(event.submitter);
          } else {
            targetForm.requestSubmit();
          }
        }
      }, true);

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
  setupHistorySearch();
})();
