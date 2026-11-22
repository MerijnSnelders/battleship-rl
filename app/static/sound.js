// Game sounds: recorded files from /static/sounds when they load, otherwise a sound made with
// the Web Audio API, so the game never goes silent because a file is missing or fails.

const STORAGE_KEY = "battleship-rl:muted";
const FADE = 0.35;

/**
 * Every recorded sound and how to play it. `start` skips leading silence, `max` cuts a long
 * tail with a fade (so the AI's quick shots do not pile up) and `gain` evens out loudness.
 */
const FILES = {
  miss: { start: 0.1, max: 1.6, gain: 1.0 },
  hit: { start: 0.05, max: 1.8, gain: 0.75 },
  sunk: { start: 0, max: null, gain: 0.75 },
  win: { start: 0, max: null, gain: 1.5 },
  lose: { start: 0.3, max: null, gain: 1.0 },
};

let context = null;
let noise = null;
let muted = readMuted();
const buffers = {}; // decoded sounds by name, filled in once the context exists

// Download the files right away (no user gesture needed); decode them once audio is allowed.
const downloads = Object.fromEntries(
  Object.keys(FILES).map((name) => [
    name,
    fetch(`/static/sounds/${name}.mp3`)
      .then((response) => (response.ok ? response.arrayBuffer() : null))
      .catch(() => null),
  ]),
);

function readMuted() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

/** The audio context, created on first use (browsers only allow it after a user gesture). */
function audio() {
  if (!context) {
    const Context = window.AudioContext ?? window.webkitAudioContext;
    if (!Context) return null;
    context = new Context();
    noise = context.createBuffer(1, context.sampleRate, context.sampleRate);
    const data = noise.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    for (const [name, download] of Object.entries(downloads)) {
      download
        .then((bytes) => (bytes ? context.decodeAudioData(bytes) : null))
        .then((buffer) => {
          if (buffer) buffers[name] = buffer;
        })
        .catch(() => {});
    }
  }
  if (context.state === "suspended") context.resume();
  return context;
}

// ---------- Recorded sounds ----------

function playFile(ctx, name, volume, at) {
  const buffer = buffers[name];
  const { start, max, gain: level } = FILES[name];
  const length = Math.min(buffer.duration - start, max ?? Infinity);
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(level * volume, at);
  if (max !== null && length < buffer.duration - start) {
    gain.gain.setValueAtTime(level * volume, at + length - FADE);
    gain.gain.linearRampToValueAtTime(0, at + length);
  }
  source.connect(gain).connect(ctx.destination);
  source.start(at, start, length);
}

// ---------- Made-up sounds, used when a file is missing ----------

function envelope(ctx, peak, attack, decay, at) {
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(peak, at + attack);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
  gain.connect(ctx.destination);
  return gain;
}

function noiseBurst(ctx, { at, volume, decay, type, from, to, q = 1 }) {
  const source = ctx.createBufferSource();
  source.buffer = noise;
  const filter = ctx.createBiquadFilter();
  filter.type = type;
  filter.Q.value = q;
  filter.frequency.setValueAtTime(from, at);
  filter.frequency.exponentialRampToValueAtTime(to, at + decay);
  source.connect(filter).connect(envelope(ctx, volume, 0.008, decay, at));
  source.start(at);
  source.stop(at + decay + 0.05);
}

function tone(ctx, { at, volume, decay, from, to, type = "sine" }) {
  const osc = ctx.createOscillator();
  osc.type = type;
  osc.frequency.setValueAtTime(from, at);
  osc.frequency.exponentialRampToValueAtTime(to, at + decay);
  osc.connect(envelope(ctx, volume, 0.005, decay, at));
  osc.start(at);
  osc.stop(at + decay + 0.05);
}

const madeUp = {
  miss(ctx, v, at) {
    noiseBurst(ctx, { at, volume: 0.22 * v, decay: 0.45, type: "bandpass", from: 1800, to: 500, q: 0.8 });
    tone(ctx, { at, volume: 0.12 * v, decay: 0.16, from: 520, to: 160 });
  },
  hit(ctx, v, at) {
    tone(ctx, { at, volume: 0.55 * v, decay: 0.4, from: 140, to: 38 });
    noiseBurst(ctx, { at, volume: 0.35 * v, decay: 0.3, type: "lowpass", from: 2400, to: 300 });
  },
  sunk(ctx, v, at) {
    madeUp.hit(ctx, v, at);
    tone(ctx, { at: at + 0.12, volume: 0.45 * v, decay: 0.9, from: 90, to: 28, type: "triangle" });
    noiseBurst(ctx, { at: at + 0.1, volume: 0.3 * v, decay: 0.9, type: "lowpass", from: 900, to: 120 });
  },
  win(ctx, v, at) {
    [523, 659, 784, 1047].forEach((f, i) =>
      tone(ctx, { at: at + i * 0.12, volume: 0.18 * v, decay: 0.5, from: f, to: f, type: "triangle" }),
    );
  },
  lose(ctx, v, at) {
    [392, 330, 262, 196].forEach((f, i) =>
      tone(ctx, { at: at + i * 0.18, volume: 0.18 * v, decay: 0.6, from: f, to: f * 0.97, type: "triangle" }),
    );
  },
};

// ---------- Public ----------

function play(name, volume) {
  if (muted) return;
  const ctx = audio();
  if (!ctx) return;
  const at = ctx.currentTime + 0.01;
  if (buffers[name]) playFile(ctx, name, volume, at);
  else madeUp[name]?.(ctx, volume, at);
}

/** Play the sound of a shot outcome ("miss", "hit" or "sunk"); `volume` scales it. */
export function playShot(outcome, volume = 1) {
  play(outcome, volume);
}

/** Play the short victory or defeat sting at the end of a game. */
export function playResult(won) {
  play(won ? "win" : "lose", 1);
}

/** Wake the audio context during a click, so later sounds are allowed to play. */
export function unlock() {
  if (!muted) audio();
}

export const isMuted = () => muted;

export function setMuted(value) {
  muted = value;
  try {
    localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
  } catch {
    // Storage blocked: the choice lasts until the page closes.
  }
}
