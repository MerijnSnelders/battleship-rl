// The game page: draws what the server sends and turns clicks, taps and drags into API calls.
// It knows no game rule. Whether a placement is legal comes from `legal_starts` in the
// state, and every shot's outcome comes from the server.

import { api, ApiError } from "./api.js";
import { blueprintSvg, hullSvg } from "./ships.js";
import { isMuted, playResult, playShot, setMuted, unlock } from "./sound.js";

const STORAGE_KEY = "battleship-rl:game";
const DEFAULT_OPPONENT = "hunt_target";
const AI_SHOT_DELAY = 500;
const DRAG_THRESHOLD = 6;
const COLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

const $ = (id) => document.getElementById(id);
const els = {
  body: document.body,
  blueprint: $("blueprint"),
  play: $("play-button"),
  titleScreen: $("title-screen"),
  status: $("status"),
  opponentLabel: $("opponent-label"),
  ownSide: $("own-side"),
  enemySide: $("enemy-side"),
  ownBoard: $("own-board"),
  enemyBoard: $("enemy-board"),
  ownFleet: $("own-fleet"),
  enemyFleet: $("enemy-fleet"),
  dock: $("dock"),
  opponents: $("opponents"),
  start: $("start-button"),
  rotate: $("rotate-button"),
  orientationLabel: $("orientation-label"),
  random: $("random-button"),
  clear: $("clear-button"),
  newGame: $("new-game-button"),
  result: $("result"),
  resultTitle: $("result-title"),
  resultNewGame: $("result-new-game"),
  resultClose: $("result-close"),
  statShots: $("stat-shots"),
  statAccuracy: $("stat-accuracy"),
  statAiShots: $("stat-ai-shots"),
  ghost: $("ghost"),
  home: $("home-button"),
  sound: $("sound-button"),
  resumeNote: $("resume-note"),
  challenge: $("challenge"),
  stepIconPlace: $("step-icon-place"),
  stepTextPlace: $("step-text-place"),
  stepTextOpponents: $("step-text-opponents"),
  factBoard: $("fact-board"),
  factFleet: $("fact-fleet"),
  factOpponents: $("fact-opponents"),
};

const configName = new URLSearchParams(location.search).get("config") ?? "standard";
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, reducedMotion() ? 0 : ms));

let state = null;
let opponents = [];
let opponentName = DEFAULT_OPPONENT;
let orientation = "horizontal";
let selected = null; // length chosen in the dock for tap placement
let busy = false;
let gesture = null; // pointer down on a dock ship or a placed ship, maybe becoming a drag
let suppressClick = false;
let ownOverride = null; // the own board's view while the AI's turn is being played back
const fresh = new Set(); // marks to animate on the next render, as "board:row,col"
const freshSunk = new Set(); // sunk ships to animate, as "board:row,col" of their start

// ---------- Small helpers ----------

const size = () => state.config.size;
const key = ([row, col]) => `${row},${col}`;
const other = (o) => (o === "horizontal" ? "vertical" : "horizontal");

function save(id) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the game simply will not survive a reload.
  }
}

function saved() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function setStatus(text, tone = "") {
  els.status.textContent = text;
  els.status.dataset.tone = tone;
}

function friendly(error) {
  const messages = {
    overlap: "That spot overlaps another ship.",
    off_board: "That ship does not fit there.",
    ship_not_in_fleet: "That ship is already placed.",
    game_not_found: "This game expired. Start a new one.",
    network: "Could not reach the server. Check your connection.",
  };
  if (error instanceof ApiError) return messages[error.code] ?? error.message;
  console.error(error);
  return "Something went wrong.";
}

/** Run one server action at a time; interactions during it are ignored. */
async function act(action) {
  if (busy) return false;
  busy = true;
  els.body.classList.add("busy");
  try {
    await action();
    return true;
  } catch (error) {
    setStatus(friendly(error), "alert");
    if (error instanceof ApiError && error.code === "game_not_found") {
      save(null);
      state = null;
      showScreen("title");
    }
    return false;
  } finally {
    busy = false;
    els.body.classList.remove("busy");
    updateControls();
  }
}

/** A ship drawn from its squares, for sunk ships which the view lists by squares only. */
function shipFromSquares(squares) {
  const sorted = [...squares].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const vertical = sorted.length > 1 && sorted[0][1] === sorted[1][1];
  return {
    start: sorted[0],
    length: sorted.length,
    orientation: vertical ? "vertical" : "horizontal",
    squares: sorted,
  };
}

function position(el, [row, col], length, orient, n) {
  const across = orient === "horizontal" ? length : 1;
  const down = orient === "horizontal" ? 1 : length;
  el.style.left = `${(col / n) * 100}%`;
  el.style.top = `${(row / n) * 100}%`;
  el.style.width = `${(across / n) * 100}%`;
  el.style.height = `${(down / n) * 100}%`;
}

// ---------- Screens ----------

function showScreen(name) {
  els.body.dataset.screen = name;
}

// ---------- Boards ----------

function buildBoard(board, n) {
  if (Number(board.dataset.size) === n) return;
  board.dataset.size = n;
  board.style.setProperty("--n", n);
  const squares = [];
  for (let row = 0; row < n; row++) {
    for (let col = 0; col < n; col++) {
      const label = `${COLS[col]}${row + 1}`;
      squares.push(
        `<button class="square" type="button" data-row="${row}" data-col="${col}" aria-label="${label}" tabindex="-1"></button>`,
      );
    }
  }
  board.innerHTML = `${squares.join("")}<div class="layer ships"></div><div class="layer marks"></div>`;
  const frame = board.parentElement;
  frame.style.setProperty("--n", n);
  frame.querySelector(".cols").innerHTML = Array.from({ length: n }, (_, i) => `<span>${COLS[i]}</span>`).join("");
  frame.querySelector(".rows").innerHTML = Array.from({ length: n }, (_, i) => `<span>${i + 1}</span>`).join("");
}

function shipElement(ship, n, classes) {
  const el = document.createElement("div");
  el.className = `ship ${classes}`;
  el.innerHTML = hullSvg(ship.length, ship.orientation);
  position(el, ship.start, ship.length, ship.orientation, n);
  return el;
}

function renderMarks(board, boardName, grid) {
  const n = grid.length;
  const marks = [];
  grid.forEach((row, r) =>
    row.forEach((square, c) => {
      if (square === "unknown") return;
      const id = `${boardName}:${r},${c}`;
      const isFresh = fresh.delete(id) ? " fresh" : "";
      const style = `left:${(c / n) * 100}%;top:${(r / n) * 100}%;width:${100 / n}%;height:${100 / n}%`;
      marks.push(`<div class="mark ${square}${isFresh}" style="${style}"></div>`);
    }),
  );
  board.querySelector(".marks").innerHTML = marks.join("");
  board.querySelectorAll(".square").forEach((el) => {
    el.dataset.state = grid[el.dataset.row][el.dataset.col];
  });
}

function renderOwn() {
  const n = size();
  const view = ownOverride ?? state.human_board.view;
  buildBoard(els.ownBoard, n);
  const layer = els.ownBoard.querySelector(".ships");
  const preview = layer.querySelector(".preview");
  layer.replaceChildren();
  const sunk = new Set(view.sunk_ships.map((s) => key(shipFromSquares(s.squares).start)));
  const setup = state.phase === "setup";
  for (const ship of state.human_board.ships) {
    const id = key(ship.start);
    let classes = setup ? "placed" : "own";
    if (sunk.has(id)) classes += " sunk";
    if (freshSunk.delete(`own:${id}`)) classes += " sinking";
    const el = shipElement(ship, n, classes);
    el.dataset.start = id;
    layer.append(el);
  }
  if (preview) layer.append(preview);
  renderMarks(els.ownBoard, "own", view.grid);
  renderFleet(els.ownFleet, view.sunk_ships);
}

function renderEnemy() {
  const n = size();
  const view = state.ai_board.view;
  buildBoard(els.enemyBoard, n);
  const layer = els.enemyBoard.querySelector(".ships");
  layer.replaceChildren();
  const sunkStarts = new Set();
  for (const sunkShip of view.sunk_ships) {
    const ship = shipFromSquares(sunkShip.squares);
    const id = key(ship.start);
    sunkStarts.add(id);
    const sinking = freshSunk.delete(`enemy:${id}`) ? " sinking" : "";
    layer.append(shipElement(ship, n, `enemy sunk${sinking}`));
  }
  for (const ship of state.ai_board.ships ?? []) {
    if (!sunkStarts.has(key(ship.start))) layer.append(shipElement(ship, n, "revealed"));
  }
  renderMarks(els.enemyBoard, "enemy", view.grid);
  renderFleet(els.enemyFleet, view.sunk_ships);
}

function renderFleet(el, sunkShips) {
  const sunk = sunkShips.map((s) => s.length);
  el.innerHTML = state.config.ships
    .map((length) => {
      const index = sunk.indexOf(length);
      const isSunk = index !== -1;
      if (isSunk) sunk.splice(index, 1);
      return `<span class="fleet-ship${isSunk ? " sunk" : ""}" style="--len:${length}" title="${length}-square ship${isSunk ? ", sunk" : ""}">${hullSvg(length)}</span>`;
    })
    .join("");
}

function renderDock() {
  const unplaced = state.human_board.unplaced;
  if (selected !== null && !unplaced.includes(selected)) selected = null;
  const highlighted = unplaced.indexOf(selected); // only one of several equal ships lights up
  els.dock.innerHTML = unplaced.length
    ? unplaced
        .map(
          (length, i) => `
      <button class="dock-ship${i === highlighted ? " selected" : ""}" type="button" data-length="${length}"
        style="--len:${length}" aria-pressed="${i === highlighted}" aria-label="${length}-square ship">
        <span class="dock-hull">${hullSvg(length)}</span>
        <span class="dock-length">${length}</span>
      </button>`,
        )
        .join("")
    : `<p class="dock-empty">Fleet in position. Pick an opponent and start.</p>`;
}

function renderOpponents() {
  els.opponents.innerHTML = opponents
    .map(
      (o) => `
    <label class="opponent${o.name === opponentName ? " chosen" : ""}">
      <input type="radio" name="opponent" value="${o.name}" ${o.name === opponentName ? "checked" : ""}>
      <span class="opponent-name">${o.display_name}</span>
      <span class="opponent-text">${o.description}</span>
    </label>`,
    )
    .join("");
}

function updateControls() {
  if (!state) return;
  const setup = state.phase === "setup";
  els.start.disabled = busy || !setup || state.human_board.unplaced.length > 0;
  els.clear.disabled = busy || !setup || state.human_board.ships.length === 0;
  els.random.disabled = busy || !setup;
  els.rotate.disabled = busy || !setup;
  els.orientationLabel.textContent = orientation;
}

function render() {
  els.body.dataset.phase = state.phase;
  const opponent = opponents.find((o) => o.name === state.opponent);
  els.opponentLabel.textContent = `vs ${opponent?.display_name ?? state.opponent}`;
  renderOwn();
  renderEnemy();
  if (state.phase === "setup") renderDock();
  document.documentElement.style.setProperty("--sq", `${squareSize()}px`);
  updateControls();
}

// ---------- Legal placements (looked up, never computed) ----------

function legalStarts(length, orient) {
  const entry = state.human_board.legal_starts?.find((item) => item.length === length);
  return new Set((entry?.[orient] ?? []).map(key));
}

/** Where a ship lands if `square` is under its square number `grab`, kept on the board. */
function landing(length, orient, [row, col], grab) {
  const n = size();
  const clamp = (v) => Math.max(0, Math.min(n - length, v));
  const start = orient === "horizontal" ? [row, clamp(col - grab)] : [clamp(row - grab), col];
  return { start, legal: legalStarts(length, orient).has(key(start)) };
}

function squareAt(board, x, y) {
  const rect = board.getBoundingClientRect();
  if (x < rect.left || x >= rect.right || y < rect.top || y >= rect.bottom) return null;
  const n = size();
  return [Math.floor(((y - rect.top) / rect.height) * n), Math.floor(((x - rect.left) / rect.width) * n)];
}

function previewElement() {
  const layer = els.ownBoard.querySelector(".ships");
  let el = layer.querySelector(".preview");
  if (!el) {
    el = document.createElement("div");
    el.className = "ship preview";
    el.hidden = true;
    layer.append(el);
  }
  return el;
}

function showPreview(length, orient, spot) {
  const el = previewElement();
  if (!spot) {
    el.hidden = true;
    return;
  }
  const shape = `${length}-${orient}`;
  if (el.dataset.shape !== shape) {
    el.dataset.shape = shape;
    el.innerHTML = hullSvg(length, orient);
  }
  el.hidden = false;
  el.classList.toggle("legal", spot.legal);
  el.classList.toggle("illegal", !spot.legal);
  position(el, spot.start, length, orient, size());
}

function hidePreview() {
  const el = els.ownBoard.querySelector(".preview");
  if (el) el.hidden = true;
}

// ---------- Setup actions ----------

async function place(length, orient, start) {
  return act(async () => {
    state = await api.place(state.id, start, length, orient);
    render();
  });
}

async function placeSelected(square) {
  const length = selected;
  const spot = landing(length, orientation, square, 0);
  if (!spot.legal) {
    showPreview(length, orientation, spot);
    shake(els.ownBoard.querySelector(".preview"));
    setStatus("No room for that ship there.", "alert");
    return;
  }
  const ok = await place(length, orientation, spot.start);
  if (ok) {
    selected = state.human_board.unplaced[0] ?? null;
    renderDock();
    setStatus(selected ? `Placed. Next: the ${selected}-square ship.` : "Fleet in position.");
  }
}

async function rotateInPlace(ship) {
  await act(async () => {
    state = await api.remove(state.id, ship.start);
    const turned = other(ship.orientation);
    const spot = landing(ship.length, turned, ship.start, 0);
    if (spot.legal) {
      state = await api.place(state.id, spot.start, ship.length, turned);
      render();
      setStatus("Ship turned.");
    } else {
      state = await api.place(state.id, ship.start, ship.length, ship.orientation);
      render();
      shake(els.ownBoard.querySelector(`[data-start="${key(ship.start)}"]`));
      setStatus("No room to turn that ship here.", "alert");
    }
  });
}

function shake(el) {
  if (!el) return;
  el.classList.remove("shake");
  void el.offsetWidth;
  el.classList.add("shake");
}

function setOrientation(next) {
  orientation = next;
  updateControls();
  if (gesture?.dragging) {
    gesture.orientation = next;
    updateDrag(gesture.lastX, gesture.lastY);
  } else if (gesture === null && selected !== null && hoverSquare) {
    showPreview(selected, orientation, landing(selected, orientation, hoverSquare, 0));
  }
}

// ---------- Drag and tap gestures ----------

let hoverSquare = null;

function squareSize() {
  return els.ownBoard.getBoundingClientRect().width / size();
}

function beginGesture(event, el, info) {
  if (busy || state?.phase !== "setup" || event.button > 0) return;
  event.preventDefault();
  const rect = el.getBoundingClientRect();
  const sq = squareSize();
  const along = info.orientation === "horizontal" ? event.clientX - rect.left : event.clientY - rect.top;
  const scale = info.kind === "dock" ? rect.width / (info.length * sq) : 1;
  gesture = {
    ...info,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    lastX: event.clientX,
    lastY: event.clientY,
    grab: Math.max(0, Math.min(info.length - 1, Math.floor(along / (sq * scale)))),
    dragging: false,
    lift: null,
    el,
  };
}

function startDrag() {
  gesture.dragging = true;
  els.body.classList.add("dragging");
  const { length } = gesture;
  if (gesture.kind === "placed") {
    gesture.el.classList.add("lifting");
    const ship = gesture.ship;
    gesture.lift = api
      .remove(state.id, ship.start)
      .then((next) => {
        state = next;
        if (gesture?.dragging) updateDrag(gesture.lastX, gesture.lastY);
        return true;
      })
      .catch((error) => {
        setStatus(friendly(error), "alert");
        return false;
      });
  } else {
    gesture.el.classList.add("lifting");
  }
  els.ghost.hidden = false;
  els.ghost.dataset.shape = "";
  setStatus(`Moving the ${length}-square ship. R or right-click rotates.`);
}

function updateDrag(x, y) {
  const { length, orientation: orient, grab } = gesture;
  const sq = squareSize();
  const shape = `${length}-${orient}`;
  if (els.ghost.dataset.shape !== shape) {
    els.ghost.dataset.shape = shape;
    els.ghost.innerHTML = hullSvg(length, orient);
    els.ghost.style.width = `${(orient === "horizontal" ? length : 1) * sq}px`;
    els.ghost.style.height = `${(orient === "horizontal" ? 1 : length) * sq}px`;
  }
  const dx = orient === "horizontal" ? (grab + 0.5) * sq : 0.5 * sq;
  const dy = orient === "horizontal" ? 0.5 * sq : (grab + 0.5) * sq;
  els.ghost.style.transform = `translate(${x - dx}px, ${y - dy}px)`;
  const square = squareAt(els.ownBoard, x, y);
  gesture.spot = square ? landing(length, orient, square, grab) : null;
  showPreview(length, orient, gesture.spot);
}

function endDrag() {
  els.body.classList.remove("dragging");
  els.ghost.hidden = true;
  hidePreview();
  gesture?.el?.classList.remove("lifting");
}

async function finishDrag() {
  const g = gesture;
  gesture = null;
  endDrag();
  suppressClick = true;
  setTimeout(() => (suppressClick = false), 0);
  if (g.kind === "placed") {
    busy = true;
    const lifted = await g.lift;
    busy = false;
    if (!lifted) return;
    const target = g.spot && legalStarts(g.length, g.orientation).has(key(g.spot.start)) ? g.spot : null;
    if (target) {
      await place(g.length, g.orientation, target.start);
      setStatus("Ship moved.");
    } else {
      await place(g.length, g.ship.orientation, g.ship.start);
      if (g.spot) setStatus("No room there, so the ship went back.", "alert");
      else setStatus("Ship put back.");
    }
    return;
  }
  if (g.spot?.legal) {
    await place(g.length, g.orientation, g.spot.start);
    setStatus(
      state.human_board.unplaced.length ? "Placed. Drag the next ship." : "Fleet in position. Pick an opponent and start.",
    );
  } else if (g.spot) {
    setStatus("No room for that ship there.", "alert");
  }
}

async function cancelDrag() {
  if (!gesture?.dragging) return;
  gesture.spot = null;
  await finishDrag();
}

function onPointerMove(event) {
  if (gesture && event.pointerId === gesture.pointerId) {
    gesture.lastX = event.clientX;
    gesture.lastY = event.clientY;
    if (!gesture.dragging) {
      const moved = Math.hypot(event.clientX - gesture.startX, event.clientY - gesture.startY);
      if (moved < DRAG_THRESHOLD) return;
      startDrag();
    }
    updateDrag(event.clientX, event.clientY);
    return;
  }
  // Hover preview for tap placement with a mouse.
  if (state?.phase === "setup" && selected !== null && !busy) {
    hoverSquare = squareAt(els.ownBoard, event.clientX, event.clientY);
    showPreview(selected, orientation, hoverSquare && landing(selected, orientation, hoverSquare, 0));
  }
}

async function onPointerUp(event) {
  if (!gesture || event.pointerId !== gesture.pointerId) return;
  if (gesture.dragging) {
    await finishDrag();
    return;
  }
  const g = gesture;
  gesture = null;
  if (g.kind === "dock") {
    selected = selected === g.length ? null : g.length;
    renderDock();
    hidePreview();
    setStatus(selected ? `Tap a square on your board for the ${selected}-square ship.` : "Place your fleet.");
  } else {
    suppressClick = true;
    setTimeout(() => (suppressClick = false), 0);
    await rotateInPlace(g.ship);
  }
}

// ---------- Game flow ----------

async function newGame(opponent = opponentName) {
  return act(async () => {
    state = await api.newGame(opponent, configName);
    opponentName = state.opponent;
    save(state.id);
    selected = state.human_board.unplaced[0];
    orientation = "horizontal";
    els.result.hidden = true;
    renderOpponents();
    render();
    showScreen("game");
    setStatus("Place your fleet: drag ships onto your board, or tap one and then a square.");
  });
}

async function changeOpponent(name) {
  if (state?.phase !== "setup" || name === state.opponent) return;
  const ships = state.human_board.ships;
  await act(async () => {
    // The opponent is fixed when a game is created, so start a new game with the same ships.
    let next = await api.newGame(name, configName);
    for (const ship of ships) {
      next = await api.place(next.id, ship.start, ship.length, ship.orientation);
    }
    state = next;
    opponentName = name;
    save(state.id);
    renderOpponents();
    render();
    const chosen = opponents.find((o) => o.name === name);
    setStatus(`Opponent: ${chosen?.display_name ?? name}.`);
  });
}

async function startBattle() {
  await act(async () => {
    const before = state.human_board.view;
    const result = await api.start(state.id);
    state = result.state;
    selected = null;
    render();
    if (result.ai_turn.length) {
      setStatus("Coin flip: the AI fires first.", "alert");
      await sleep(900);
      await replayAi(before, result.ai_turn);
    } else {
      setStatus("Coin flip: you fire first. Pick a square in enemy waters.", "good");
    }
    afterTurn();
  });
}

async function fire(row, col) {
  if (state?.phase !== "playing" || state.ai_board.view.grid[row][col] !== "unknown") return;
  await act(async () => {
    const before = state.human_board.view;
    const result = await api.fire(state.id, row, col);
    state = result.state;
    fresh.add(`enemy:${row},${col}`);
    if (result.shot.sunk_ship) freshSunk.add(`enemy:${key(result.shot.sunk_ship.start)}`);
    ownOverride = structuredClone(before);
    render();
    const { outcome, sunk_ship: sunkShip } = result.shot;
    playShot(outcome);
    if (outcome === "sunk") setStatus(`You sank a ${sunkShip.length}-square ship!${state.phase === "over" ? "" : " Fire again."}`, "good");
    else if (outcome === "hit") setStatus("Hit! Fire again.", "good");
    else setStatus("Miss.");
    if (result.ai_turn.length) {
      await sleep(650);
      await replayAi(before, result.ai_turn);
    }
    ownOverride = null;
    render();
    afterTurn();
  });
}

/** Play the AI's shots back one at a time on the own board, starting from `before`. */
async function replayAi(before, shots) {
  ownOverride = structuredClone(before);
  els.body.classList.add("ai-turn");
  setStatus("The AI is firing...", "alert");
  for (const shot of shots) {
    const [row, col] = shot.square;
    ownOverride.grid[row][col] = shot.outcome;
    fresh.add(`own:${row},${col}`);
    playShot(shot.outcome, 0.6);
    const ship = state.human_board.ships.find((s) => s.squares.some(([r, c]) => r === row && c === col));
    if (shot.sunk_ship) {
      for (const [r, c] of shot.sunk_ship.squares) ownOverride.grid[r][c] = "sunk";
      ownOverride.sunk_ships.push({ length: shot.sunk_ship.length, squares: shot.sunk_ship.squares });
      freshSunk.add(`own:${key(shot.sunk_ship.start)}`);
      setStatus(`The AI sank your ${shot.sunk_ship.length}-square ship.`, "alert");
    } else if (shot.outcome === "hit") {
      setStatus(`The AI hit your ${ship?.length ?? ""}-square ship.`, "alert");
    } else {
      setStatus(`The AI missed at ${COLS[col]}${row + 1}.`);
    }
    renderOwn();
    await sleep(AI_SHOT_DELAY);
  }
  ownOverride = null;
  els.body.classList.remove("ai-turn");
}

function afterTurn() {
  render();
  if (state.phase === "over") {
    showResult({ sting: true });
  } else if (state.phase === "playing") {
    const tone = els.status.dataset.tone;
    if (!/Fire again/.test(els.status.textContent)) setStatus("Your turn. Pick a square in enemy waters.", tone === "alert" ? "" : tone);
  }
}

/** Open the battle report. `sting` plays the win or lose sound, only when the game just ended. */
function showResult({ sting = false } = {}) {
  const won = state.winner === "human";
  const view = state.ai_board.view;
  const strikes = view.grid.flat().filter((s) => s === "hit" || s === "sunk").length;
  els.resultTitle.textContent = won ? "Victory. Enemy fleet sunk." : "Defeat. Your fleet is sunk.";
  els.resultTitle.dataset.won = won;
  els.statShots.textContent = view.shot_count;
  els.statAccuracy.textContent = view.shot_count ? `${Math.round((strikes / view.shot_count) * 100)}%` : "0%";
  els.statAiShots.textContent = state.human_board.view.shot_count;
  setStatus(won ? `You won in ${view.shot_count} shots.` : `The AI won in ${state.human_board.view.shot_count} shots.`, won ? "good" : "alert");
  setTimeout(() => {
    els.result.hidden = false;
    els.resultNewGame.focus();
    if (sting) playResult(won);
  }, reducedMotion() ? 0 : 700);
}

// ---------- Wiring ----------

function wire() {
  els.play.addEventListener("click", async () => {
    if (els.titleScreen.classList.contains("firing")) return;
    unlock();
    if (!reducedMotion()) {
      els.titleScreen.classList.add("firing");
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
    if (unfinished()) {
      // Back from the home page: carry on with the battle that was left.
      render();
      showScreen("game");
      setStatus(state.phase === "setup" ? "Welcome back. Finish placing your fleet." : "Welcome back. Your turn.");
    } else {
      await newGame();
    }
    els.titleScreen.classList.remove("firing");
  });

  els.home.addEventListener("click", () => {
    els.result.hidden = true;
    renderTitle();
    showScreen("title");
    window.scrollTo(0, 0);
  });

  els.sound.addEventListener("click", () => {
    setMuted(!isMuted());
    renderSoundButton();
    if (!isMuted()) {
      unlock();
      playShot("hit", 0.5);
    }
  });
  renderSoundButton();

  els.dock.addEventListener("pointerdown", (event) => {
    const item = event.target.closest(".dock-ship");
    if (!item) return;
    beginGesture(event, item, { kind: "dock", length: Number(item.dataset.length), orientation });
  });

  els.ownBoard.addEventListener("pointerdown", (event) => {
    const item = event.target.closest(".ship.placed");
    if (!item) return;
    const ship = state.human_board.ships.find((s) => key(s.start) === item.dataset.start);
    if (!ship) return;
    beginGesture(event, item, { kind: "placed", ship, length: ship.length, orientation: ship.orientation });
  });

  els.ownBoard.addEventListener("click", (event) => {
    if (suppressClick || state?.phase !== "setup" || selected === null || busy) return;
    if (event.target.closest(".ship.placed")) return;
    const square = squareAt(els.ownBoard, event.clientX, event.clientY);
    if (square) placeSelected(square);
  });

  els.ownBoard.addEventListener("pointerleave", () => {
    if (!gesture) {
      hoverSquare = null;
      hidePreview();
    }
  });

  els.enemyBoard.addEventListener("click", (event) => {
    const square = event.target.closest(".square");
    if (square && !busy) fire(Number(square.dataset.row), Number(square.dataset.col));
  });

  // The first click anywhere allows audio, so the sound files are ready before the first shot.
  window.addEventListener("pointerdown", unlock, { once: true });
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
  window.addEventListener("pointercancel", () => cancelDrag());

  window.addEventListener("keydown", (event) => {
    if (state?.phase !== "setup" || els.body.dataset.screen !== "game") return;
    if ((event.key === "r" || event.key === "R") && !event.ctrlKey && !event.metaKey) {
      setOrientation(other(gesture?.dragging ? gesture.orientation : orientation));
    } else if (event.key === "Escape") {
      if (gesture?.dragging) cancelDrag();
      else if (selected !== null) {
        selected = null;
        renderDock();
        hidePreview();
      }
    }
  });

  window.addEventListener("contextmenu", (event) => {
    if (state?.phase === "setup" && (gesture?.dragging || selected !== null) && els.body.dataset.screen === "game") {
      event.preventDefault();
      setOrientation(other(gesture?.dragging ? gesture.orientation : orientation));
    }
  });

  els.rotate.addEventListener("click", () => setOrientation(other(orientation)));
  els.random.addEventListener("click", () =>
    act(async () => {
      state = await api.randomFleet(state.id);
      selected = null;
      render();
      setStatus("Random fleet placed. Drag ships to adjust, or start.");
    }),
  );
  els.clear.addEventListener("click", () =>
    act(async () => {
      state = await api.clear(state.id);
      selected = state.human_board.unplaced[0];
      render();
      setStatus("Board cleared. Place your fleet.");
    }),
  );
  els.start.addEventListener("click", startBattle);
  els.opponents.addEventListener("change", (event) => changeOpponent(event.target.value));

  els.newGame.addEventListener("click", () => {
    const underway = state?.phase === "playing" && state.ai_board.view.shot_count > 0;
    if (underway && !window.confirm("Abandon this battle and start a new game?")) return;
    newGame();
  });
  els.resultNewGame.addEventListener("click", () => newGame());
  els.resultClose.addEventListener("click", () => {
    els.result.hidden = true;
  });

  new ResizeObserver(() => {
    if (state) document.documentElement.style.setProperty("--sq", `${squareSize()}px`);
  }).observe(els.ownBoard);
}

// ---------- Home page ----------

const unfinished = () => state !== null && state.phase !== "over";

function renderSoundButton() {
  els.sound.setAttribute("aria-pressed", String(!isMuted()));
  els.sound.title = isMuted() ? "Sound off" : "Sound on";
}

/** Fill the home page with what the server knows: fleet, opponents and the resume note. */
function renderTitle(config = state?.config) {
  if (config) {
    els.factBoard.textContent = `${config.size} × ${config.size}`;
    els.factFleet.textContent = `${config.ships.length} ships`;
    els.stepTextPlace.textContent = `Drag ${config.ships.length} ships (${config.ships.join(", ")} squares long) onto a ${config.size} × ${config.size} grid, or let chance place them.`;
  }
  if (opponents.length) {
    els.factOpponents.textContent = String(opponents.length);
    const names = opponents.map((o) => o.display_name);
    els.stepTextOpponents.textContent = `${names.slice(0, -1).join(", ")} or ${names.at(-1)}: from a random shooter to AIs that reason about where your ships can be.`;
  }
  els.resumeNote.hidden = !unfinished();
  if (unfinished()) {
    const opponent = opponents.find((o) => o.name === state.opponent);
    els.resumeNote.textContent = `Continue your battle against ${opponent?.display_name ?? state.opponent}`;
  }
}

/** The benchmark challenge: how many shots the best AI needs. Hidden without results. */
async function renderChallenge() {
  try {
    const stats = await api.stats(configName);
    const best = stats.ais[0];
    const worst = stats.ais.at(-1);
    if (!best) return;
    renderTitle(stats.config);
    const fmt = (n) => n.toLocaleString("en-US", { maximumFractionDigits: 1 });
    els.challenge.innerHTML = `
      <span class="challenge-label">Benchmark, ${fmt(stats.games)} games</span>
      <span class="challenge-text"><strong>${best.display_name}</strong> sinks a whole fleet in
      <span class="challenge-number">${fmt(best.mean)}</span> shots on average.
      ${worst && worst !== best ? `${worst.display_name} needs ${fmt(worst.mean)}.` : ""} Can you beat it?</span>`;
    els.challenge.hidden = false;
  } catch {
    els.challenge.hidden = true;
  }
}

async function init() {
  els.blueprint.innerHTML = blueprintSvg();
  // Lets CSS draw every line of the blueprint from start to end.
  for (const part of els.blueprint.querySelectorAll(".bp-draw > :not([stroke-dasharray])")) {
    part.setAttribute("pathLength", "1");
  }
  els.stepIconPlace.innerHTML = hullSvg(4);
  wire();
  renderChallenge();
  try {
    opponents = await api.opponents();
  } catch (error) {
    setStatus(friendly(error), "alert");
  }
  if (!opponents.some((o) => o.name === opponentName) && opponents.length) opponentName = opponents[0].name;
  renderOpponents();

  const id = saved();
  if (id) {
    try {
      state = await api.getGame(id);
      opponentName = state.opponent;
      selected = state.human_board.unplaced[0] ?? null;
      renderOpponents();
      render();
      showScreen("game");
      if (state.phase === "setup") setStatus("Welcome back. Finish placing your fleet.");
      else if (state.phase === "playing") setStatus("Welcome back. Your turn.");
      else showResult();
      return;
    } catch {
      save(null);
      state = null;
    }
  }
  renderTitle();
  showScreen("title");
}

init();
