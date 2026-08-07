import { describe, expect, it } from "vitest";
import {
  formatParkLabel,
  getLocationLabel,
  getLocationLabelSpoken,
  getParkName,
} from "./catalog";

describe("getParkName", () => {
  it("returns the full park name for known codes", () => {
    expect(getParkName("DENA")).toBe("Denali");
    expect(getParkName("GAAR")).toBe("Gates of the Arctic");
    expect(getParkName("LACL")).toBe("Lake Clark");
  });

  it("returns the code unchanged when unknown", () => {
    expect(getParkName("UNKNOWN")).toBe("UNKNOWN");
  });
});

describe("formatParkLabel", () => {
  it("combines park name and code", () => {
    expect(formatParkLabel("DENA")).toBe("Denali (DENA)");
    expect(formatParkLabel("WRST")).toBe("Wrangell-St. Elias (WRST)");
  });
});

describe("getLocationLabel", () => {
  it("joins park and site with a middle dot", () => {
    expect(
      getLocationLabel({
        park_code: "DENA",
        site_code: "BICR",
        site_name: "Birch Creek",
      }),
    ).toBe("Denali · Birch Creek");
  });

  it("falls back to site code when site name is missing", () => {
    expect(
      getLocationLabel({
        park_code: "KATM",
        site_code: "JOJO",
        site_name: null,
      }),
    ).toBe("Katmai · JOJO");
  });

  it("returns unknown location when park and site are missing", () => {
    expect(
      getLocationLabel({
        park_code: null,
        site_code: null,
        site_name: null,
      }),
    ).toBe("Unknown location");
  });
});

describe("getLocationLabelSpoken", () => {
  it("uses a dash between park and site for screen readers", () => {
    expect(
      getLocationLabelSpoken({
        park_code: "DENA",
        site_code: "BICR",
        site_name: "Birch Creek",
      }),
    ).toBe("Denali - Birch Creek");
  });

  it("returns park or site alone when only one is present", () => {
    expect(
      getLocationLabelSpoken({
        park_code: "GLBA",
        site_code: null,
        site_name: null,
      }),
    ).toBe("Glacier Bay");
    expect(
      getLocationLabelSpoken({
        park_code: null,
        site_code: "HANM",
        site_name: null,
      }),
    ).toBe("HANM");
  });

  it("returns unknown location when nothing is available", () => {
    expect(
      getLocationLabelSpoken({
        park_code: null,
        site_code: null,
        site_name: null,
      }),
    ).toBe("Unknown location");
  });
});
