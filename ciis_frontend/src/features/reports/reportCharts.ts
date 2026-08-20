/**
 * Deterministic SVG diagrams for the investigation report.
 *
 * Everything is drawn from values already present in the report model —
 * nothing is computed or inferred here. No charting library is used: the
 * output must be self-contained inline SVG that survives being embedded in
 * an emailed/archived HTML file with no network access.
 */
import type { ConnectionRow, EvidenceRow, ModelPredictionRow } from "./reportModel";

/**
 * Every colour is emitted as a CSS variable with its printed-document value as
 * the fallback.
 *
 * These diagrams were drawn in fixed ink — near-black labels, a near-white bar
 * track — which is right for paper and unreadable on the application's dark
 * surfaces: the evidence ids beside each bar were the same tone as the page
 * behind them. The consumer sets the variables from the active theme; anything
 * embedding this SVG without them still gets the original document palette.
 */
const ink = (fallback: string, token: string) => `var(--ciis-chart-${token}, ${fallback})`;

const INK = ink("#1f2937", "ink");
const MUTED = ink("#4a5568", "muted");
const TRACK = ink("#edf2f7", "track");
const NODE_FILL = ink("#f0fdf4", "node-fill");
const NODE_STROKE = ink("#14532d", "node-stroke");
const WEAK_LINE = ink("#4a5568", "weak");

const STRONG_LINE = ink("#b3261e", "strong");
const MODERATE_LINE = ink("#a86612", "moderate");
const GOOD_BAR = ink("#1a7f5a", "good");

const STRENGTH_COLOR: Record<string, string> = {
  STRONG: STRONG_LINE,
  MODERATE: MODERATE_LINE,
  WEAK: WEAK_LINE,
};

const STRENGTH_WIDTH: Record<string, number> = {
  STRONG: 3,
  MODERATE: 2,
  WEAK: 1.2,
};

function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Shorten an evidence id for node labels: EVD_20260725_001 -> …_001. */
function shortId(id: string): string {
  return id.length <= 12 ? id : `…${id.slice(-8)}`;
}

/**
 * Evidence-correlation network: every evidence item is a node on a circle,
 * every correlated pair an edge coloured/weighted by relationship strength.
 */
export function connectionDiagramSvg(
  evidence: EvidenceRow[],
  connections: ConnectionRow[],
): string {
  const ids = evidence.map((e) => e.evidenceId);
  // Include ids that only appear in connections (defensive completeness).
  for (const c of connections) {
    for (const id of [c.from, c.to]) {
      if (id && !ids.includes(id)) ids.push(id);
    }
  }
  if (ids.length === 0) return "";

  const width = 640;
  const height = Math.max(240, Math.min(360, 140 + ids.length * 26));
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(cx, cy) - 56;

  const pos = new Map<string, { x: number; y: number }>();
  ids.forEach((id, i) => {
    // Start at 12 o'clock and distribute evenly.
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / ids.length;
    pos.set(id, {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    });
  });

  const edges = connections
    .map((c) => {
      const a = pos.get(c.from);
      const b = pos.get(c.to);
      if (!a || !b) return "";
      const color = STRENGTH_COLOR[c.strength.toUpperCase()] ?? WEAK_LINE;
      const strokeWidth = STRENGTH_WIDTH[c.strength.toUpperCase()] ?? 1.5;
      const midX = (a.x + b.x) / 2;
      const midY = (a.y + b.y) / 2;
      return (
        `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" ` +
        `x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" ` +
        `stroke="${color}" stroke-width="${strokeWidth}" stroke-opacity="0.75"/>` +
        `<text x="${midX.toFixed(1)}" y="${(midY - 5).toFixed(1)}" ` +
        `text-anchor="middle" font-size="9" fill="${color}">${esc(c.confidence)}</text>`
      );
    })
    .join("");

  const nodes = ids
    .map((id) => {
      const p = pos.get(id);
      if (!p) return "";
      const labelY = p.y > cy ? p.y + 26 : p.y - 18;
      return (
        `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="11" ` +
        `fill="${NODE_FILL}" stroke="${NODE_STROKE}" stroke-width="1.6"/>` +
        `<text x="${p.x.toFixed(1)}" y="${(p.y + 3.5).toFixed(1)}" text-anchor="middle" ` +
        `font-size="8.5" font-weight="700" fill="${NODE_STROKE}">E</text>` +
        `<text x="${p.x.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="middle" ` +
        `font-size="9.5" font-family="ui-monospace,monospace" fill="${INK}">${esc(shortId(id))}</text>`
      );
    })
    .join("");

  const legend =
    `<g font-size="9.5" fill="${MUTED}">` +
    `<line x1="16" y1="${height - 14}" x2="40" y2="${height - 14}" stroke="${STRONG_LINE}" stroke-width="3"/>` +
    `<text x="46" y="${height - 10.5}">Strong</text>` +
    `<line x1="92" y1="${height - 14}" x2="116" y2="${height - 14}" stroke="${MODERATE_LINE}" stroke-width="2"/>` +
    `<text x="122" y="${height - 10.5}">Moderate</text>` +
    `<line x1="182" y1="${height - 14}" x2="206" y2="${height - 14}" stroke="${WEAK_LINE}" stroke-width="1.2"/>` +
    `<text x="212" y="${height - 10.5}">Weak — labels show engine confidence</text>` +
    `</g>`;

  return (
    `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" ` +
    `role="img" aria-label="Evidence correlation diagram" ` +
    `style="width:100%;height:auto;max-width:${width}px">` +
    `${edges}${nodes}${legend}</svg>`
  );
}

/** Horizontal bar chart of a 0–1 (or 0–100) metric per labelled row. */
function barChart(
  rows: { label: string; value: number | null; display: string; color: string }[],
  axisNote: string,
): string {
  if (rows.length === 0) return "";
  const rowH = 26;
  const top = 8;
  const labelW = 170;
  const width = 640;
  const barMaxW = width - labelW - 92;
  const height = top + rows.length * rowH + 24;

  const bars = rows
    .map((r, i) => {
      const y = top + i * rowH;
      const frac = r.value === null ? 0 : Math.max(0, Math.min(1, r.value));
      const barW = Math.max(2, frac * barMaxW);
      return (
        `<text x="${labelW - 8}" y="${y + 15}" text-anchor="end" font-size="10" ` +
        `font-family="ui-monospace,monospace" fill="${INK}">${esc(r.label)}</text>` +
        `<rect x="${labelW}" y="${y + 4}" width="${barMaxW}" height="14" rx="3" fill="${TRACK}"/>` +
        `<rect x="${labelW}" y="${y + 4}" width="${barW.toFixed(1)}" height="14" rx="3" fill="${r.color}"/>` +
        `<text x="${labelW + barMaxW + 8}" y="${y + 15}" font-size="10" fill="${INK}">${esc(r.display)}</text>`
      );
    })
    .join("");

  return (
    `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" ` +
    `role="img" style="width:100%;height:auto;max-width:${width}px">` +
    `${bars}` +
    `<text x="${labelW}" y="${height - 6}" font-size="9" fill="${MUTED}">${esc(axisNote)}</text>` +
    `</svg>`
  );
}

/** OCR text-recognition confidence per evidence item. */
export function ocrConfidenceSvg(evidence: EvidenceRow[]): string {
  const rows = evidence
    .filter((e) => e.textConfidenceValue !== null)
    .map((e) => ({
      label: shortId(e.evidenceId),
      value: e.textConfidenceValue,
      display: e.textConfidence,
      color: (e.textConfidenceValue ?? 0) >= 0.85 ? GOOD_BAR : MODERATE_LINE,
    }));
  return barChart(
    rows,
    "Engine confidence in the text read from each item (Phase-1 OCR).",
  );
}

/** Threat-model risk score per classified indicator. */
export function predictionRiskSvg(predictions: ModelPredictionRow[]): string {
  const rows = predictions
    .filter((p) => p.riskValue !== null)
    .slice(0, 12)
    .map((p) => ({
      label: p.indicator.length > 26 ? `${p.indicator.slice(0, 24)}…` : p.indicator,
      value: (p.riskValue ?? 0) / 100,
      display: p.risk,
      color: p.verdictBad ? STRONG_LINE : GOOD_BAR,
    }));
  return barChart(
    rows,
    "Risk score (0–100) assigned by the threat model to each URL/domain found in the evidence.",
  );
}
