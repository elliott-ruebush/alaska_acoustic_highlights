export const SEEK_STEP_SEC = 5;
export const SEEK_STEP_LARGE_SEC = 30;

export function isFormField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    !!target.isContentEditable
  );
}
/** Buttons and links handle Space/Enter natively — don't double-toggle play/pause. */
function isNativeActivationTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLButtonElement || target instanceof HTMLAnchorElement;
}

function isRangeInput(target: EventTarget | null): boolean {
  return target instanceof HTMLInputElement && target.type === "range";
}

export type PlayerKeyActions = {
  togglePlayPause: () => void;
  seekBy: (deltaSec: number) => void;
  seekToStart: () => void;
  seekToEnd: () => void;
  toggleMute: () => void;
};

/**
 * Handle keyboard shortcuts for the audio player (YouTube-style).
 * K toggles play/pause page-wide (except form fields).
 * Space, arrows, Home/End, and M require focus inside the player.
 */
export function handlePlayerKeydown(
  e: KeyboardEvent,
  playerEl: HTMLElement,
  actions: PlayerKeyActions,
): boolean {
  if (isFormField(e.target)) return false;

  const inPlayer = playerEl.contains(document.activeElement);
  const key = e.key;

  if (key === "k" || key === "K") {
    e.preventDefault();
    actions.togglePlayPause();
    return true;
  }

  if (!inPlayer) return false;

  if (key === " " || key === "Spacebar") {
    if (isNativeActivationTarget(e.target) || isRangeInput(e.target)) return false;
    e.preventDefault();
    actions.togglePlayPause();
    return true;
  }

  if (key === "Enter") {
    if (isNativeActivationTarget(e.target) || isRangeInput(e.target)) return false;
    e.preventDefault();
    actions.togglePlayPause();
    return true;
  }

  if (key === "ArrowLeft" || key === "ArrowRight") {
    if (isRangeInput(e.target)) return false;
    e.preventDefault();
    const step = e.shiftKey ? SEEK_STEP_LARGE_SEC : SEEK_STEP_SEC;
    actions.seekBy(key === "ArrowLeft" ? -step : step);
    return true;
  }

  if (key === "Home") {
    e.preventDefault();
    actions.seekToStart();
    return true;
  }

  if (key === "End") {
    e.preventDefault();
    actions.seekToEnd();
    return true;
  }

  if (key === "m" || key === "M") {
    e.preventDefault();
    actions.toggleMute();
    return true;
  }

  return false;
}
