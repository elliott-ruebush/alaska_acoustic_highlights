import {
  buildFilterAnnouncement,
  hasActiveFilters,
  type FilterState,
} from "./filterAnnounce";

export const FILTER_PARAM_CATEGORY = "category";
export const FILTER_PARAM_PARK = "park";
export const FILTER_PARAM_SEARCH = "q";
export const SEARCH_DEBOUNCE_MS = 300;

export type HistoryMode = "push" | "replace" | "none";

export type CardFilterData = {
  category: string;
  park: string;
  searchText: string;
};

export type ParsedFilters = {
  category: string;
  park: string;
  search: string;
};

export type ParkCountResult = {
  total: number;
  counts: Map<string, number>;
};

export function cardMatchesCategoryAndSearch(
  card: CardFilterData,
  category: string,
  query: string,
): boolean {
  return (
    (category === "all" || card.category === category) &&
    (!query || card.searchText.includes(query))
  );
}

export function cardIsVisible(
  card: CardFilterData,
  category: string,
  park: string,
  query: string,
): boolean {
  return (
    cardMatchesCategoryAndSearch(card, category, query) &&
    (park === "all" || card.park === park)
  );
}

export function parseFiltersFromSearchParams(
  params: URLSearchParams,
  validCategories: ReadonlySet<string>,
  validParks: ReadonlySet<string>,
): ParsedFilters {
  const category = params.get(FILTER_PARAM_CATEGORY) ?? "all";
  const park = params.get(FILTER_PARAM_PARK) ?? "all";
  return {
    category: validCategories.has(category) ? category : "all",
    park: validParks.has(park) ? park : "all",
    search: params.get(FILTER_PARAM_SEARCH) ?? "",
  };
}

export function buildFilterPath(
  pathname: string,
  category: string,
  park: string,
  search: string,
): string {
  const params = new URLSearchParams();
  if (category !== "all") params.set(FILTER_PARAM_CATEGORY, category);
  if (park !== "all") params.set(FILTER_PARAM_PARK, park);
  const trimmed = search.trim();
  if (trimmed) params.set(FILTER_PARAM_SEARCH, trimmed);
  const qs = params.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

export function computeParkCounts(
  cards: readonly CardFilterData[],
  category: string,
  query: string,
): ParkCountResult {
  const counts = new Map<string, number>();
  let total = 0;

  for (const card of cards) {
    if (!cardMatchesCategoryAndSearch(card, category, query)) continue;
    total++;
    if (card.park !== "unknown") {
      counts.set(card.park, (counts.get(card.park) ?? 0) + 1);
    }
  }

  return { total, counts };
}

export function countVisibleCards(
  cards: readonly CardFilterData[],
  category: string,
  park: string,
  query: string,
): number {
  return cards.filter((card) => cardIsVisible(card, category, park, query)).length;
}

function readCardData(card: Element): CardFilterData {
  return {
    category: card.getAttribute("data-category") ?? "",
    park: card.getAttribute("data-park") ?? "",
    searchText: card.getAttribute("data-search") ?? "",
  };
}

export function initGalleryFilters(root: Document = document): void {
  const chips = root.querySelectorAll<HTMLButtonElement>(".chip");
  const categoryGroup = root.querySelector<HTMLElement>(".chip-group");
  const parkSelect = root.querySelector<HTMLSelectElement>("#park-filter");
  const searchInput = root.querySelector<HTMLInputElement>("#search-filter");
  const clearFiltersBtn = root.querySelector<HTMLButtonElement>("#clear-filters");
  const cardElements = root.querySelectorAll(".card");
  const emptyState = root.querySelector<HTMLParagraphElement>("#empty-state");
  const filterStatus = root.querySelector<HTMLParagraphElement>("#filter-status");

  if (
    !parkSelect ||
    !searchInput ||
    !clearFiltersBtn ||
    !emptyState ||
    cardElements.length === 0
  ) {
    return;
  }

  const ui = {
    parkSelect,
    searchInput,
    clearFiltersBtn,
    emptyState,
  } satisfies {
    parkSelect: HTMLSelectElement;
    searchInput: HTMLInputElement;
    clearFiltersBtn: HTMLButtonElement;
    emptyState: HTMLParagraphElement;
  };

  const cards = [...cardElements].map((card) => ({
    element: card,
    data: readCardData(card),
  }));
  const totalClips = cards.length;

  const validCategories = new Set(
    [...chips].map((chip) => chip.dataset.category ?? "all"),
  );
  const validParks = new Set(
    [...ui.parkSelect.options].map((option) => option.value),
  );

  let activeCategory = "all";
  let searchDebounce: ReturnType<typeof setTimeout> | undefined;
  let lastAnnouncement = "";

  function getFilterState(): FilterState {
    const selected = ui.parkSelect.selectedOptions[0];
    return {
      category: activeCategory,
      parkCode: ui.parkSelect.value,
      parkName: selected?.dataset.parkName ?? null,
      search: ui.searchInput.value,
    };
  }

  function setChipActiveState(category: string) {
    chips.forEach((chip) => {
      const chipCategory = chip.dataset.category ?? "all";
      const isActive = chipCategory === category;
      chip.dataset.active = isActive ? "true" : "false";
      chip.setAttribute("aria-checked", isActive ? "true" : "false");
      chip.tabIndex = isActive ? 0 : -1;
    });
  }

  function updateClearButton() {
    ui.clearFiltersBtn.hidden = !hasActiveFilters(getFilterState());
  }

  function announceFilterResults(visible: number) {
    if (!filterStatus) return;
    const message = buildFilterAnnouncement(visible, totalClips, getFilterState());
    if (message === lastAnnouncement) return;
    lastAnnouncement = message;
    filterStatus.textContent = message;
  }

  function syncUiFromState(category: string, park: string, search: string) {
    activeCategory = category;
    setChipActiveState(category);
    ui.parkSelect.value = park;
    if (ui.searchInput.value !== search) {
      ui.searchInput.value = search;
    }
    updateClearButton();
  }

  function updateUrl(mode: Exclude<HistoryMode, "none">) {
    const url = buildFilterPath(
      window.location.pathname,
      activeCategory,
      ui.parkSelect.value,
      ui.searchInput.value,
    );
    if (mode === "replace") {
      history.replaceState(null, "", url);
    } else {
      history.pushState(null, "", url);
    }
  }

  function updateParkCounts() {
    const query = ui.searchInput.value.trim().toLowerCase();
    const { total, counts } = computeParkCounts(
      cards.map((card) => card.data),
      activeCategory,
      query,
    );

    [...ui.parkSelect.options].forEach((option) => {
      if (option.value === "all") {
        option.textContent = `All parks (${total})`;
        return;
      }
      const code = option.value;
      const name = option.dataset.parkName ?? code;
      const count = counts.get(code) ?? 0;
      option.textContent = `${name} (${code}) (${count})`;
      option.disabled = count === 0;
    });

    const selected = ui.parkSelect.value;
    if (selected !== "all" && (counts.get(selected) ?? 0) === 0) {
      ui.parkSelect.value = "all";
    }
  }

  function applyFilters(options: { announce?: boolean; updateParkCounts?: boolean } = {}) {
    const { announce = true, updateParkCounts: refreshParkCounts = true } = options;
    const query = ui.searchInput.value.trim().toLowerCase();
    const park = ui.parkSelect.value;

    if (refreshParkCounts) {
      updateParkCounts();
    }

    for (const card of cards) {
      const show = cardIsVisible(card.data, activeCategory, park, query);
      card.element.classList.toggle("is-hidden", !show);
      if (show) {
        card.element.removeAttribute("hidden");
      } else {
        card.element.setAttribute("hidden", "");
      }
    }

    const visible = countVisibleCards(
      cards.map((card) => card.data),
      activeCategory,
      park,
      query,
    );

    ui.emptyState.hidden = visible > 0;
    if (visible === 0 && announce) {
      ui.emptyState.setAttribute("aria-hidden", "true");
    } else if (visible > 0) {
      ui.emptyState.removeAttribute("aria-hidden");
    }
    updateClearButton();

    if (announce) {
      announceFilterResults(visible);
    }

    return visible;
  }

  function selectCategory(
    category: string,
    historyMode: HistoryMode = "push",
    options: { announce?: boolean } = {},
  ) {
    activeCategory = category;
    setChipActiveState(category);
    applyFilters({ announce: options.announce });
    if (historyMode !== "none") {
      updateUrl(historyMode);
    }
  }

  function setFiltersFromUrl(updateHistory: HistoryMode) {
    const { category, park, search } = parseFiltersFromSearchParams(
      new URLSearchParams(window.location.search),
      validCategories,
      validParks,
    );
    syncUiFromState(category, park, search);
    const shouldAnnounce = hasActiveFilters({
      category,
      parkCode: park,
      parkName: ui.parkSelect.selectedOptions[0]?.dataset.parkName ?? null,
      search,
    });
    applyFilters({ announce: shouldAnnounce });
    if (updateHistory !== "none") {
      updateUrl(updateHistory);
    }
  }

  function clearAllFilters() {
    syncUiFromState("all", "all", "");
    lastAnnouncement = "";
    applyFilters();
    updateUrl("push");
    chips[0]?.focus();
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      selectCategory(chip.dataset.category ?? "all");
    });
  });

  categoryGroup?.addEventListener("keydown", (e) => {
    const chipList = [...chips];
    const currentIndex = chipList.findIndex(
      (chip) => chip.getAttribute("aria-checked") === "true",
    );
    if (currentIndex < 0) return;

    let nextIndex = currentIndex;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      nextIndex = (currentIndex + 1) % chipList.length;
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      nextIndex = (currentIndex - 1 + chipList.length) % chipList.length;
    } else if (e.key === "Home") {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === "End") {
      e.preventDefault();
      nextIndex = chipList.length - 1;
    } else if (e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      selectCategory(chipList[currentIndex]!.dataset.category ?? "all");
      return;
    } else {
      return;
    }

    const nextChip = chipList[nextIndex]!;
    selectCategory(nextChip.dataset.category ?? "all", "replace", { announce: false });
    nextChip.focus();
  });

  ui.parkSelect.addEventListener("change", () => {
    applyFilters();
    updateUrl("push");
  });

  ui.searchInput.addEventListener("input", () => {
    applyFilters({ announce: false, updateParkCounts: false });
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      applyFilters();
      updateUrl("replace");
    }, SEARCH_DEBOUNCE_MS);
  });

  ui.clearFiltersBtn.addEventListener("click", clearAllFilters);

  window.addEventListener("popstate", () => {
    setFiltersFromUrl("none");
  });

  setFiltersFromUrl("replace");
}
