/**
 * Plain-language definitions for the forensic terminology the UI displays.
 *
 * The engine names its metrics for the people who built it ("forgery risk",
 * "correlation strength", "specificity"). An investigator opening a case for
 * the first time has no way to know that a *high* forgery risk is bad while a
 * *high* evidence confidence is good, or that specificity is about how rare a
 * value is rather than how certain the match is.
 *
 * Every definition here describes what the engine actually computes — the
 * wording is derived from the scoring code in
 * `timeline_report_engine/ciis_timeline_report/prioritization/service.py` and
 * the correlation/suspect services, not invented for the UI. Where a metric
 * has a direction (higher is better/worse) that is stated explicitly, because
 * it is the single most common misreading.
 */

export interface GlossaryEntry {
  /** Display name, already human-cased. */
  term: string;
  /** One sentence: what the number *is*. */
  definition: string;
  /** How to read it — scale, direction, and what a notable value means. */
  reading?: string;
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  // ---------------------------------------------------- priority components
  evidence_confidence: {
    term: "Evidence Confidence",
    definition:
      "How reliable the automated reading of the evidence was — averaged across every item in the case.",
    reading:
      "0–100, higher is better. Low values usually mean poor scan quality or text the reader struggled with, so findings drawn from that item deserve a manual check.",
  },
  threat_intelligence: {
    term: "Threat Intelligence",
    definition:
      "The share of this case's evidence that touches an indicator flagged as malicious by the threat provider.",
    reading:
      "0–100, higher is worse. 100 means every item references something already known to be malicious.",
  },
  forgery_risk: {
    term: "Forgery Risk",
    definition:
      "The highest tampering score found on any single item — signs that a screenshot or document was edited rather than captured.",
    reading:
      "0–100, higher is worse. This is the worst item, not an average: 50 or above is treated as possible tampering and flagged for review.",
  },
  campaign_size: {
    term: "Campaign Size",
    definition:
      "How large the biggest coordinated group of related evidence is, relative to what the engine considers a full-size campaign.",
    reading:
      "0–100, higher is worse. 100 means the largest cluster has reached full campaign size — evidence of an organised operation rather than an isolated incident.",
  },
  correlation_strength: {
    term: "Correlation Strength",
    definition:
      "The confidence of the single strongest link found between any two pieces of evidence in this case.",
    reading:
      "0–100, higher means better-connected. A high value means at least one pair is tied together firmly; it says nothing about the rest.",
  },
  timeline_criticality: {
    term: "Timeline Criticality",
    definition:
      "How many critical moments — events involving OTPs or financial transfers — appear on the case timeline.",
    reading:
      "0–100, higher is worse. It scales with the count of critical events, reaching 100 at the configured threshold.",
  },

  // ------------------------------------------------------- case-level score
  priority_score: {
    term: "Priority Score",
    definition:
      "The overall urgency of the case: a weighted average of the components below, using only those with data available.",
    reading:
      "0–100. Components that could not be computed are excluded entirely rather than counted as zero, so the score is never dragged down by missing inputs.",
  },

  // ---------------------------------------------------------- correlation
  specificity: {
    term: "Specificity",
    definition:
      "How identifying a matched value is — whether it appears almost nowhere else, or turns up all over the corpus.",
    reading:
      "0.00–1.00, higher is stronger. 1.00 means the value is essentially unique, so a shared match is meaningful; a low value means it is common, so it barely supports a link.",
  },
  correlation_confidence: {
    term: "Correlation Confidence",
    definition:
      "How firmly two pieces of evidence are tied together, combining every matching factor and how rare each match is.",
    reading: "0–100%, higher means a firmer link.",
  },
  relationship_strength: {
    term: "Relationship Strength",
    definition:
      "The confidence figure sorted into a band — weak, medium, strong or very strong.",
  },
  contribution: {
    term: "Contribution",
    definition:
      "How much this single factor added to the pair's overall correlation confidence.",
    reading: "Factors with a larger contribution are the ones driving the link.",
  },

  // -------------------------------------------------------------- suspects
  suspect_confidence: {
    term: "Suspect Confidence",
    definition:
      "How strongly an identifier is tied to the criminal activity in this case — based on how often it appears, how it correlates, and whether threat intelligence flagged it.",
    reading:
      "0–100%, higher means a stronger evidentiary link. This measures connection to the evidence, not guilt.",
  },
  threat_flagged: {
    term: "Threat Intel",
    definition:
      "This identifier was independently flagged as malicious by the threat intelligence provider — not merely inferred from this case.",
  },

  // -------------------------------------------------------------- timeline
  critical: {
    term: "Critical event",
    definition:
      "A moment involving an OTP or a financial transfer — the points where control or money actually changed hands.",
    reading:
      "These are what drive the case's timeline criticality score, and usually what an investigation is reconstructed around.",
  },
  milestone: {
    term: "Milestone",
    definition:
      "An event that marks the case moving from one stage of the scam into the next.",
  },
  event: {
    term: "Event",
    definition:
      "A dated action reconstructed from the evidence — a message sent, a page visited, a payment made.",
  },
  also_evidences: {
    term: "Also evidences",
    definition:
      "A hollow echo marking a stage the event also supports, drawn where it is not the event's primary stage.",
    reading:
      "One event can evidence several stages at once; it is drawn solid only in the stage it enters the story at.",
  },

  // ----------------------------------------------------------- evidence
  ocr_confidence: {
    term: "OCR Confidence",
    definition:
      "How certain the text reader was about the characters it extracted from an image or scan.",
    reading:
      "0–100, higher is better. Low confidence means the extracted text may contain errors.",
  },
  hash_verified: {
    term: "Hash Verified",
    definition:
      "The file's cryptographic fingerprint still matches the one recorded when it was acquired — proof it has not changed since.",
    reading:
      "A failure here breaks the chain of custody and must be resolved before the item is relied upon.",
  },
  evidence_set_digest: {
    term: "Evidence-Set Digest",
    definition:
      "A single SHA-256 fingerprint covering every item this report was built from, so the report can be tied back to an exact evidence set.",
  },
};

/** Normalise an engine key or display label to a glossary key. */
export function glossaryKey(name: string): string {
  return name.trim().toLowerCase().replace(/[\s-]+/g, "_");
}

/** Look up a term, tolerating either `Forgery Risk` or `forgery_risk`. */
export function lookupTerm(name: string): GlossaryEntry | undefined {
  return GLOSSARY[glossaryKey(name)];
}
