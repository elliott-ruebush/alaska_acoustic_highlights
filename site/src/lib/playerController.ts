import WaveSurfer from "wavesurfer.js";
import { formatDuration, formatDurationSpoken } from "./format";
import { handlePlayerKeydown } from "./playerKeyboard";

export const VOLUME_STORAGE_KEY = "soundscapes-volume-v2";
export const DEFAULT_VOLUME = 100;

export function clampVolume(percent: number): number {
  return Math.min(100, Math.max(0, percent));
}

export function updateVolumeAria(
  volumeSlider: HTMLInputElement,
  percent: number,
): void {
  const clamped = clampVolume(percent);
  const muted = clamped === 0;
  volumeSlider.setAttribute("aria-valuenow", String(clamped));
  volumeSlider.setAttribute("aria-valuetext", muted ? "Muted" : `${clamped}%`);
  volumeSlider.setAttribute(
    "aria-label",
    muted ? "Playback volume, muted" : "Playback volume",
  );
}

export function readStoredVolume(): number {
  try {
    const raw = localStorage.getItem(VOLUME_STORAGE_KEY);
    if (raw === null) return DEFAULT_VOLUME;
    const value = Number.parseInt(raw, 10);
    if (Number.isNaN(value)) return DEFAULT_VOLUME;
    return clampVolume(value);
  } catch {
    return DEFAULT_VOLUME;
  }
}

export function initPlayer(el: HTMLElement): void {
  const audioSrc = el.dataset.audioSrc!;
  const fallbackDuration = parseFloat(el.dataset.duration || "0");
  const statusEl = el.querySelector<HTMLElement>(".player-status")!;
  const waveformEl = el.querySelector<HTMLElement>(".waveform")!;
  const frame = el.querySelector<HTMLElement>(".spectrogram-frame")!;
  const cursor = el.querySelector<HTMLElement>(".cursor")!;
  const playBtn = el.querySelector<HTMLButtonElement>(".play-pause")!;
  const seekSlider = el.querySelector<HTMLInputElement>(".seek-slider")!;
  const timeElapsed = el.querySelector<HTMLElement>(".time-elapsed")!;
  const timeTotal = el.querySelector<HTMLElement>(".time-total")!;
  const volumeSlider = el.querySelector<HTMLInputElement>(".volume-slider")!;

  let ws: WaveSurfer | null = null;
  let loadPromise: Promise<WaveSurfer> | null = null;
  let isLoaded = false;
  let pendingPlay = false;
  let storedVolume = readStoredVolume();
  let preMuteVolume = storedVolume;
  let isScrubbing = false;
  let lastAnnouncedSeek = -1;

  function getDuration(): number {
    return ws?.getDuration() || fallbackDuration;
  }

  function getCurrentTime(): number {
    return ws?.getCurrentTime() ?? 0;
  }

  function announce(message: string) {
    statusEl.textContent = message;
  }

  function setPlayState(playing: boolean) {
    playBtn.textContent = playing ? "Pause" : "Play";
    playBtn.setAttribute("aria-label", playing ? "Pause" : "Play");
  }

  function updateTimeDisplay() {
    const duration = getDuration();
    const current = Math.min(duration, Math.max(0, getCurrentTime()));
    const elapsed = formatDuration(current);
    const total = formatDuration(duration);

    timeElapsed.textContent = elapsed;
    timeTotal.textContent = total;

    if (!isScrubbing) {
      seekSlider.value = String(current);
      // Avoid updating slider ARIA during playback — some screen readers re-announce it.
      if (!ws?.isPlaying()) {
        seekSlider.setAttribute("aria-valuenow", String(Math.round(current)));
        seekSlider.setAttribute("aria-valuetext", `${elapsed} of ${total}`);
      }
    }
  }

  function updateCursor() {
    const duration = getDuration();
    const pct = duration ? (getCurrentTime() / duration) * 100 : 0;
    cursor.style.left = `${Math.min(100, Math.max(0, pct))}%`;
    updateTimeDisplay();
  }

  function applyVolume(percent: number) {
    const clamped = clampVolume(percent);
    if (clamped > 0) {
      storedVolume = clamped;
      preMuteVolume = clamped;
    }
    volumeSlider.value = String(clamped);
    updateVolumeAria(volumeSlider, clamped);
    if (!ws) return;
    ws.setVolume(clamped / 100);
    if (clamped === 0) {
      ws.setMuted(true);
    } else if (ws.getMuted()) {
      ws.setMuted(false);
    }
  }

  function bindWaveSurferEvents(
    instance: WaveSurfer,
    onReady: () => void,
    onError: () => void,
  ) {
    instance.on("audioprocess", updateCursor);
    instance.on("seeking", updateCursor);
    instance.on("timeupdate", updateCursor);
    instance.on("finish", () => {
      updateCursor();
      setPlayState(false);
      announce("Finished");
    });
    instance.on("play", () => {
      setPlayState(true);
      statusEl.textContent = "";
    });
    instance.on("pause", () => {
      setPlayState(false);
      updateTimeDisplay();
      announce("Paused");
    });
    instance.on("ready", () => {
      const duration = getDuration();
      seekSlider.max = String(duration);
      seekSlider.setAttribute("aria-valuemax", String(Math.round(duration)));
      timeTotal.textContent = formatDuration(duration);
      playBtn.disabled = false;
      seekSlider.disabled = false;
      el.classList.remove("player--idle");
      statusEl.textContent = "";
      updateTimeDisplay();
      if (pendingPlay) {
        pendingPlay = false;
        void instance.play();
      }
      onReady();
    });
    instance.on("error", () => {
      pendingPlay = false;
      playBtn.disabled = false;
      seekSlider.disabled = true;
      announce("Unable to load audio");
      onError();
    });
  }

  function ensureLoaded(): Promise<WaveSurfer> {
    if (ws) return Promise.resolve(ws);
    if (loadPromise) return loadPromise;

    loadPromise = new Promise<WaveSurfer>((resolve, reject) => {
      announce("Loading audio…");
      playBtn.disabled = true;

      const instance = WaveSurfer.create({
        container: waveformEl,
        url: audioSrc,
        height: 48,
        cursorWidth: 0,
        waveColor: "#8a5a35",
        progressColor: "#1b3a2b",
        interact: false,
      });

      ws = instance;
      bindWaveSurferEvents(
        instance,
        () => {
          isLoaded = true;
          resolve(instance);
        },
        () => {
          loadPromise = null;
          ws = null;
          reject(new Error("audio load failed"));
        },
      );
      applyVolume(storedVolume);
    }).catch((err) => {
      loadPromise = null;
      throw err;
    });

    return loadPromise!;
  }

  async function seekToTime(seconds: number, announceSeek = true) {
    if (!isLoaded) {
      await ensureLoaded();
    }
    if (!ws) return;

    const duration = getDuration();
    const clamped = Math.min(duration, Math.max(0, seconds));
    ws.setTime(clamped);
    updateCursor();

    if (announceSeek && !ws.isPlaying()) {
      const rounded = Math.round(clamped);
      if (rounded !== lastAnnouncedSeek) {
        lastAnnouncedSeek = rounded;
        announce(`Seek to ${formatDurationSpoken(clamped)}`);
      }
    }
  }

  async function togglePlayPause() {
    if (!isLoaded) {
      pendingPlay = true;
      try {
        await ensureLoaded();
      } catch {
        pendingPlay = false;
      }
      return;
    }
    ws?.playPause();
  }

  function toggleMute() {
    if (!ws) return;
    const currentPercent = Number.parseInt(volumeSlider.value, 10);
    if (ws.getMuted() || currentPercent === 0) {
      applyVolume(preMuteVolume);
    } else {
      preMuteVolume = currentPercent;
      applyVolume(0);
    }
  }

  applyVolume(storedVolume);
  el.classList.add("player--idle");
  seekSlider.disabled = true;

  volumeSlider.addEventListener("input", () => {
    const percent = Number.parseInt(volumeSlider.value, 10);
    applyVolume(percent);
    try {
      localStorage.setItem(VOLUME_STORAGE_KEY, String(percent));
    } catch {
      // ignore private browsing / storage errors
    }
  });

  seekSlider.addEventListener("pointerdown", () => {
    isScrubbing = true;
  });
  seekSlider.addEventListener("pointerup", () => {
    isScrubbing = false;
  });
  seekSlider.addEventListener("change", () => {
    isScrubbing = false;
  });
  seekSlider.addEventListener("input", () => {
    void seekToTime(Number.parseFloat(seekSlider.value), true);
  });

  playBtn.addEventListener("click", () => {
    void togglePlayPause();
  });

  frame.addEventListener("click", (e) => {
    const rect = frame.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    void seekToTime(pct * getDuration()).then(() => {
      if (ws && !ws.isPlaying()) void ws.play();
    });
  });

  const keyActions = {
    togglePlayPause: () => {
      void togglePlayPause();
    },
    seekBy: (deltaSec: number) => {
      void seekToTime(getCurrentTime() + deltaSec);
    },
    seekToStart: () => {
      void seekToTime(0);
    },
    seekToEnd: () => {
      void seekToTime(getDuration());
    },
    toggleMute,
  };

  document.addEventListener("keydown", (e) => {
    handlePlayerKeydown(e, el, keyActions);
  });
}
