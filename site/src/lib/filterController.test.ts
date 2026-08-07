import { describe, expect, it } from "vitest";
import {
  buildFilterPath,
  cardIsVisible,
  cardMatchesCategoryAndSearch,
  computeParkCounts,
  countVisibleCards,
  parseFiltersFromSearchParams,
  type CardFilterData,
} from "./filterController";

const sampleCards: CardFilterData[] = [
  { category: "Birds", park: "DENA", searchText: "thrush denali chorus" },
  { category: "Mammals", park: "DENA", searchText: "wolf howling" },
  { category: "Mammals", park: "WRST", searchText: "wolf pack" },
  { category: "Geophony", park: "unknown", searchText: "thunder rain" },
];

const validCategories = new Set(["all", "Birds", "Mammals", "Geophony"]);
const validParks = new Set(["all", "DENA", "WRST"]);

describe("cardMatchesCategoryAndSearch", () => {
  const card = sampleCards[1]!;

  it("matches all categories when category is all", () => {
    expect(cardMatchesCategoryAndSearch(card, "all", "")).toBe(true);
  });

  it("filters by category and search text", () => {
    expect(cardMatchesCategoryAndSearch(card, "Mammals", "wolf")).toBe(true);
    expect(cardMatchesCategoryAndSearch(card, "Birds", "wolf")).toBe(false);
    expect(cardMatchesCategoryAndSearch(card, "Mammals", "bear")).toBe(false);
  });
});

describe("cardIsVisible", () => {
  it("requires category, search, and park to match", () => {
    const card = sampleCards[1]!;
    expect(cardIsVisible(card, "Mammals", "DENA", "wolf")).toBe(true);
    expect(cardIsVisible(card, "Mammals", "WRST", "wolf")).toBe(false);
  });
});

describe("parseFiltersFromSearchParams", () => {
  it("reads valid params from the URL", () => {
    const params = new URLSearchParams("category=Birds&park=DENA&q=thrush");
    expect(parseFiltersFromSearchParams(params, validCategories, validParks)).toEqual({
      category: "Birds",
      park: "DENA",
      search: "thrush",
    });
  });

  it("falls back to defaults for invalid values", () => {
    const params = new URLSearchParams("category=Reptiles&park=NOPE&q=");
    expect(parseFiltersFromSearchParams(params, validCategories, validParks)).toEqual({
      category: "all",
      park: "all",
      search: "",
    });
  });
});

describe("buildFilterPath", () => {
  it("omits default values from the query string", () => {
    expect(buildFilterPath("/alaska_acoustic_highlights/", "all", "all", "")).toBe(
      "/alaska_acoustic_highlights/",
    );
  });

  it("builds a shareable filter URL", () => {
    expect(buildFilterPath("/alaska_acoustic_highlights/", "Birds", "DENA", "wolf")).toBe(
      "/alaska_acoustic_highlights/?category=Birds&park=DENA&q=wolf",
    );
  });

  it("trims search before adding it to the URL", () => {
    expect(buildFilterPath("/", "all", "all", "  wolf  ")).toBe("/?q=wolf");
  });
});

describe("computeParkCounts", () => {
  it("counts parks for the current category and search", () => {
    const { total, counts } = computeParkCounts(sampleCards, "Mammals", "wolf");
    expect(total).toBe(2);
    expect(counts.get("DENA")).toBe(1);
    expect(counts.get("WRST")).toBe(1);
  });

  it("skips unknown parks in the per-park breakdown", () => {
    const { counts } = computeParkCounts(sampleCards, "Geophony", "");
    expect(counts.size).toBe(0);
  });
});

describe("countVisibleCards", () => {
  it("counts cards visible for category, park, and search together", () => {
    expect(countVisibleCards(sampleCards, "all", "all", "")).toBe(4);
    expect(countVisibleCards(sampleCards, "Mammals", "DENA", "wolf")).toBe(1);
    expect(countVisibleCards(sampleCards, "Birds", "DENA", "wolf")).toBe(0);
  });
});
