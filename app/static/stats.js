// The stats page: benchmark results from /api/stats as a table, a distribution chart and
// an explanation of every AI. The numbers all come from the server; nothing is computed
// here except what is needed to draw them.

import { api } from "./api.js";

const CONFIGS = ["standard", "small"];
const BASELINE = "hunt_target";
const SVG = "http://www.w3.org/2000/svg";
// Line colours, handed out by AI name in alphabetical order so an AI keeps its colour on
// both boards. Checked for contrast against the navy paper.
const PALETTE = ["#f2b33d", "#6cb8ff", "#e3483c", "#c6d0dc", "#5fd3a6", "#c49bff", "#ff8fb1"];

const $ = (id) => document.getElementById(id);
const els = {
  method: $("method"),
  configSwitch: $("config-switch"),
  error: $("stats-error"),
  content: $("stats-content"),
  rows: $("stats-rows"),
  baselineHead: $("baseline-head"),
  legend: $("legend"),
  chart: $("chart"),
  readout: $("readout"),
  explanations: $("explanations"),
};

const results = {}; // config name -> stats from the API
let current = null; // the config name on screen
const hidden = new Set(); // AI names hidden from the chart

const fmt = (n, digits = 1) =>
  n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const int = (n) => n.toLocaleString("en-US");
const escape = (text) =>
  String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const boardLabel = (config) => `${config.size} × ${config.size}`;
const listLengths = (ships) =>
  ships.length > 1 ? `${ships.slice(0, -1).join(", ")} and ${ships.at(-1)}` : String(ships[0]);

function colours(ais) {
  const sorted = ais.map((ai) => ai.name).sort();
  return Object.fromEntries(sorted.map((name, i) => [name, PALETTE[i % PALETTE.length]]));
}

function el(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  if (parent) parent.appendChild(node);
  return node;
}

// ---------- Method note and config switch ----------

function renderMethod(data) {
  const { size, ships } = data.config;
  const lowest = ships.reduce((a, b) => a + b, 0);
  els.method.textContent =
    `${int(data.games)} benchmark games per AI on a ${boardLabel(data.config)} board with ships of ` +
    `${listLengths(ships)} squares. Every AI fires at the same randomly placed fleets, board for ` +
    `board (seed ${data.seed}), until all ships are sunk. Shots to finish lie between ${lowest} ` +
    `(no miss at all) and ${size * size} (every square).`;
}

function renderSwitch() {
  const available = CONFIGS.filter((name) => results[name]);
  els.configSwitch.hidden = available.length < 2;
  els.configSwitch.replaceChildren(
    ...available.map((name) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button ghost small";
      button.setAttribute("role", "radio");
      button.setAttribute("aria-checked", String(name === current));
      button.textContent = boardLabel(results[name].config);
      button.addEventListener("click", () => show(name));
      return button;
    }),
  );
}

// ---------- Table ----------

function renderTable(data, palette) {
  const baseline = data.ais.find((ai) => ai.name === BASELINE);
  els.baselineHead.hidden = !baseline;
  els.rows.replaceChildren(
    ...data.ais.map((ai, index) => {
      const row = document.createElement("tr");
      const [low, high] = ai.ci95;
      let versus = "";
      if (baseline) {
        const diff = ai.mean - baseline.mean;
        versus =
          ai === baseline
            ? `<span class="muted">baseline</span>`
            : `<span class="${diff < 0 ? "better" : "worse"}">${diff < 0 ? "−" : "+"}${fmt(Math.abs(diff))}</span>`;
      }
      row.innerHTML = `
        <td class="rank">${index + 1}</td>
        <th scope="row" class="ai-col"><span class="swatch" style="--colour:${palette[ai.name]}"></span>${escape(ai.display_name)}</th>
        <td><strong>${fmt(ai.mean)}</strong> <span class="ci">${fmt(low)} to ${fmt(high)}</span></td>
        <td>${fmt(ai.median)}</td>
        <td>${fmt(ai.std)}</td>
        <td>${ai.min} to ${ai.max}</td>
        ${baseline ? `<td>${versus}</td>` : ""}`;
      return row;
    }),
  );
}

// ---------- Chart ----------

/** Round tick steps (1, 2 or 5 times a power of ten) giving about `count` ticks up to `max`. */
function niceStep(max, count) {
  const raw = max / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * power).find((step) => step >= raw);
}

function renderLegend(data, palette) {
  els.legend.replaceChildren(
    ...data.ais.map((ai) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "legend-item";
      button.setAttribute("aria-pressed", String(!hidden.has(ai.name)));
      button.innerHTML = `<span class="swatch" style="--colour:${palette[ai.name]}"></span>${escape(ai.display_name)} <span class="muted">${fmt(ai.mean)}</span>`;
      button.addEventListener("click", () => {
        if (hidden.has(ai.name)) hidden.delete(ai.name);
        else hidden.add(ai.name);
        renderLegend(data, palette);
        renderChart(data, palette);
      });
      return button;
    }),
  );
}

function renderChart(data, palette) {
  const { size, ships } = data.config;
  const lowest = ships.reduce((a, b) => a + b, 0);
  const highest = size * size;
  const visible = data.ais.filter((ai) => !hidden.has(ai.name));
  const shares = Object.fromEntries(
    data.ais.map((ai) => [ai.name, new Map(ai.histogram.map(([shots, games]) => [shots, (100 * games) / ai.games]))]),
  );

  const width = Math.max(300, els.chart.clientWidth);
  const height = Math.round(Math.min(420, Math.max(240, width * 0.5)));
  const pad = { top: 14, right: 14, bottom: 42, left: 46 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const peak = Math.max(1, ...visible.flatMap((ai) => [...shares[ai.name].values()]));
  const yStep = niceStep(peak, 5);
  const yMax = Math.ceil(peak / yStep) * yStep;
  const x = (shots) => pad.left + ((shots - (lowest - 0.5)) / (highest - lowest + 1)) * plotW;
  const y = (share) => pad.top + plotH - (share / yMax) * plotH;

  const svg = el("svg", {
    viewBox: `0 0 ${width} ${height}`,
    width,
    height,
    class: "chart-svg",
    role: "img",
    "aria-label": `Distribution of shots to finish for ${visible.map((ai) => ai.display_name).join(", ") || "no AI"}`,
  });

  // Grid and axes.
  const grid = el("g", { class: "chart-grid" }, svg);
  for (let share = 0; share <= yMax + 1e-9; share += yStep) {
    el("line", { x1: pad.left, x2: width - pad.right, y1: y(share), y2: y(share) }, grid);
    const label = el("text", { x: pad.left - 8, y: y(share) + 4, "text-anchor": "end", class: "chart-tick" }, svg);
    label.textContent = `${fmt(share, yStep < 1 ? 1 : 0)}%`;
  }
  const xStep = niceStep(highest - lowest, Math.max(3, Math.floor(plotW / 70)));
  for (let shots = Math.ceil(lowest / xStep) * xStep; shots <= highest; shots += xStep) {
    el("line", { x1: x(shots), x2: x(shots), y1: pad.top + plotH, y2: pad.top + plotH + 5, class: "chart-axis" }, svg);
    const label = el("text", { x: x(shots), y: pad.top + plotH + 19, "text-anchor": "middle", class: "chart-tick" }, svg);
    label.textContent = String(shots);
  }
  el("line", { x1: pad.left, x2: width - pad.right, y1: pad.top + plotH, y2: pad.top + plotH, class: "chart-axis" }, svg);
  const xTitle = el("text", { x: pad.left + plotW / 2, y: height - 4, "text-anchor": "middle", class: "chart-title" }, svg);
  xTitle.textContent = "Shots to finish (fewer is better)";

  // One step line per AI, and its mean.
  for (const ai of [...visible].reverse()) {
    const colour = palette[ai.name];
    let d = `M ${x(lowest - 0.5)} ${y(0)}`;
    for (let shots = lowest; shots <= highest; shots += 1) {
      const top = y(shares[ai.name].get(shots) ?? 0);
      d += ` V ${top} H ${x(shots + 0.5)}`;
    }
    d += ` V ${y(0)}`;
    el("path", { d, class: "chart-line", stroke: colour }, svg);
    el("line", { x1: x(ai.mean), x2: x(ai.mean), y1: pad.top, y2: pad.top + plotH, class: "chart-mean", stroke: colour }, svg);
  }

  // Hover guide.
  const guide = el("line", { y1: pad.top, y2: pad.top + plotH, class: "chart-guide", visibility: "hidden" }, svg);
  const overlay = el("rect", { x: pad.left, y: pad.top, width: plotW, height: plotH, class: "chart-overlay" }, svg);

  const point = (event) => {
    const box = svg.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * width;
    const shots = Math.round(lowest - 0.5 + ((px - pad.left) / plotW) * (highest - lowest + 1));
    return Math.min(highest, Math.max(lowest, shots));
  };
  const showReadout = (event) => {
    if (!visible.length) return;
    const shots = point(event);
    guide.setAttribute("x1", x(shots));
    guide.setAttribute("x2", x(shots));
    guide.setAttribute("visibility", "visible");
    els.readout.innerHTML =
      `<span class="readout-title">${shots} shots</span>` +
      visible
        .map((ai) => {
          const share = shares[ai.name].get(shots) ?? 0;
          return `<span class="readout-row"><span class="swatch" style="--colour:${palette[ai.name]}"></span>${escape(ai.display_name)}<span>${fmt(share)}%</span></span>`;
        })
        .join("");
    els.readout.hidden = false;
    const left = (x(shots) / width) * els.chart.clientWidth;
    const flip = left > els.chart.clientWidth / 2;
    els.readout.style.left = flip ? "" : `${left + 12}px`;
    els.readout.style.right = flip ? `${els.chart.clientWidth - left + 12}px` : "";
  };
  const hideReadout = () => {
    guide.setAttribute("visibility", "hidden");
    els.readout.hidden = true;
  };
  overlay.addEventListener("pointermove", showReadout);
  overlay.addEventListener("pointerdown", showReadout);
  overlay.addEventListener("pointerleave", hideReadout);

  els.chart.querySelector("svg")?.remove();
  els.readout.hidden = true;
  els.chart.prepend(svg);
}

// ---------- Explanations ----------

function renderExplanations(data, palette) {
  els.explanations.replaceChildren(
    ...data.ais.map((ai) => {
      const card = document.createElement("article");
      card.className = "ai-card";
      card.style.setProperty("--colour", palette[ai.name]);
      card.innerHTML = `
        <h3 class="ai-card-title">${escape(ai.display_name)}</h3>
        <p class="ai-card-mean"><span class="challenge-number">${fmt(ai.mean)}</span> shots on average</p>
        <p class="ai-card-text">${escape(ai.explanation || "No explanation available.")}</p>`;
      return card;
    }),
  );
}

// ---------- Page ----------

function show(name) {
  current = name;
  const data = results[name];
  const palette = colours(data.ais);
  const url = new URL(location.href);
  if (name === "standard") url.searchParams.delete("config");
  else url.searchParams.set("config", name);
  history.replaceState(null, "", url);

  renderMethod(data);
  renderSwitch();
  renderTable(data, palette);
  renderLegend(data, palette);
  els.content.hidden = false;
  renderChart(data, palette);
  renderExplanations(data, palette);
}

async function init() {
  const fetched = await Promise.allSettled(CONFIGS.map((name) => api.stats(name)));
  fetched.forEach((outcome, i) => {
    if (outcome.status === "fulfilled") results[CONFIGS[i]] = outcome.value;
  });
  const wanted = new URLSearchParams(location.search).get("config") ?? "standard";
  const first = results[wanted] ? wanted : CONFIGS.find((name) => results[name]);
  if (!first) {
    els.method.textContent = "";
    els.error.textContent = "No benchmark results yet. Run the benchmark first.";
    els.error.hidden = false;
    return;
  }
  show(first);

  let lastWidth = els.chart.clientWidth;
  new ResizeObserver(() => {
    if (els.chart.clientWidth === lastWidth || !current) return;
    lastWidth = els.chart.clientWidth;
    renderChart(results[current], colours(results[current].ais));
  }).observe(els.chart);
}

init();
