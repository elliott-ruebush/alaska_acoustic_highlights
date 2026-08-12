export function initSitePhotoDialogs(root: Document = document): void {
  root.querySelectorAll("[data-site-photo-open]").forEach((button) => {
    const dialogId = button.getAttribute("data-site-photo-open");
    if (!dialogId) return;
    const dialog = root.getElementById(dialogId);
    if (!(dialog instanceof HTMLDialogElement)) return;

    button.addEventListener("click", () => dialog.showModal());
    dialog.addEventListener("close", () => {
      if (button instanceof HTMLElement) button.focus();
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });
}
