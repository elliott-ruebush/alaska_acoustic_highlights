import { describe, expect, it } from "vitest";
import {
  ABOUT_PAGE_CLIP_IDS,
  formatParkLabel,
  getClipById,
  getLocationLabel,
  getLocationLabelSpoken,
  getParkName,
  getSitePhoto,
  getSitePhotoTakenYear,
} from "./catalog";

describe("getClipById", () => {
  it("returns a clip when the id exists", () => {
    const clip = getClipById("denawocr_20150624_202549");
    expect(clip.title).toBe("Fox Sparrow Song With Thunder and Swainson's Thrush");
  });

  it("throws when the id is missing", () => {
    expect(() => getClipById("not-a-real-clip")).toThrow("Unknown clip id: not-a-real-clip");
  });
});

describe("about page clip links", () => {
  it("resolves every featured clip id from the catalog", () => {
    for (const id of ABOUT_PAGE_CLIP_IDS) {
      expect(getClipById(id).id).toBe(id);
    }
  });
});

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

describe("getSitePhotoTakenYear", () => {
  it("extracts the year from an ISO date", () => {
    expect(
      getSitePhotoTakenYear({
        id: "test",
        path: "highlights/site_photos/test.webp",
        site_key: "DENABICR",
        park_code: "DENA",
        site_code: "BICR",
        taken_date: "2013-08-09",
        source_filename: "test.webp",
      }),
    ).toBe("2013");
  });

  it("returns null when taken_date is missing", () => {
    expect(
      getSitePhotoTakenYear({
        id: "test",
        path: "highlights/site_photos/test.webp",
        site_key: "DENABICR",
        park_code: "DENA",
        site_code: "BICR",
        taken_date: null,
        source_filename: "test.webp",
      }),
    ).toBeNull();
  });
});

describe("getSitePhoto", () => {
  it("resolves a photo for clips with site_photo_id", () => {
    const clip = getClipById("denabicr_20130809_020959");
    if (!clip.site_photo_id) return;

    const photo = getSitePhoto(clip);
    expect(photo).not.toBeNull();
    expect(photo?.path).toMatch(/^highlights\/site_photos\/.+\.webp$/);
  });
});
