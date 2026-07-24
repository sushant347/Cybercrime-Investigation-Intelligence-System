/**
 * Builds a standalone HTML file of the plain-language report.
 *
 * Self-contained (inline CSS, no assets) so it can be emailed, archived, or
 * opened on a machine with no network - and printed to PDF from the browser.
 * Rendered from the same `SimpleReport` model as the on-screen version.
 */
import type { SimpleReport } from "./reportModel";

const BADGE_COLORS: Record<string, string> = {
  good: "#1a7f5a",
  warn: "#a86612",
  bad: "#b3261e",
  neutral: "#4a5568",
};

/** Escape untrusted text: evidence file names come from user uploads. */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function buildReportHtml(report: SimpleReport): string {
  const summaryRows = report.summary
    .map(
      (row) => `
      <tr>
        <th>${escapeHtml(row.label)}</th>
        <td>
          ${
            row.badge
              ? `<span class="badge" style="background:${BADGE_COLORS[row.badge]}">${escapeHtml(row.value)}</span>`
              : escapeHtml(row.value)
          }
          ${row.hint ? `<div class="hint">${escapeHtml(row.hint)}</div>` : ""}
        </td>
      </tr>`,
    )
    .join("");

  const evidenceRows = report.evidence
    .map(
      (row) => `
      <tr>
        <td><strong>${escapeHtml(row.file)}</strong><div class="hint">${escapeHtml(row.evidenceId)}</div></td>
        <td>${escapeHtml(row.acquired)}</td>
        <td>${escapeHtml(row.textConfidence)}</td>
        <td><span class="badge" style="background:${row.integrityOk ? BADGE_COLORS.good : BADGE_COLORS.bad}">${escapeHtml(row.integrity)}</span></td>
      </tr>`,
    )
    .join("");

  const connectionRows = report.connections
    .map(
      (row) => `
      <tr>
        <td><code>${escapeHtml(row.pair)}</code></td>
        <td>${escapeHtml(row.strength)}</td>
        <td>${escapeHtml(row.confidence)}</td>
        <td>${escapeHtml(row.meaning)}</td>
      </tr>`,
    )
    .join("");

  const section = (title: string, body: string) =>
    body.trim() ? `<section><h2>${escapeHtml(title)}</h2>${body}</section>` : "";

  const list = (items: string[]) =>
    items.length ? `<ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>` : "";

  const progression = report.progression.length
    ? `<p class="stages">${report.progression.map((s) => `<span class="stage">${escapeHtml(s)}</span>`).join('<span class="arrow">→</span>')}</p>`
    : "";

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Investigation Report — ${escapeHtml(report.caseReference || report.caseId)}</title>
<style>
  *{ box-sizing: border-box; }
  body{ margin:0; padding:32px 16px; background:#f4f6f8; color:#1a202c;
        font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  .sheet{ max-width:860px; margin:0 auto; background:#fff; border:1px solid #dfe3e8;
          border-radius:10px; overflow:hidden; }
  header{ background:#1aa179; color:#fff; padding:22px 26px; }
  header h1{ margin:0; font-size:21px; }
  header p{ margin:6px 0 0; opacity:.92; font-size:13.5px; }
  section{ padding:22px 26px; border-top:1px solid #edf0f3; }
  h2{ margin:0 0 14px; font-size:16px; color:#12805f;
      text-transform:uppercase; letter-spacing:.04em; }
  table{ width:100%; border-collapse:collapse; }
  th,td{ padding:11px 12px; text-align:left; vertical-align:top;
         border-bottom:1px solid #edf0f3; font-size:14px; }
  tbody tr:last-child th, tbody tr:last-child td{ border-bottom:0; }
  th{ width:36%; color:#48566a; font-weight:600; background:#fafbfc; }
  thead th{ width:auto; background:#fafbfc; color:#48566a;
            font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  .badge{ display:inline-block; padding:3px 10px; border-radius:999px;
          color:#fff; font-size:12.5px; font-weight:700; }
  .hint{ margin-top:4px; color:#68758a; font-size:12.5px; }
  ul{ margin:0; padding-left:20px; }
  li{ margin-bottom:8px; }
  code{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:13px; }
  .stages{ margin:0; }
  .stage{ display:inline-block; background:#e8f5f0; color:#12805f; border-radius:6px;
          padding:4px 10px; margin:3px 0; font-size:13.5px; font-weight:600; }
  .arrow{ margin:0 7px; color:#9aa5b5; }
  footer{ padding:16px 26px; color:#68758a; font-size:12px; background:#fafbfc; }
  @media print{
    body{ background:#fff; padding:0; }
    .sheet{ border:0; border-radius:0; max-width:none; }
    section{ break-inside:avoid; }
  }
</style>
</head>
<body>
<div class="sheet">
  <header>
    <h1>Investigation Report</h1>
    <p>${escapeHtml(report.caseReference || report.caseId)} · report version ${report.reportVersion}</p>
  </header>

  <section>
    <h2>Report Summary</h2>
    <table><tbody>${summaryRows}</tbody></table>
  </section>

  ${section("What We Found", list(report.findings))}
  ${section("How The Scam Progressed", progression)}
  ${
    evidenceRows
      ? section(
          "Evidence Examined",
          `<table><thead><tr><th>File</th><th>Added</th><th>Text Read</th><th>Integrity</th></tr></thead><tbody>${evidenceRows}</tbody></table>`,
        )
      : ""
  }
  ${
    connectionRows
      ? section(
          "Links Between Evidence",
          `<table><thead><tr><th>Items</th><th>Strength</th><th>Confidence</th><th>What This Means</th></tr></thead><tbody>${connectionRows}</tbody></table>`,
        )
      : ""
  }
  ${section("Recommended Next Steps", list(report.nextSteps))}

  <footer>
    Generated by the Cybercrime Investigation Intelligence System.
    Every figure in this report was produced by the analysis engine from the
    evidence listed above.
  </footer>
</div>
</body>
</html>`;
}
