import { beforeEach, describe, expect, it, vi } from "vitest";
import { handlePlayerKeydown, isFormField, type PlayerKeyActions } from "./playerKeyboard";

function installDomMocks() {
  class HTMLElement {
    tagName = "DIV";
    isContentEditable = false;
  }
  class HTMLInputElement extends HTMLElement {
    type = "";
  }
  class HTMLButtonElement extends HTMLElement {
    tagName = "BUTTON";
  }
  class HTMLAnchorElement extends HTMLElement {
    tagName = "A";
  }
  class HTMLTextAreaElement extends HTMLElement {
    tagName = "TEXTAREA";
  }
  class HTMLSelectElement extends HTMLElement {
    tagName = "SELECT";
  }

  vi.stubGlobal("HTMLElement", HTMLElement);
  vi.stubGlobal("HTMLInputElement", HTMLInputElement);
  vi.stubGlobal("HTMLButtonElement", HTMLButtonElement);
  vi.stubGlobal("HTMLAnchorElement", HTMLAnchorElement);
  vi.stubGlobal("HTMLTextAreaElement", HTMLTextAreaElement);
  vi.stubGlobal("HTMLSelectElement", HTMLSelectElement);

  return {
    HTMLElement,
    HTMLInputElement,
    HTMLButtonElement,
    HTMLAnchorElement,
  };
}

function createKeyEvent(
  key: string,
  target: EventTarget | null,
  options: { shiftKey?: boolean } = {},
): KeyboardEvent {
  return {
    key,
    target,
    shiftKey: options.shiftKey ?? false,
    preventDefault: vi.fn(),
  } as unknown as KeyboardEvent;
}

function createElement<T extends HTMLElement>(
  Class: new () => T,
  props: Partial<T> = {},
): T {
  const el = Object.create(Class.prototype) as T;
  Object.assign(el, { isContentEditable: false }, props);
  return el;
}

function createPlayerEl(options: { focused?: HTMLElement | null; inPlayer?: boolean } = {}) {
  const focused = options.focused ?? null;
  const inPlayer = options.inPlayer ?? false;
  const playerEl = {
    contains(el: unknown) {
      return inPlayer && el === focused;
    },
  } as unknown as HTMLElement;

  vi.stubGlobal("document", {
    activeElement: focused,
  });

  return playerEl;
}

describe("isFormField", () => {
  beforeEach(() => {
    installDomMocks();
  });

  it("returns false for non-elements", () => {
    expect(isFormField(null)).toBe(false);
    expect(isFormField({})).toBe(false);
  });

  it("detects form field elements", () => {
    const { HTMLInputElement, HTMLElement } = installDomMocks();
    const input = createElement(HTMLInputElement, { tagName: "INPUT" });
    const textarea = createElement(HTMLElement, { tagName: "TEXTAREA" });
    const select = createElement(HTMLElement, { tagName: "SELECT" });
    const editable = createElement(HTMLElement, { isContentEditable: true });

    expect(isFormField(input)).toBe(true);
    expect(isFormField(textarea)).toBe(true);
    expect(isFormField(select)).toBe(true);
    expect(isFormField(editable)).toBe(true);
  });

  it("returns false for non-form elements", () => {
    const { HTMLElement } = installDomMocks();
    const div = createElement(HTMLElement, { tagName: "DIV", isContentEditable: false });
    expect(isFormField(div)).toBe(false);
  });
});

describe("handlePlayerKeydown", () => {
  let dom: ReturnType<typeof installDomMocks>;
  let actions: PlayerKeyActions;

  beforeEach(() => {
    dom = installDomMocks();
    actions = {
      togglePlayPause: vi.fn(),
      seekBy: vi.fn(),
      seekToStart: vi.fn(),
      seekToEnd: vi.fn(),
      toggleMute: vi.fn(),
    };
  });

  it("toggles play on K page-wide outside form fields", () => {
    const div = Object.create(dom.HTMLElement.prototype);
    const playerEl = createPlayerEl({ focused: div, inPlayer: false });

    const handled = handlePlayerKeydown(createKeyEvent("k", div), playerEl, actions);

    expect(handled).toBe(true);
    expect(actions.togglePlayPause).toHaveBeenCalledOnce();
  });

  it("ignores K when focus is on a form field", () => {
    const input = createElement(dom.HTMLInputElement, { tagName: "INPUT" });
    const playerEl = createPlayerEl({ focused: input, inPlayer: true });

    const handled = handlePlayerKeydown(createKeyEvent("K", input), playerEl, actions);

    expect(handled).toBe(false);
    expect(actions.togglePlayPause).not.toHaveBeenCalled();
  });

  it("toggles play on Space when focus is inside the player", () => {
    const div = Object.create(dom.HTMLElement.prototype);
    const playerEl = createPlayerEl({ focused: div, inPlayer: true });
    const event = createKeyEvent(" ", div);

    const handled = handlePlayerKeydown(event, playerEl, actions);

    expect(handled).toBe(true);
    expect(event.preventDefault).toHaveBeenCalled();
    expect(actions.togglePlayPause).toHaveBeenCalledOnce();
  });

  it("does not toggle play on Space when target is a button or link", () => {
    const button = Object.create(dom.HTMLButtonElement.prototype);
    const link = Object.create(dom.HTMLAnchorElement.prototype);
    const playerEl = createPlayerEl({ focused: button, inPlayer: true });

    expect(handlePlayerKeydown(createKeyEvent(" ", button), playerEl, actions)).toBe(false);
    expect(handlePlayerKeydown(createKeyEvent(" ", link), playerEl, actions)).toBe(false);
    expect(actions.togglePlayPause).not.toHaveBeenCalled();
  });

  it("does not toggle play on Space or Enter when target is a range input", () => {
    const range = createElement(dom.HTMLInputElement, { tagName: "INPUT", type: "range" });
    const playerEl = createPlayerEl({ focused: range, inPlayer: true });

    expect(handlePlayerKeydown(createKeyEvent(" ", range), playerEl, actions)).toBe(false);
    expect(handlePlayerKeydown(createKeyEvent("Enter", range), playerEl, actions)).toBe(false);
    expect(actions.togglePlayPause).not.toHaveBeenCalled();
  });

  it("toggles play on Enter inside the player when not on button/link", () => {
    const div = Object.create(dom.HTMLElement.prototype);
    const playerEl = createPlayerEl({ focused: div, inPlayer: true });
    const event = createKeyEvent("Enter", div);

    const handled = handlePlayerKeydown(event, playerEl, actions);

    expect(handled).toBe(true);
    expect(event.preventDefault).toHaveBeenCalled();
    expect(actions.togglePlayPause).toHaveBeenCalledOnce();
  });

  it("does not seek with arrow keys when focus is on a range input", () => {
    const range = createElement(dom.HTMLInputElement, { tagName: "INPUT", type: "range" });
    const playerEl = createPlayerEl({ focused: range, inPlayer: true });

    expect(handlePlayerKeydown(createKeyEvent("ArrowLeft", range), playerEl, actions)).toBe(
      false,
    );
    expect(handlePlayerKeydown(createKeyEvent("ArrowRight", range), playerEl, actions)).toBe(
      false,
    );
    expect(actions.seekBy).not.toHaveBeenCalled();
  });

  it("seeks with arrow keys inside the player", () => {
    const div = Object.create(dom.HTMLElement.prototype);
    const playerEl = createPlayerEl({ focused: div, inPlayer: true });

    handlePlayerKeydown(createKeyEvent("ArrowLeft", div), playerEl, actions);
    handlePlayerKeydown(createKeyEvent("ArrowRight", div, { shiftKey: true }), playerEl, actions);

    expect(actions.seekBy).toHaveBeenNthCalledWith(1, -5);
    expect(actions.seekBy).toHaveBeenNthCalledWith(2, 30);
  });

  it("handles Home, End, and M only when focus is inside the player", () => {
    const outside = Object.create(dom.HTMLElement.prototype);
    const inside = Object.create(dom.HTMLElement.prototype);
    const playerEl = {
      contains(el: unknown) {
        return el === inside;
      },
    } as unknown as HTMLElement;

    vi.stubGlobal("document", { activeElement: outside });
    expect(handlePlayerKeydown(createKeyEvent("Home", outside), playerEl, actions)).toBe(false);
    expect(handlePlayerKeydown(createKeyEvent("End", outside), playerEl, actions)).toBe(false);
    expect(handlePlayerKeydown(createKeyEvent("m", outside), playerEl, actions)).toBe(false);

    vi.stubGlobal("document", { activeElement: inside });
    handlePlayerKeydown(createKeyEvent("Home", inside), playerEl, actions);
    handlePlayerKeydown(createKeyEvent("End", inside), playerEl, actions);
    handlePlayerKeydown(createKeyEvent("M", inside), playerEl, actions);

    expect(actions.seekToStart).toHaveBeenCalledOnce();
    expect(actions.seekToEnd).toHaveBeenCalledOnce();
    expect(actions.toggleMute).toHaveBeenCalledOnce();
  });

  it("ignores player shortcuts when focus is outside the player", () => {
    const outside = Object.create(dom.HTMLElement.prototype);
    const playerEl = createPlayerEl({ focused: outside, inPlayer: false });

    expect(handlePlayerKeydown(createKeyEvent(" ", outside), playerEl, actions)).toBe(false);
    expect(handlePlayerKeydown(createKeyEvent("ArrowLeft", outside), playerEl, actions)).toBe(
      false,
    );
    expect(actions.togglePlayPause).not.toHaveBeenCalled();
    expect(actions.seekBy).not.toHaveBeenCalled();
  });
});
