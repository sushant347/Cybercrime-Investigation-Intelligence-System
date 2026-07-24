/**
 * Turns the engine's investigation report into a plain-language summary.
 *
 * This is presentation only: every number and sentence comes from a stored
 * engine artifact. Nothing is scored, inferred, or invented here - the mapping
 * just chooses friendlier labels and adds a short "what this means" line so the
 * report is readable by someone who is not a forensic analyst.
 *
 * The on-screen report and the downloadable file are both rendered from this
 * one model so they can never drift apart.
 */
import type { ArtifactDocument, CasePriority, InvestigationReport } from "@/types";

export interface SummaryRow {
  label: string;
  value: string;
  /** Renders as a coloured pill (verdicts and counts), like a scan result. */
  badge?: "good" | "warn" | "bad" | "neutral";
  /** Optional one-line explanation shown under the value. */
  hint?: string;
}

export interface EvidenceRow {
  file: string;
  evidenceId: string;
  acquired: string;
  textConfidence: string;
  integrity: string;
  integrityOk: boolean;
}

export interface ConnectionRow {
  pair: string;
  strength: string;
  confidence: string;
  meaning: string;
}

export interface SimpleReport {
  caseId: string;
  caseReference: string;
  title: string;
  generatedAt: string;
  reportVersion: number;
  summary: SummaryRow[];
  findings: string[];
  evidence: EvidenceRow[];
  connections: ConnectionRow[];
  progression: string[];
  nextSteps: string[];
}

const PRIORITY_BADGE: Record<string, SummaryRow["badge"]> = {
  CRITICAL: "bad",
  HIGH: "bad",
  MEDIUM: "warn",
  LOW: "good",
};

/** Engine stores sections with no input data as an explanatory string. */
function structured<T>(section: T | string | null | undefined): T | null {
  return section && typeof section === "object" ? (section as T) : null;
}

function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function humanDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function titleCaseStage(stage: string): string {
  return stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Plain-language gloss for a correlation strength band. */
function strengthMeaning(strength: string): string {
  switch (strength.toUpperCase()) {
    case "STRONG":
      return "These two items are very likely part of the same activity.";
    case "MODERATE":
      return "These two items share enough in common to be treated as related.";
    case "WEAK":
      return "These two items show a slight link — treat as a lead, not proof.";
    default:
      return "The engine recorded a link between these two items.";
  }
}

export function buildSimpleReport(
  document: ArtifactDocument<InvestigationReport>,
  priority: CasePriority | undefined,
  caseReference: string,
): SimpleReport {
  const sections = document.report.sections;
  const overview = sections.case_overview;
  const correlation = structured<{
    pair_count: number;
    related_pair_count: number;
    top_relationships: {
      pair: string;
      strength: string;
      confidence: number;
      explanation: string;
    }[];
  }>(sections.correlation_analysis);
  const timeline = structured<{
    summary: string;
    stage_progression: string[];
    progression_consistent: boolean;
  }>(sections.timeline_analysis);
  const quality = structured<Record<string, number>>(sections.evidence_quality_summary);
  const evidenceRows = Array.isArray(sections.evidence_summary) ? sections.evidence_summary : [];

  const verifiedCount = evidenceRows.filter((row) => row.hash_verified).length;
  const allVerified = evidenceRows.length > 0 && verifiedCount === evidenceRows.length;

  const summary: SummaryRow[] = [
    { label: "Case Reference", value: caseReference || "—" },
    { label: "Case ID", value: document.case_id },
    { label: "Evidence Items", value: String(overview.evidence_count) },
    {
      label: "File Types",
      value: overview.file_types.length ? overview.file_types.join(", ") : "—",
    },
    { label: "First Evidence Added", value: humanDate(overview.first_evidence) },
    { label: "Last Evidence Added", value: humanDate(overview.last_evidence) },
    { label: "Analysis Run", value: humanDate(document.generated_at) },
  ];

  if (priority) {
    summary.push({
      label: "Case Priority",
      value: `${priority.priority_level} — ${priority.priority_score}/100`,
      badge: PRIORITY_BADGE[priority.priority_level] ?? "neutral",
      hint: priority.investigation_recommendation,
    });
  }

  summary.push({
    label: "Evidence Integrity",
    value: `${verifiedCount}/${evidenceRows.length} verified`,
    badge: allVerified ? "good" : "bad",
    hint: allVerified
      ? "Every file still matches the fingerprint taken when it was added — nothing was altered."
      : "At least one file does not match its original fingerprint.",
  });

  if (correlation) {
    summary.push({
      label: "Linked Evidence Pairs",
      value: `${correlation.related_pair_count} of ${correlation.pair_count} compared`,
      badge: correlation.related_pair_count > 0 ? "warn" : "neutral",
      hint:
        correlation.related_pair_count > 0
          ? "The engine found evidence items that appear to belong to the same activity."
          : "No links were found between the evidence items.",
    });
  }

  if (quality && typeof quality.mean_ocr_confidence === "number") {
    summary.push({
      label: "Text Recognition Quality",
      value: percent(quality.mean_ocr_confidence),
      badge: quality.mean_ocr_confidence >= 0.85 ? "good" : "warn",
      hint: "How confident the engine is in the text it read from the evidence.",
    });
  }

  // The executive summary and the conclusion overlap (both restate the
  // chain-of-custody count), so near-identical lines are collapsed.
  const seen = new Set<string>();
  const findings = [
    ...(sections.executive_summary ?? []),
    ...(sections.investigation_conclusion ?? []),
  ]
    // Artifact filenames are an implementation detail; drop them for readability.
    .map((line) => line.replace(/\s*\[[a-z_]+\.json\]/gi, "").trim())
    .filter((line) => {
      if (!line) return false;
      const key = line.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

  return {
    caseId: document.case_id,
    caseReference,
    title: overview.case_id === document.case_id ? caseReference : caseReference,
    generatedAt: document.generated_at,
    reportVersion: document.report_version,
    summary,
    findings,
    evidence: evidenceRows.map((row) => ({
      file: row.file_name,
      evidenceId: row.evidence_id,
      acquired: humanDate(row.upload_time),
      textConfidence: percent(row.ocr_confidence),
      integrity: row.hash_verified ? "Verified" : "FAILED",
      integrityOk: row.hash_verified,
    })),
    connections: (correlation?.top_relationships ?? []).map((rel) => ({
      pair: rel.pair,
      strength: rel.strength,
      confidence: percent(rel.confidence),
      meaning: strengthMeaning(rel.strength),
    })),
    progression: (timeline?.stage_progression ?? []).map(titleCaseStage),
    nextSteps: sections.recommendations ?? [],
  };
}
