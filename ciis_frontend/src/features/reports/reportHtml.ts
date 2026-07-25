/**
 * Builds a standalone HTML file of the investigation report.
 *
 * Self-contained (inline CSS + inline SVG, no assets) so it can be emailed,
 * archived, or opened on a machine with no network — and printed to PDF from
 * the browser. Rendered from the same `SimpleReport` model and the same SVG
 * chart builders as the on-screen version, so the two can never drift apart.
 * Section numbering mirrors the on-screen view and the engine's native PDF.
 */
import type { SimpleReport } from "./reportModel";
import {
  connectionDiagramSvg,
  ocrConfidenceSvg,
  predictionRiskSvg,
} from "./reportCharts";

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
  let sectionNumber = 0;

  const section = (title: string, body: string) => {
    if (!body.trim()) return "";
    sectionNumber += 1;
    return `<section><h2>${sectionNumber}. ${escapeHtml(title)}</h2>${body}</section>`;
  };

  const numberedList = (items: string[]) =>
    items.length
      ? `<ol>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ol>`
      : "";

  const bulletList = (items: string[]) =>
    items.length
      ? `<ul>${items.map((i) => `<li>${escapeHtml(i)}</li>`).join("")}</ul>`
      : "";

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
        <td><strong>${escapeHtml(row.file)}</strong><div class="hint"><code>${escapeHtml(row.evidenceId)}</code></div></td>
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

  const linkedCaseRows = report.linkedCases
    .map(
      (row) => `
      <tr>
        <td><code>${escapeHtml(row.caseId)}</code></td>
        <td>${escapeHtml(row.strength)}</td>
        <td>${escapeHtml(row.confidence)}</td>
        <td>${escapeHtml(row.sharedEntities)}</td>
      </tr>`,
    )
    .join("");

  // Each indicator gets a second row carrying the domain facts and the
  // model's plain-language reasons, so the downloaded file says exactly what
  // the on-screen report says.
  const predictionRows = report.modelPredictions
    .map((row) => {
      const facts = row.facts
        .map(
          (f) =>
            `<span class="fact${f.bad ? " fact-bad" : ""}">${escapeHtml(f.label)}: ${escapeHtml(f.value)}</span>`,
        )
        .join("");
      const reasons = row.reasons.length
        ? `<ul class="reasons">${row.reasons
            .map((r) => `<li>${escapeHtml(r)}</li>`)
            .join("")}</ul>`
        : "";
      const detail =
        facts || reasons
          ? `<tr class="detail"><td colspan="5">${facts ? `<p class="facts">${facts}</p>` : ""}${reasons}</td></tr>`
          : "";
      return `
      <tr>
        <td><code>${escapeHtml(row.indicator)}</code></td>
        <td><span class="badge" style="background:${row.verdictBad ? BADGE_COLORS.bad : BADGE_COLORS.good}">${escapeHtml(row.verdict)}</span></td>
        <td>${escapeHtml(row.risk)}</td>
        <td>${escapeHtml(row.confidence)}</td>
        <td><code>${escapeHtml(row.model)}</code></td>
      </tr>${detail}`;
    })
    .join("");

  const progression = report.progression.length
    ? `<p class="stages">${report.progression
        .map((s, i) => `<span class="stage">${i + 1}. ${escapeHtml(s)}</span>`)
        .join('<span class="arrow">→</span>')}</p>`
    : "";

  const ocrChart = ocrConfidenceSvg(report.evidence);
  const networkChart = connectionDiagramSvg(report.evidence, report.connections);
  const riskChart = predictionRiskSvg(report.modelPredictions);

  const provenanceBlock = report.provenance
    ? `
    <div class="prov">
      <div>${escapeHtml(report.provenance.generator)}</div>
      <div class="mono">Evidence-set digest (SHA-256): ${escapeHtml(report.provenance.evidenceSetDigest)}</div>
      ${report.provenance.artifactHashes
        .map((h) => `<div class="mono">${escapeHtml(h.name)}: ${escapeHtml(h.digest)}</div>`)
        .join("")}
    </div>`
    : "";

  const reportIdHeader = report.provenance
    ? `<p class="rid">${escapeHtml(report.provenance.reportId)}</p>`
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
  .sheet{ max-width:880px; margin:0 auto; background:#fff; border:1px solid #dfe3e8;
          border-radius:10px; overflow:hidden; }
  header{ padding:26px 28px 20px; border-bottom:3px solid #14532d; }
  header .org{ margin:0; font-size:11.5px; text-transform:uppercase;
               letter-spacing:.1em; color:#4a5568; }
  header h1{ margin:4px 0 0; font-size:23px; color:#111827; }
  header p{ margin:6px 0 0; color:#4a5568; font-size:13.5px; }
  header .rid{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
               font-size:12px; color:#14532d; margin-top:8px; }
  section{ padding:22px 28px; border-top:1px solid #edf0f3; }
  h2{ margin:0 0 14px; font-size:15px; color:#14532d;
      text-transform:uppercase; letter-spacing:.05em; }
  table{ width:100%; border-collapse:collapse; }
  th,td{ padding:10px 12px; text-align:left; vertical-align:top;
         border-bottom:1px solid #edf0f3; font-size:13.5px; }
  tbody tr:last-child th, tbody tr:last-child td{ border-bottom:0; }
  th{ width:34%; color:#48566a; font-weight:600; background:#fafbfc; }
  thead th{ width:auto; background:#f0fdf4; color:#14532d;
            font-size:11.5px; text-transform:uppercase; letter-spacing:.04em;
            border-bottom:2px solid #14532d; }
  .badge{ display:inline-block; padding:3px 10px; border-radius:999px;
          color:#fff; font-size:12px; font-weight:700; }
  .hint{ margin-top:4px; color:#68758a; font-size:12.5px; }
  tr.detail td{ padding-top:0; border-top:0; }
  .facts{ margin:0 0 6px; }
  .fact{ display:inline-block; margin:0 6px 4px 0; padding:2px 8px;
         border:1px solid #cbd5e1; border-radius:999px; font-size:11.5px;
         color:#334155; }
  .fact-bad{ border-color:#b3261e; color:#b3261e; }
  .reasons{ margin:0; padding-left:20px; color:#68758a; font-size:12px; }
  .reasons li{ margin-bottom:3px; }
  ul,ol{ margin:0; padding-left:22px; }
  li{ margin-bottom:8px; }
  code{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12.5px; }
  .chart{ margin-top:14px; }
  .note{ color:#4a5568; font-size:13px; margin:0 0 12px; }
  .stages{ margin:0; }
  .stage{ display:inline-block; background:#e8f5f0; color:#14532d; border-radius:6px;
          padding:4px 10px; margin:3px 0; font-size:13.5px; font-weight:600; }
  .stage:first-child{ background:#14532d; color:#fff; }
  .arrow{ margin:0 7px; color:#9aa5b5; }
  footer{ padding:18px 28px; color:#68758a; font-size:12px; background:#fafbfc;
          border-top:1px solid #edf0f3; }
  .prov .mono, .mono{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
          font-size:10.5px; word-break:break-all; color:#4a5568; margin-top:3px; }
  .sig{ display:flex; gap:40px; margin-top:22px; padding-top:14px;
        border-top:1px solid #dfe3e8; }
  .sig div{ flex:1; font-size:12px; color:#1f2937; }
  .sig .line{ margin-top:34px; border-top:1px solid #4a5568; padding-top:4px;
              color:#68758a; }
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
    <p class="org">Cybercrime Investigation Intelligence Engine</p>
    <h1>Investigation Report</h1>
    <p>Case &ldquo;${escapeHtml(report.caseReference || report.caseId)}&rdquo; · report version ${report.reportVersion} — assembled from stored, hash-verified findings only</p>
    ${reportIdHeader}
  </header>

  ${section("Case Summary", `<table><tbody>${summaryRows}</tbody></table>`)}
  ${section("Key Findings", numberedList(report.findings))}
  ${
    evidenceRows
      ? section(
          "Evidence & Chain of Custody",
          `<table><thead><tr><th>File</th><th>Added</th><th>Text Read</th><th>Integrity</th></tr></thead><tbody>${evidenceRows}</tbody></table>` +
            (ocrChart ? `<div class="chart">${ocrChart}</div>` : ""),
        )
      : ""
  }
  ${
    connectionRows
      ? section(
          "How the Evidence Connects",
          (networkChart ? `<div class="chart">${networkChart}</div>` : "") +
            `<table><thead><tr><th>Items</th><th>Strength</th><th>Confidence</th><th>What This Means</th></tr></thead><tbody>${connectionRows}</tbody></table>`,
        )
      : ""
  }
  ${
    linkedCaseRows
      ? section(
          "Cross-Case Correlation",
          `<p class="note">Identifiers from this case (phones, wallets, URLs…) were also observed in the cases below — these investigations may be related.</p>` +
            `<table><thead><tr><th>Case</th><th>Strength</th><th>Confidence</th><th>Shared With This Case</th></tr></thead><tbody>${linkedCaseRows}</tbody></table>`,
        )
      : ""
  }
  ${
    predictionRows
      ? section(
          "Model Prediction Results",
          `<p class="note">Every URL and domain found in the evidence, classified by the threat model. Verdicts are recorded verbatim from the model output.</p>` +
            `<table><thead><tr><th>Indicator</th><th>Verdict</th><th>Risk</th><th>Model Confidence</th><th>Source Model</th></tr></thead><tbody>${predictionRows}</tbody></table>` +
            (riskChart ? `<div class="chart">${riskChart}</div>` : ""),
        )
      : report.modelPredictionsNote
        ? section(
            "Model Prediction Results",
            `<p class="note">${escapeHtml(report.modelPredictionsNote)}</p>`,
          )
        : ""
  }
  ${section("How the Scam Progressed", progression)}
  ${section("Methodology", bulletList(report.methodology))}
  ${section("Recommendations", numberedList(report.nextSteps))}

  <footer>
    Generated by the Cybercrime Investigation Intelligence Engine. Every figure
    in this report was produced by the analysis engine from the evidence listed
    above; no content is generated outside computed results.
    ${provenanceBlock}
    <div class="sig">
      <div>Prepared by (system)<div class="line">Automated Phase-2 reporting module</div></div>
      <div>Reviewed by (investigator)<div class="line">Date · Signature</div></div>
    </div>
  </footer>
</div>
</body>
</html>`;
}
