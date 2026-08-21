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
import type {
  ArtifactDocument,
  CasePriority,
  InvestigationReport,
  ReportLegalBasisSection,
  ReportModelPrediction,
} from "@/types";

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
  /** Numeric OCR confidence (0–1) for chart rendering; null when unknown. */
  textConfidenceValue: number | null;
  integrity: string;
  integrityOk: boolean;
  entityCount: number;
}

/**
 * One weighted reason a pair was linked, as the correlation engine recorded it.
 *
 * `contribution` is this factor's share of the pair's total weight — how
 * identifying the kind of match is, times how rare the shared values are. The
 * shares sum to `ConnectionRow.weight`, and the confidence is that total on a
 * saturating scale.
 */
export interface ConnectionFactor {
  factor: string;
  label: string;
  detail: string;
  contribution: number;
  type_weight: number;
  matches: number;
}

export interface ConnectionRow {
  pair: string;
  /** The two evidence ids, split out for diagram rendering. */
  from: string;
  to: string;
  strength: string;
  confidence: string;
  /** Numeric confidence (0–1) for diagram rendering; null when unknown. */
  confidenceValue: number | null;
  meaning: string;
  /** Stored correlation-engine explanation, shown without reinterpretation. */
  basis: string;
  /** Summed factor contributions; null in reports stored before this existed. */
  weight: number | null;
  /** Empty for those older reports, which fall back to `basis`. */
  factors: ConnectionFactor[];
}

export interface TimelineEventRow {
  timestamp: string;
  evidenceId: string;
  file: string;
  source: string;
  confidence: string;
  inferred: boolean;
  fallback: boolean;
  stages: string[];
  critical: boolean;
}

export interface ModelPredictionRow {
  indicator: string;
  evidenceId: string;
  verdict: string;
  verdictBad: boolean;
  risk: string;
  /** Numeric risk (0–100) for chart rendering; null when unknown. */
  riskValue: number | null;
  confidence: string;
  model: string;
  /**
   * Domain facts behind the verdict (domain, age, registrar, SPF/DMARC, …),
   * already formatted for display. Empty when the active provider supplied
   * none — the static indicator file supplies none of it.
   */
  facts: PredictionFact[];
  /** Plain-language reasons the model gave, verbatim. */
  reasons: string[];
  /** Negative security indicators, verbatim. */
  threatSignals: string[];
}

export interface PredictionFact {
  label: string;
  value: string;
  /** True when this fact is itself a warning sign (missing SPF, young domain). */
  bad?: boolean;
}

export interface ProvenanceInfo {
  reportId: string;
  generator: string;
  evidenceSetDigest: string;
  artifactHashes: { name: string; digest: string }[];
}

export interface LinkedCaseRow {
  caseId: string;
  strength: string;
  confidence: string;
  /**
   * Kept structured rather than pre-joined into prose. Flattening these to
   * "bank account 0501…, domain esewa…, money npr 1500, …" produced a
   * 29-item lowercase run-on sentence in a table cell — every shared
   * identifier present, none of them findable.
   */
  sharedEntities: { entityType: string; value: string }[];
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
  linkedCases: LinkedCaseRow[];
  modelPredictions: ModelPredictionRow[];
  modelPredictionsNote: string | null;
  methodology: string[];
  /**
   * What the run set out to do, what it covered, and what re-running it
   * reproduces. Stored beside the stage list and printed in the PDF, but
   * previously dropped on screen — leaving the stages without the statement
   * of scope that qualifies them.
   */
  methodologyScope: {
    objective: string;
    evidenceScope: string;
    reproducibility: string;
  };
  progression: string[];
  timelineEvents: TimelineEventRow[];
  timelineReliability: string | null;
  limitations: string[];
  nextSteps: string[];
  legalBasis: ReportLegalBasisSection | null;
  provenance: ProvenanceInfo | null;
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

/**
 * Name the classifier behind a verdict, readably.
 *
 * The engine reports the source as `ml:xgboost` and the model version from the
 * trained model's own metadata — which defaults to the literal string
 * "unknown" when the model file records no version. Printed straight through,
 * that produced "ml:xgboost (unknown)", which reads like a failure rather than
 * "this model file does not state its version". A missing version is now
 * simply not shown, and the `ml:` prefix becomes words.
 */
export function describeModel(
  source: string,
  modelVersion: string | null | undefined,
): string {
  const raw = (source || "").trim();
  const mlMatch = /^ml:(.+)$/i.exec(raw);
  const name = mlMatch
    ? `${mlMatch[1].toUpperCase()} model`
    : raw || "Unrecorded source";

  const version = (modelVersion || "").trim();
  const versionIsKnown = version && !/^(unknown|none|n\/a|null)$/i.test(version);
  return versionIsKnown ? `${name} v${version}` : name;
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
/**
 * One plain sentence per relationship band.
 *
 * The engine's bands are NO_RELATIONSHIP / WEAK / MEDIUM / STRONG /
 * VERY_STRONG. Two of those had no case here — MEDIUM was spelled "MODERATE"
 * and VERY_STRONG was missing entirely — so the two ends of the scale that
 * matter most both fell through to the generic default. "MODERATE" is kept as
 * an alias in case a deployment configures its bands under that name.
 */
function strengthMeaning(strength: string): string {
  switch (strength.toUpperCase()) {
    case "VERY_STRONG":
      return "Several independent identifiers match — these two items almost certainly belong to the same activity.";
    case "STRONG":
      return "These two items are very likely part of the same activity.";
    case "MEDIUM":
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
      /** Absent in reports stored before the factors were carried through. */
      weight?: number;
      factors?: ConnectionFactor[];
    }[];
  }>(sections.correlation_analysis);
  const timeline = structured<{
    summary: string;
    stage_progression: string[];
    progression_consistent: boolean;
    timestamp_quality?: { reliability_note?: string };
    chronological_events?: {
      timestamp: string;
      evidence_id: string;
      file_name: string;
      timestamp_source: string;
      timestamp_confidence: number | string;
      timestamp_inferred: boolean;
      stages: string[];
      critical: boolean;
    }[];
  }>(sections.timeline_analysis);
  const quality = structured<Record<string, number>>(sections.evidence_quality_summary);
  const crossCase = structured<{
    related_case_ids: string[];
    links: {
      other_case_id: string;
      relationship_strength: string;
      match_confidence: number;
      matched_entities: { entity_type: string; value: string }[];
    }[];
  }>(sections.cross_case_correlation);
  const evidenceRows = Array.isArray(sections.evidence_summary) ? sections.evidence_summary : [];
  const scope = structured<{
    objective: string;
    evidence_scope: string;
    methodology: string[];
    reproducibility: string;
  }>(sections.scope_and_methodology);
  const predictions = structured<{
    indicators_classified: number;
    flagged_malicious: number;
    predictions: ReportModelPrediction[];
  }>(sections.model_predictions);
  const provenanceSection = structured<{
    report_id: string;
    generator: string;
    evidence_set_digest: string;
    source_artifact_hashes: Record<string, string>;
  }>(sections.report_provenance);

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

  if (predictions) {
    summary.push({
      label: "Threat Model Verdicts",
      value: `${predictions.flagged_malicious} malicious of ${predictions.indicators_classified} classified`,
      badge: predictions.flagged_malicious > 0 ? "bad" : "good",
      hint:
        predictions.flagged_malicious > 0
          ? "The URL classifier flagged indicators in this case as malicious — details in Model Prediction Results."
          : "No URL or domain in the evidence was classified as malicious.",
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

  const linkedCases: LinkedCaseRow[] = (crossCase?.links ?? []).map((link) => ({
    caseId: link.other_case_id,
    strength: link.relationship_strength,
    confidence: percent(link.match_confidence),
    sharedEntities: link.matched_entities.map((m) => ({
      entityType: m.entity_type,
      value: m.value,
    })),
  }));

  if (crossCase) {
    summary.push({
      label: "Linked Other Cases",
      value: linkedCases.length
        ? `${linkedCases.length} — ${crossCase.related_case_ids.join(", ")}`
        : "None",
      badge: linkedCases.length ? "warn" : "neutral",
      hint: linkedCases.length
        ? "This case shares entities (phones, wallets, URLs…) with other cases in the system."
        : "No entities from this case were seen in any other case.",
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
    linkedCases,
    evidence: evidenceRows.map((row) => ({
      file: row.file_name,
      evidenceId: row.evidence_id,
      acquired: humanDate(row.upload_time),
      textConfidence: percent(row.ocr_confidence),
      textConfidenceValue:
        typeof row.ocr_confidence === "number" ? row.ocr_confidence : null,
      integrity: row.hash_verified ? "Verified" : "FAILED",
      integrityOk: row.hash_verified,
      entityCount: row.entity_count,
    })),
    connections: (correlation?.top_relationships ?? []).map((rel) => {
      const [from = "", to = ""] = rel.pair.split("<->").map((s) => s.trim());
      return {
        pair: rel.pair,
        from,
        to,
        strength: rel.strength,
        confidence: percent(rel.confidence),
        confidenceValue:
          typeof rel.confidence === "number" ? rel.confidence : null,
        meaning: strengthMeaning(rel.strength),
        basis: rel.explanation,
        weight: typeof rel.weight === "number" ? rel.weight : null,
        factors: rel.factors ?? [],
      };
    }),
    modelPredictions: (predictions?.predictions ?? []).map((p) => ({
      indicator: p.indicator,
      evidenceId: p.evidence_id,
      verdict: p.verdict.toUpperCase(),
      verdictBad: ["malicious", "phishing", "suspicious"].includes(
        p.verdict.toLowerCase(),
      ),
      risk: p.risk_score === null || p.risk_score === undefined ? "—" : `${p.risk_score}/100`,
      riskValue:
        typeof p.risk_score === "number" ? p.risk_score : null,
      confidence: percent(p.confidence),
      model: describeModel(p.source, p.model_version),
      // "Only the necessary info": the facts an investigator would cite,
      // as label/value pairs. Anything the provider did not supply is
      // simply absent rather than rendered as an empty or zero field.
      facts: [
        p.domain ? { label: "Domain", value: p.domain } : null,
        p.ip_address ? { label: "Resolves to", value: p.ip_address } : null,
        typeof p.domain_age_days === "number"
          ? {
              label: "Domain age",
              value: `${p.domain_age_days} day${p.domain_age_days === 1 ? "" : "s"}`,
              bad: p.domain_age_days < 180,
            }
          : null,
        p.registrar ? { label: "Registrar", value: p.registrar } : null,
        p.hosting ? { label: "Hosted by", value: p.hosting } : null,
        p.ssl_status
          ? {
              label: "SSL",
              value:
                typeof p.ssl_days_left === "number"
                  ? `${p.ssl_status} (${p.ssl_days_left} days left)`
                  : p.ssl_status,
              bad: p.ssl_status.toUpperCase() !== "VALID",
            }
          : null,
        typeof p.spf_present === "boolean"
          ? { label: "SPF", value: p.spf_present ? "present" : "missing", bad: !p.spf_present }
          : null,
        typeof p.dmarc_present === "boolean"
          ? {
              label: "DMARC",
              value: p.dmarc_present ? "present" : "missing",
              bad: !p.dmarc_present,
            }
          : null,
        p.brand_impersonated
          ? {
              label: "Brand",
              value: p.official_domain
                ? `${p.brand_impersonated} (official domain)`
                : `impersonates ${p.brand_impersonated}`,
              bad: !p.official_domain,
            }
          : null,
        typeof p.trust_score === "number"
          ? { label: "Trust", value: `${p.trust_score}/100`, bad: p.trust_score < 50 }
          : null,
      ].filter((f): f is PredictionFact => f !== null),
      reasons: p.reasons ?? [],
      threatSignals: p.threat_signals ?? [],
    })),
    modelPredictionsNote:
      typeof sections.model_predictions === "string"
        ? sections.model_predictions
        : null,
    methodology: scope?.methodology ?? [],
    methodologyScope: {
      objective: scope?.objective ?? "",
      evidenceScope: scope?.evidence_scope ?? "",
      reproducibility: scope?.reproducibility ?? "",
    },
    progression: (timeline?.stage_progression ?? []).map(titleCaseStage),
    timelineEvents: (timeline?.chronological_events ?? []).map((event) => ({
      timestamp: humanDate(event.timestamp),
      evidenceId: event.evidence_id,
      file: event.file_name,
      source: titleCaseStage(event.timestamp_source),
      confidence:
        typeof event.timestamp_confidence === "number"
          ? percent(event.timestamp_confidence)
          : String(event.timestamp_confidence || "—"),
      inferred: event.timestamp_inferred,
      fallback: event.timestamp_source === "upload_time_fallback",
      stages: (event.stages ?? []).map(titleCaseStage),
      critical: Boolean(event.critical),
    })),
    timelineReliability: timeline?.timestamp_quality?.reliability_note ?? null,
    limitations: Array.isArray(sections.limitations) ? sections.limitations : [],
    nextSteps: sections.recommendations ?? [],
    legalBasis: structured<ReportLegalBasisSection>(sections.legal_basis),
    provenance: provenanceSection
      ? {
          reportId: provenanceSection.report_id,
          generator: provenanceSection.generator,
          evidenceSetDigest: provenanceSection.evidence_set_digest,
          artifactHashes: Object.entries(
            provenanceSection.source_artifact_hashes ?? {},
          ).map(([name, digest]) => ({ name, digest })),
        }
      : null,
  };
}
