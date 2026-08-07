export function formatDuration(seconds: number): string {
  const total = Math.round(seconds);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

/** Natural-language duration for screen readers, e.g. "16 seconds" or "1 minute and 30 seconds". */
export function formatDurationSpoken(seconds: number): string {
  const total = Math.round(seconds);
  const mins = Math.floor(total / 60);
  const secs = total % 60;

  if (mins === 0) {
    return secs === 1 ? "1 second" : `${secs} seconds`;
  }
  if (secs === 0) {
    return mins === 1 ? "1 minute" : `${mins} minutes`;
  }

  const minPart = mins === 1 ? "1 minute" : `${mins} minutes`;
  const secPart = secs === 1 ? "1 second" : `${secs} seconds`;
  return `${minPart} and ${secPart}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function categorySlug(category: string): string {
  return category.toLowerCase();
}
