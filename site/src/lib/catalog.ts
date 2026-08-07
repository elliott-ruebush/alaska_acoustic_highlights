import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export interface Clip {
  id: string;
  title: string;
  category: "Birds" | "Mammals" | "Geophony" | "Insects" | "General";
  category_folder: string;
  park_code: string | null;
  site_code: string | null;
  recorded_date: string | null;
  recorded_time: string | null;
  description: string;
  audio_path: string;
  spectrogram_path: string;
  duration_sec: number;
  sample_rate: number;
  format: string;
  file_size_bytes: number;
  artist: string;
  species_common: string | null;
  species_scientific: string | null;
  xc_quality: number | null;
  site_photo_path: string | null;
  site_photo_year: string | null;
  site_name: string | null;
}

const CATEGORY_ORDER = ["Birds", "Mammals", "Geophony", "Insects", "General"] as const;

const PARK_NAMES: Record<string, string> = {
  DENA: "Denali",
  GAAR: "Gates of the Arctic",
  GLBA: "Glacier Bay",
  KATM: "Katmai",
  LACL: "Lake Clark",
  WRST: "Wrangell-St. Elias",
};

export function getParkName(code: string): string {
  return PARK_NAMES[code] ?? code;
}

export function getParkUrl(parkCode: string): string {
  return `https://www.nps.gov/${parkCode.toLowerCase()}`;
}

export function getSiteName(clip: Pick<Clip, "site_code" | "site_name">): string | null {
  if (clip.site_name) return clip.site_name;
  return clip.site_code;
}

function formatWithCode(label: string, code: string | null): string {
  if (!code || label === code) return label;
  return `${label} (${code})`;
}

export function formatParkLabel(parkCode: string): string {
  return formatWithCode(getParkName(parkCode), parkCode);
}

export function formatSiteLabel(clip: Pick<Clip, "site_code" | "site_name">): string | null {
  const site = getSiteName(clip);
  if (!site) return null;
  return formatWithCode(site, clip.site_code);
}

export function getLocationLabel(clip: Pick<Clip, "park_code" | "site_code" | "site_name">): string {
  const park = clip.park_code ? getParkName(clip.park_code) : null;
  const site = getSiteName(clip);
  return [park, site].filter(Boolean).join(" · ") || "Unknown location";
}

/** Natural-language location for screen readers, e.g. "Denali - Birch Creek". */
export function getLocationLabelSpoken(
  clip: Pick<Clip, "park_code" | "site_code" | "site_name">,
): string {
  const park = clip.park_code ? getParkName(clip.park_code) : null;
  const site = getSiteName(clip);
  if (park && site) return `${park} - ${site}`;
  if (park) return park;
  if (site) return site;
  return "Unknown location";
}

export function getLocationLabelDetailed(
  clip: Pick<Clip, "park_code" | "site_code" | "site_name">,
): string {
  const park = clip.park_code ? formatParkLabel(clip.park_code) : null;
  const site = formatSiteLabel(clip);
  return [park, site].filter(Boolean).join(" · ") || "Unknown location";
}

function resolveCatalogPath(): string {
  let dir = path.dirname(fileURLToPath(import.meta.url));
  while (true) {
    const candidate = path.join(dir, "data", "catalog", "highlights.json");
    if (existsSync(candidate)) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) {
      throw new Error("Could not find data/catalog/highlights.json");
    }
    dir = parent;
  }
}

function loadCatalog(): Clip[] {
  const raw = readFileSync(resolveCatalogPath(), "utf-8");
  return JSON.parse(raw) as Clip[];
}

let cached: Clip[] | null = null;

export function getAllClips(): Clip[] {
  if (!cached) cached = loadCatalog();
  return cached;
}

export function getCategories(): { name: string; count: number }[] {
  const clips = getAllClips();
  const counts = new Map<string, number>();
  for (const clip of clips) {
    counts.set(clip.category, (counts.get(clip.category) ?? 0) + 1);
  }
  return CATEGORY_ORDER.filter((name) => counts.has(name)).map((name) => ({
    name,
    count: counts.get(name) ?? 0,
  }));
}

export function buildClipSearchText(clip: Clip): string {
  return [
    clip.title,
    clip.description,
    clip.park_code,
    clip.site_code,
    clip.site_name,
    clip.park_code && getParkName(clip.park_code),
    clip.category,
    clip.id,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function getParks(): { code: string; name: string; count: number }[] {
  const clips = getAllClips();
  const counts = new Map<string, number>();
  for (const clip of clips) {
    if (!clip.park_code) continue;
    counts.set(clip.park_code, (counts.get(clip.park_code) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([code, count]) => ({ code, name: getParkName(code), count }))
    .sort((a, b) => b.count - a.count || a.code.localeCompare(b.code));
}
