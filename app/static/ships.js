// Ship drawings as SVG strings. Pure drawing: nothing here knows a game rule.
//
// A hull is drawn top-down along the x axis, 100 units per square and 100 units wide,
// with the bow at the far end. A vertical ship is the same drawing turned a quarter turn
// so its bow points up.

const U = 100;

function hullPath(length) {
  const w = length * U;
  const taper = Math.min(110, 40 + length * 14);
  return [
    "M 16 24",
    `L ${w - taper} 24`,
    `C ${w - taper * 0.45} 24 ${w - 16} 38 ${w - 5} 50`,
    `C ${w - 16} 62 ${w - taper * 0.45} 76 ${w - taper} 76`,
    "L 16 76",
    "Q 7 76 7 66",
    "L 7 34",
    "Q 7 24 16 24 Z",
  ].join(" ");
}

function turret(cx, facing) {
  // A round turret with twin barrels pointing towards the bow (facing 1) or stern (-1).
  const tip = cx + facing * 34;
  return `
    <line class="barrel" x1="${cx}" y1="46" x2="${tip}" y2="46"/>
    <line class="barrel" x1="${cx}" y1="54" x2="${tip}" y2="54"/>
    <circle class="turret" cx="${cx}" cy="50" r="15"/>`;
}

function details(length) {
  const center = (i) => i * U + U / 2;
  if (length <= 1) {
    return `<rect class="deck" x="30" y="40" width="40" height="20" rx="4"/>`;
  }
  if (length === 2) {
    // Patrol boat: a cabin and a small gun on the foredeck.
    return `
      <rect class="deck" x="34" y="36" width="72" height="28" rx="5"/>
      <line class="detail" x1="50" y1="36" x2="50" y2="64"/>
      <circle class="turret" cx="${center(1) + 14}" cy="50" r="9"/>
      <line class="barrel" x1="${center(1) + 14}" y1="50" x2="${center(1) + 40}" y2="50"/>`;
  }
  // Bigger ships: superstructure amidships, a funnel behind it, turrets fore and aft.
  const bridge = Math.floor((length - 1) / 2);
  let out = `
    <rect class="deck" x="${center(bridge) - 34}" y="34" width="68" height="32" rx="4"/>
    <rect class="detail" x="${center(bridge) - 14}" y="42" width="28" height="16" rx="2"/>`;
  if (length >= 4) {
    out += `<rect class="funnel" x="${center(bridge) - 70}" y="40" width="26" height="20" rx="9"/>`;
  }
  for (let i = bridge + 1; i < length; i++) {
    if (i === length - 1 && length > 3) continue; // keep the bow clear on big ships
    out += turret(center(i) - (i === length - 1 ? 18 : 0), 1);
  }
  if (length >= 4) out += turret(center(0) + 8, -1);
  return out;
}

/** The SVG of one ship of `length` squares in `orientation` ("horizontal" or "vertical"). */
export function hullSvg(length, orientation = "horizontal") {
  const w = length * U;
  const vertical = orientation === "vertical";
  const viewBox = vertical ? `0 0 ${U} ${w}` : `0 0 ${w} ${U}`;
  // Quarter turn: (x, y) becomes (y, w - x), so the bow ends up at the top.
  const turn = vertical ? `transform="matrix(0 -1 1 0 0 ${w})"` : "";
  return `
    <svg class="hull" viewBox="${viewBox}" preserveAspectRatio="none" aria-hidden="true">
      <g ${turn}>
        <path class="hull-shape" d="${hullPath(length)}"/>
        <line class="keel" x1="22" y1="50" x2="${w - 30}" y2="50"/>
        ${details(length)}
      </g>
    </svg>`;
}

/** The large side elevation and plan of a battleship for the title screen. */
export function blueprintSvg() {
  return `
  <svg viewBox="0 0 1000 420" class="blueprint-svg" role="img" aria-label="Blueprint of a battleship">
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" class="bp-arrow"/>
      </marker>
    </defs>

    <!-- Side elevation -->
    <g class="bp-draw">
      <line class="bp-water" x1="40" y1="200" x2="960" y2="200"/>
      <path class="bp-hull" d="M 90 160 L 900 160 L 948 150 L 912 214 L 140 214 Q 100 214 90 190 Z"/>
      <line class="bp-thin" x1="110" y1="186" x2="925" y2="186"/>
      <!-- Aft turrets -->
      <path class="bp-part" d="M 190 160 L 196 142 L 256 142 L 262 160"/>
      <line class="bp-part" x1="196" y1="148" x2="140" y2="146"/>
      <line class="bp-part" x1="196" y1="153" x2="140" y2="152"/>
      <path class="bp-part" d="M 285 160 L 290 128 L 344 128 L 350 160"/>
      <line class="bp-part" x1="290" y1="136" x2="236" y2="134"/>
      <!-- Superstructure -->
      <path class="bp-part" d="M 380 160 L 380 120 L 470 120 L 470 98 L 560 98 L 560 120 L 640 120 L 640 160"/>
      <rect class="bp-part" x="486" y="70" width="58" height="28"/>
      <line class="bp-thin" x1="492" y1="80" x2="538" y2="80"/>
      <path class="bp-part" d="M 420 120 L 426 76 L 456 76 L 462 120"/>
      <line class="bp-part" x1="515" y1="70" x2="515" y2="18"/>
      <line class="bp-thin" x1="495" y1="34" x2="535" y2="34"/>
      <line class="bp-thin" x1="502" y1="48" x2="528" y2="48"/>
      <path class="bp-part" d="M 590 120 L 594 100 L 626 100 L 630 120"/>
      <!-- Forward turrets -->
      <path class="bp-part" d="M 672 160 L 678 128 L 732 128 L 738 160"/>
      <line class="bp-part" x1="732" y1="136" x2="790" y2="134"/>
      <path class="bp-part" d="M 770 160 L 776 142 L 836 142 L 842 160"/>
      <line class="bp-part" x1="836" y1="148" x2="900" y2="146"/>
      <line class="bp-part" x1="836" y1="153" x2="900" y2="152"/>
      <!-- Portholes -->
      ${Array.from({ length: 22 }, (_, i) => `<circle class="bp-thin" cx="${170 + i * 32}" cy="174" r="3"/>`).join("")}
    </g>

    <!-- Plan view -->
    <g class="bp-draw">
      <path class="bp-hull" d="M 110 290 L 820 290 C 880 290 930 310 950 330 C 930 350 880 370 820 370 L 110 370 Q 92 370 92 352 L 92 308 Q 92 290 110 290 Z"/>
      <line class="bp-thin" x1="100" y1="330" x2="940" y2="330" stroke-dasharray="14 6 3 6"/>
      <circle class="bp-part" cx="225" cy="330" r="20"/>
      <circle class="bp-part" cx="318" cy="330" r="22"/>
      <rect class="bp-part" x="390" y="306" width="240" height="48" rx="6"/>
      <rect class="bp-part" x="426" y="316" width="34" height="28" rx="12"/>
      <rect class="bp-part" x="486" y="314" width="58" height="32"/>
      <circle class="bp-part" cx="705" cy="330" r="22"/>
      <circle class="bp-part" cx="806" cy="330" r="20"/>
      <line class="bp-part" x1="725" y1="324" x2="770" y2="324"/>
      <line class="bp-part" x1="725" y1="336" x2="770" y2="336"/>
      <line class="bp-part" x1="826" y1="324" x2="870" y2="324"/>
      <line class="bp-part" x1="826" y1="336" x2="870" y2="336"/>
      <line class="bp-part" x1="205" y1="324" x2="160" y2="324"/>
      <line class="bp-part" x1="205" y1="336" x2="160" y2="336"/>
    </g>

    <!-- Dimensions and callouts -->
    <g class="bp-dim">
      <line x1="90" y1="236" x2="90" y2="252"/>
      <line x1="948" y1="236" x2="948" y2="252"/>
      <line x1="92" y1="244" x2="946" y2="244" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
      <text x="519" y="238" text-anchor="middle">L.O.A. 5 SQUARES</text>
      <line x1="975" y1="290" x2="975" y2="370" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
      <text x="984" y="334">1 SQ</text>
      <line x1="515" y1="18" x2="600" y2="18"/>
      <text x="606" y="22">MAST</text>
      <line x1="315" y1="128" x2="315" y2="70"/>
      <line x1="315" y1="70" x2="360" y2="70"/>
      <text x="366" y="74">TURRET B</text>
      <text x="40" y="196">WL</text>
      <text x="60" y="404" class="bp-caption">SIDE ELEVATION &amp; PLAN &middot; NOT TO BE SUNK</text>
    </g>
  </svg>`;
}
