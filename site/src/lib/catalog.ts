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
  spectrogram_lowfreq_path: string | null;
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

export function getClipById(id: string): Clip | undefined {
  return getAllClips().find((clip) => clip.id === id);
}

export function getCategories(): { name: string; slug: string; count: number }[] {
  const clips = getAllClips();
  const counts = new Map<string, number>();
  for (const clip of clips) {
    counts.set(clip.category, (counts.get(clip.category) ?? 0) + 1);
  }
  return CATEGORY_ORDER.filter((name) => counts.has(name)).map((name) => ({
    name,
    slug: name.toLowerCase(),
    count: counts.get(name) ?? 0,
  }));
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
