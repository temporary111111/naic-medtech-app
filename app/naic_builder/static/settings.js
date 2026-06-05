(() => {
  const copyText = async (value) => {
    const text = String(value || "");
    if (!text) {
      return false;
    }
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
        // Fall back to the selection-based copy path below.
      }
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch {
      copied = false;
    }
    textarea.remove();
    return copied;
  };

  const copyButtons = Array.from(document.querySelectorAll("[data-copy-value]"));
  copyButtons.forEach((button) => {
    const defaultLabel = button.textContent || "Copy link";
    button.addEventListener("click", async () => {
      const copied = await copyText(button.dataset.copyValue);
      button.textContent = copied ? "Copied" : "Copy failed";
      window.setTimeout(() => {
        button.textContent = defaultLabel;
      }, 1400);
    });
  });

  const userSearch = document.getElementById("userSearch");
  const userCards = Array.from(document.querySelectorAll("[data-user-card]"));
  const filterButtons = Array.from(document.querySelectorAll("[data-user-filter]"));
  const emptyState = document.querySelector("[data-user-empty]");
  if (!userCards.length) {
    return;
  }

  let activeStatus = "all";

  const applyFilters = () => {
    const query = String(userSearch?.value || "").trim().toLowerCase();
    let visibleCount = 0;

    userCards.forEach((card) => {
      const status = String(card.dataset.userStatus || "");
      const searchText = String(card.dataset.userSearch || "");
      const statusMatch = activeStatus === "all" || status === activeStatus;
      const queryMatch = !query || searchText.includes(query);
      const isVisible = statusMatch && queryMatch;
      card.hidden = !isVisible;
      if (isVisible) {
        visibleCount += 1;
      }
    });

    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  };

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeStatus = String(button.dataset.userFilter || "all");
      filterButtons.forEach((item) => item.classList.toggle("is-active", item === button));
      applyFilters();
    });
  });

  userSearch?.addEventListener("input", applyFilters);
  applyFilters();
})();
