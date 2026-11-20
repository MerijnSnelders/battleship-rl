// Shot sounds made with the Web Audio API, so there are no sound files to download.
// A miss is a short splash, a hit a boom, a sink a heavier boom with a rumble after it.

const STORAGE_KEY = "battleship-rl:muted";

let context = null;
let noise = null;
let muted = readMuted();

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
    // One second of white noise, reused as the source of every splash and blast.
    noise = context.createBuffer(1, context.sampleRate, context.sampleRate);
    const data = noise.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  }
  if (context.state === "suspended") context.resume();
  return context;
}

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

const sounds = {
  miss(ctx, v, at) {
    noiseBurst(ctx, { at, volume: 0.22 * v, decay: 0.45, type: "bandpass", from: 1800, to: 500, q: 0.8 });
    tone(ctx, { at, volume: 0.12 * v, decay: 0.16, from: 520, to: 160 });
  },
  hit(ctx, v, at) {
    tone(ctx, { at, volume: 0.55 * v, decay: 0.4, from: 140, to: 38 });
    noiseBurst(ctx, { at, volume: 0.35 * v, decay: 0.3, type: "lowpass", from: 2400, to: 300 });
  },
  sunk(ctx, v, at) {
    sounds.hit(ctx, v, at);
    tone(ctx, { at: at + 0.12, volume: 0.45 * v, decay: 0.9, from: 90, to: 28, type: "triangle" });
    noiseBurst(ctx, { at: at + 0.1, volume: 0.3 * v, decay: 0.9, type: "lowpass", from: 900, to: 120 });
  },
};

/** Play the sound of a shot outcome ("miss", "hit" or "sunk"); `volume` scales it. */
export function playShot(outcome, volume = 1) {
  if (muted || !sounds[outcome]) return;
  const ctx = audio();
  if (!ctx) return;
  sounds[outcome](ctx, volume, ctx.currentTime + 0.01);
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
