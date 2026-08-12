import { describe, expect, it } from "vitest";
import { formatDuration, formatDurationSpoken, formatFileSize } from "./format";

describe("formatDuration", () => {
  it("formats seconds as m:ss", () => {
    expect(formatDuration(16)).toBe("0:16");
    expect(formatDuration(90)).toBe("1:30");
  });
});

describe("formatDurationSpoken", () => {
  it("uses seconds only under one minute", () => {
    expect(formatDurationSpoken(1)).toBe("1 second");
    expect(formatDurationSpoken(16)).toBe("16 seconds");
  });

  it("uses minutes only when there are no remaining seconds", () => {
    expect(formatDurationSpoken(60)).toBe("1 minute");
    expect(formatDurationSpoken(120)).toBe("2 minutes");
  });

  it("combines minutes and seconds", () => {
    expect(formatDurationSpoken(90)).toBe("1 minute and 30 seconds");
    expect(formatDurationSpoken(61)).toBe("1 minute and 1 second");
  });
});

describe("formatFileSize", () => {
  it("formats bytes", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(1023)).toBe("1023 B");
  });

  it("formats kilobytes with one decimal", () => {
    expect(formatFileSize(1024)).toBe("1.0 KB");
    expect(formatFileSize(1536)).toBe("1.5 KB");
  });

  it("formats megabytes with one decimal", () => {
    expect(formatFileSize(1024 * 1024)).toBe("1.0 MB");
    expect(formatFileSize(2.5 * 1024 * 1024)).toBe("2.5 MB");
  });
});
