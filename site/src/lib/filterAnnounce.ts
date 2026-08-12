export type FilterState = {
  category: string;
  parkCode: string;
  parkName: string | null;
  search: string;
};

export function hasActiveFilters(state: FilterState): boolean {
  return (
    state.category !== "all" ||
    state.parkCode !== "all" ||
    state.search.trim() !== ""
  );
}

export function buildFilterAnnouncement(
  visible: number,
  total: number,
  state: FilterState,
): string {
  const countMessage =
    visible === 0
      ? "No recordings match your filters."
      : `Showing ${visible} of ${total} recordings.`;

  const parts: string[] = [];
  if (state.category !== "all") parts.push(`Category: ${state.category}`);
  if (state.parkCode !== "all" && state.parkName) {
    parts.push(`Park: ${state.parkName}`);
  }
  const query = state.search.trim();
  if (query) parts.push(`Search: ${query}`);

  if (parts.length === 0) return countMessage;
  return `${countMessage} ${parts.join(". ")}.`;
}
