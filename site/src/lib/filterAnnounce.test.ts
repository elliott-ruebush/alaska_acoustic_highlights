import { describe, expect, it } from "vitest";
import { buildFilterAnnouncement, hasActiveFilters } from "./filterAnnounce";

describe("hasActiveFilters", () => {
  it("returns false when all filters are default", () => {
    expect(
      hasActiveFilters({ category: "all", parkCode: "all", parkName: null, search: "" }),
    ).toBe(false);
  });

  it("returns true when category, park, or search is set", () => {
    expect(
      hasActiveFilters({ category: "Birds", parkCode: "all", parkName: null, search: "" }),
    ).toBe(true);
    expect(
      hasActiveFilters({ category: "all", parkCode: "DENA", parkName: "Denali", search: "" }),
    ).toBe(true);
    expect(
      hasActiveFilters({ category: "all", parkCode: "all", parkName: null, search: "wolf" }),
    ).toBe(true);
  });

  it("ignores whitespace-only search", () => {
    expect(
      hasActiveFilters({ category: "all", parkCode: "all", parkName: null, search: "   " }),
    ).toBe(false);
  });
});

describe("buildFilterAnnouncement", () => {
  it("announces only the count when no filters are active", () => {
    expect(
      buildFilterAnnouncement(12, 120, {
        category: "all",
        parkCode: "all",
        parkName: null,
        search: "",
      }),
    ).toBe("Showing 12 of 120 recordings.");
  });

  it("announces zero results", () => {
    expect(
      buildFilterAnnouncement(0, 120, {
        category: "Birds",
        parkCode: "all",
        parkName: null,
        search: "",
      }),
    ).toBe("No recordings match your filters. Category: Birds.");
  });

  it("includes active category, park, and search", () => {
    expect(
      buildFilterAnnouncement(3, 120, {
        category: "Mammals",
        parkCode: "DENA",
        parkName: "Denali",
        search: "wolf",
      }),
    ).toBe(
      "Showing 3 of 120 recordings. Category: Mammals. Park: Denali. Search: wolf.",
    );
  });
});
