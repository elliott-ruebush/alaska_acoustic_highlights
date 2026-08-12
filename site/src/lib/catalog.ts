import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { formatDurationSpoken } from "./format";

export interface SitePhoto {
  id: string;
  path: string;
  site_key: string;
  park_code: string;
  site_code: string;
  taken_date: string | null;
  source_filename: string;
}

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
  spectrogram_thumb_path: string;
  duration_sec: number;
  sample_rate: number;
  format: string;
  file_size_bytes: number;
  artist: string;
  species_common: string | null;
  species_scientific: string | null;
  xc_quality: number | null;
  site_photo_id: string | null;
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

export function getCardLinkDescription(
  clip: Pick<Clip, "category" | "park_code" | "site_code" | "site_name" | "duration_sec">,
): string {
  return `${clip.category}. Location: ${getLocationLabelSpoken(clip)}. Duration: ${formatDurationSpoken(clip.duration_sec)}.`;
}

function resolveCatalogDir(): string {
  let dir = path.dirname(fileURLToPath(import.meta.url));
  while (true) {
    const catalogDir = path.join(dir, "data", "catalog");
    if (existsSync(path.join(catalogDir, "highlights.json"))) return catalogDir;
    const parent = path.dirname(dir);
    if (parent === dir) {
      throw new Error("Could not find data/catalog/highlights.json");
    }
    dir = parent;
  }
}

function loadCatalog(): Clip[] {
  const raw = readFileSync(path.join(resolveCatalogDir(), "highlights.json"), "utf-8");
  return JSON.parse(raw) as Clip[];
}

function loadSitePhotos(): SitePhoto[] {
  const sitePhotosPath = path.join(resolveCatalogDir(), "site_photos.json");
  if (!existsSync(sitePhotosPath)) {
    throw new Error("Could not find data/catalog/site_photos.json");
  }
  const raw = readFileSync(sitePhotosPath, "utf-8");
  return JSON.parse(raw) as SitePhoto[];
}

let cached: Clip[] | null = null;
let sitePhotosCached: Map<string, SitePhoto> | null = null;

export function getAllClips(): Clip[] {
  if (!cached) cached = loadCatalog();
  return cached;
}

function getSitePhotoMap(): Map<string, SitePhoto> {
  if (!sitePhotosCached) {
    sitePhotosCached = new Map(loadSitePhotos().map((photo) => [photo.id, photo]));
  }
  return sitePhotosCached;
}

export function getSitePhotoById(id: string): SitePhoto | null {
  return getSitePhotoMap().get(id) ?? null;
}

export function getSitePhoto(clip: Pick<Clip, "site_photo_id">): SitePhoto | null {
  if (!clip.site_photo_id) return null;
  return getSitePhotoById(clip.site_photo_id);
}

/** Year extracted from ISO `taken_date` (YYYY-MM-DD) for display. */
export function getSitePhotoTakenYear(photo: SitePhoto): string | null {
  if (!photo.taken_date || photo.taken_date.length < 4) return null;
  return photo.taken_date.slice(0, 4);
}

export function getClipById(id: string): Clip {
  const clip = getAllClips().find((entry) => entry.id === id);
  if (!clip) {
    throw new Error(`Unknown clip id: ${id}`);
  }
  return clip;
}

/** Clips linked from the About page — kept in sync for catalog validation tests. */
export const ABOUT_PAGE_CLIP_IDS = [
  "denawocr_20150624_202549",
  "denamoos_20180814_105458",
] as const;

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
