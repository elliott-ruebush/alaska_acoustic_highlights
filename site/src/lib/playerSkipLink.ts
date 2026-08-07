/** Focus target id for clip-page skip links (matches SpectrogramPlayer). */
export const PLAYER_SKIP_TARGET_ID = "audio-player";

/**
 * When the skip link is activated, move keyboard focus into the player region so
 * documented shortcuts (Space, arrows, Home/End, M) work immediately.
 */
export function bindPlayerSkipLink(playerEl: HTMLElement): void {
  if (playerEl.id !== PLAYER_SKIP_TARGET_ID) return;

  const focusPlayer = () => {
    playerEl.focus({ preventScroll: false });
  };

  const skipLink = document.querySelector<HTMLAnchorElement>(
    `a.skip-link[href="#${PLAYER_SKIP_TARGET_ID}"]`,
  );

  skipLink?.addEventListener("click", (event) => {
    event.preventDefault();
    window.location.hash = PLAYER_SKIP_TARGET_ID;
    focusPlayer();
  });

  const focusFromHash = () => {
    if (window.location.hash === `#${PLAYER_SKIP_TARGET_ID}`) {
      focusPlayer();
    }
  };

  focusFromHash();
  window.addEventListener("hashchange", focusFromHash);
}
