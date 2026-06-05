(() => {
  let passwordInputCounter = 0;
  let passwordLabelCounter = 0;

  const ensureInputId = (input) => {
    if (input.id) {
      return input.id;
    }

    passwordInputCounter += 1;
    input.id = `password-input-${passwordInputCounter}`;
    return input.id;
  };

  const setButtonState = (button, input) => {
    const visible = input.type === "text";
    button.textContent = visible ? "Hide" : "Show";
    button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
    button.setAttribute("aria-pressed", visible ? "true" : "false");
    button.title = visible ? "Hide password" : "Show password";
  };

  const preserveInputLabel = (input) => {
    if (input.hasAttribute("aria-label") || input.hasAttribute("aria-labelledby")) {
      return;
    }

    const label = input.closest("label");
    if (!label) {
      return;
    }

    const labelText = Array.from(label.children).find((child) => (
      child instanceof HTMLElement && child.tagName.toLowerCase() === "span"
    ));

    if (!labelText) {
      return;
    }

    if (!labelText.id) {
      passwordLabelCounter += 1;
      labelText.id = `password-label-${passwordLabelCounter}`;
    }

    input.setAttribute("aria-labelledby", labelText.id);
  };

  const enhancePasswordInput = (input) => {
    if (!(input instanceof HTMLInputElement)) {
      return;
    }

    if (input.dataset.passwordToggleEnhanced === "true" || input.type !== "password") {
      return;
    }

    const parent = input.parentNode;
    if (!parent) {
      return;
    }

    input.dataset.passwordToggleEnhanced = "true";
    preserveInputLabel(input);

    const wrapper = document.createElement("div");
    wrapper.className = "password-toggle-field";
    parent.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const button = document.createElement("button");
    button.className = "password-toggle-button";
    button.type = "button";
    button.setAttribute("aria-controls", ensureInputId(input));
    setButtonState(button, input);

    button.addEventListener("click", () => {
      input.type = input.type === "password" ? "text" : "password";
      setButtonState(button, input);
      input.focus({ preventScroll: true });
    });

    wrapper.appendChild(button);
  };

  const enhancePasswordInputs = (root = document) => {
    if (root instanceof HTMLInputElement) {
      enhancePasswordInput(root);
      return;
    }

    if (!(root instanceof Document) && !(root instanceof Element)) {
      return;
    }

    root.querySelectorAll("input[type='password']").forEach(enhancePasswordInput);
  };

  const start = () => {
    enhancePasswordInputs(document);

    if (!document.body || !window.MutationObserver) {
      return;
    }

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          enhancePasswordInputs(node);
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
