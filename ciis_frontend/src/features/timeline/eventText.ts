import type { TimelineEvent } from "@/types";

/**
 * A readable title for a timeline event.
 *
 * When the engine has nothing better to say it falls back to a description
 * assembled from fields the UI already displays as their own columns —
 * "Evidence EVID_00023 (bank_transactions.csv); stages: financial_transaction".
 * Repeating the evidence id, the file name and the stage list inside the
 * sentence, next to chips showing exactly those three things, is how a row
 * ends up looking like noise. Strip the boilerplate and keep whatever real
 * description remains.
 */
export function eventTitle(event: TimelineEvent): string {
  const text = (event.description ?? "").replace(/;\s*stages?:.*$/i, "").trim();
  const generic = /^Evidence\s+(\S+?)\s*\(([^)]*)\)$/i.exec(text);
  if (generic) return generic[2] || generic[1];
  return text || event.file_name || event.evidence_id || "Event";
}

/** True when the description carried no information of its own. */
export function isGeneratedDescription(event: TimelineEvent): boolean {
  const text = (event.description ?? "").replace(/;\s*stages?:.*$/i, "").trim();
  return /^Evidence\s+\S+?\s*\([^)]*\)$/i.test(text);
}
