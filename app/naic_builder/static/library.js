const searchEl = document.getElementById("librarySearch");
const clearSearchEl = document.getElementById("libraryClearSearch");
const searchStatusEl = document.getElementById("librarySearchStatus");
const libraryRootEl = document.querySelector("[data-library-root]");
const rootNodes = [...(libraryRootEl?.children || [])].filter((node) => node.dataset?.nodeKind);
const searchableNodes = [...document.querySelectorAll("[data-node-kind]")];
const quickJumpEl = document.querySelector(".library-quick-jump");
const jumpLinks = [...document.querySelectorAll("[data-jump-link]")];
const emptyStateEl = document.getElementById("emptySearchState");
const emptyClearEls = [...document.querySelectorAll("[data-clear-library-search]")];

function childNodesOf(node) {
  const childrenWrap = node.querySelector(":scope > .tree-node-body > .tree-children");
  return [...(childrenWrap?.children || [])].filter((child) => child.dataset?.nodeKind);
}

function filterNode(node, query) {
  const searchText = String(node.dataset.searchText || "");
  const ownMatch = !query || searchText.includes(query);
  const childNodes = childNodesOf(node);
  let childVisible = false;

  childNodes.forEach((child) => {
    if (filterNode(child, query)) {
      childVisible = true;
    }
  });

  const visible = ownMatch || childVisible;
  node.classList.toggle("hidden", !visible);

  if (node instanceof HTMLDetailsElement) {
    const defaultOpen = String(node.dataset.defaultOpen || "") === "true";
    node.open = query ? visible : defaultOpen;
  }

  return visible;
}

function applyLibraryFilter() {
  const query = String(searchEl?.value || "").trim().toLowerCase();
  let visibleRootCount = 0;

  rootNodes.forEach((node) => {
    if (filterNode(node, query)) {
      visibleRootCount += 1;
    }
  });

  jumpLinks.forEach((link) => {
    const nodeId = String(link.dataset.jumpLink || "");
    const related = rootNodes.find((node) => String(node.dataset.nodeId || "") === nodeId);
    link.classList.toggle("hidden", !related || related.classList.contains("hidden"));
  });

  const visibleNodes = searchableNodes.filter((node) => !node.classList.contains("hidden"));
  const visibleForms = visibleNodes.filter((node) => node.dataset.nodeKind === "form").length;
  const visibleFolders = visibleNodes.filter((node) => node.dataset.nodeKind === "container").length;
  const totalCount = Number(searchStatusEl?.dataset.totalCount || searchableNodes.length);
  const formCount = Number(searchStatusEl?.dataset.formCount || 0);
  const folderCount = Number(searchStatusEl?.dataset.folderCount || 0);

  if (searchStatusEl) {
    searchStatusEl.textContent = query
      ? `${visibleForms} forms - ${visibleFolders} folders shown`
      : `${formCount} forms - ${folderCount} folders`;
    searchStatusEl.hidden = totalCount <= 0;
  }

  if (clearSearchEl) {
    clearSearchEl.hidden = !query;
  }

  if (quickJumpEl) {
    quickJumpEl.hidden = visibleRootCount <= 0;
  }

  emptyStateEl?.classList.toggle("hidden", !query || visibleRootCount > 0);
}

function clearLibrarySearch() {
  if (!searchEl) {
    return;
  }

  searchEl.value = "";
  applyLibraryFilter();
  searchEl.focus();
}

if (searchEl) {
  searchEl.addEventListener("input", applyLibraryFilter);
}

clearSearchEl?.addEventListener("click", clearLibrarySearch);
emptyClearEls.forEach((button) => {
  button.addEventListener("click", clearLibrarySearch);
});

jumpLinks.forEach((link) => {
  link.addEventListener("click", () => {
    const nodeId = String(link.dataset.jumpLink || "");
    const related = rootNodes.find((node) => String(node.dataset.nodeId || "") === nodeId);
    if (related instanceof HTMLDetailsElement) {
      related.open = true;
    }
  });
});

applyLibraryFilter();
