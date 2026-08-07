import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clampVolume,
  DEFAULT_VOLUME,
  readStoredVolume,
  updateVolumeAria,
  VOLUME_STORAGE_KEY,
} from "./playerController";

function createVolumeSlider(): HTMLInputElement {
  const attrs = new Map<string, string>();
  return {
    type: "range",
    min: "0",
    max: "100",
    value: "100",
    setAttribute(name: string, value: string) {
      attrs.set(name, value);
    },
    getAttribute(name: string) {
      return attrs.get(name) ?? null;
    },
  } as unknown as HTMLInputElement;
}

describe("clampVolume", () => {
  it("clamps values to 0–100", () => {
    expect(clampVolume(-5)).toBe(0);
    expect(clampVolume(0)).toBe(0);
    expect(clampVolume(50)).toBe(50);
    expect(clampVolume(100)).toBe(100);
    expect(clampVolume(150)).toBe(100);
  });
});

describe("readStoredVolume", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value);
      },
      clear: () => storage.clear(),
    });
  });

  it("returns default when storage is empty or invalid", () => {
    expect(readStoredVolume()).toBe(DEFAULT_VOLUME);

    storage.set(VOLUME_STORAGE_KEY, "not-a-number");
    expect(readStoredVolume()).toBe(DEFAULT_VOLUME);
  });

  it("reads and clamps stored volume", () => {
    storage.set(VOLUME_STORAGE_KEY, "75");
    expect(readStoredVolume()).toBe(75);

    storage.set(VOLUME_STORAGE_KEY, "200");
    expect(readStoredVolume()).toBe(100);
  });
});

describe("updateVolumeAria", () => {
  it("sets percent label and value text for non-zero volume", () => {
    const slider = createVolumeSlider();

    updateVolumeAria(slider, 65);

    expect(slider.getAttribute("aria-valuenow")).toBe("65");
    expect(slider.getAttribute("aria-valuetext")).toBe("65%");
    expect(slider.getAttribute("aria-label")).toBe("Playback volume");
  });

  it("sets muted label and value text at zero volume", () => {
    const slider = createVolumeSlider();

    updateVolumeAria(slider, 0);

    expect(slider.getAttribute("aria-valuenow")).toBe("0");
    expect(slider.getAttribute("aria-valuetext")).toBe("Muted");
    expect(slider.getAttribute("aria-label")).toBe("Playback volume, muted");
  });

  it("clamps out-of-range values", () => {
    const slider = createVolumeSlider();

    updateVolumeAria(slider, -10);
    expect(slider.getAttribute("aria-valuenow")).toBe("0");
    expect(slider.getAttribute("aria-valuetext")).toBe("Muted");

    updateVolumeAria(slider, 120);
    expect(slider.getAttribute("aria-valuenow")).toBe("100");
    expect(slider.getAttribute("aria-valuetext")).toBe("100%");
  });
});
