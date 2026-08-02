import { titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";

/**
 * Presentation metadata for the engine's attack stages.
 *
 * The keys mirror `InvestigationConfig.timeline_stage_order` — the canonical
 * order a scam progresses through. Colours escalate along that order (calm
 * blue for first contact through to red at the money movement), so the chart
 * carries the severity story even before anyone reads a label. The plain
 * wording matters: "Credential Theft" means nothing to someone seeing the
 * tool for the first time, but "Passwords or OTPs requested" does.
 */
export interface StageMeta {
  label: string;
  meaning: string;
  color: string;
}

/** Lane holding events the engine could not attribute to any attack stage. */
export const UNSTAGED = "__unstaged__";

const STAGE_META: Record<string, StageMeta> = {
  initial_contact: {
    label: "Initial Contact",
    meaning: "The scammer's first approach — a prize, job offer or greeting.",
    color: BRAND.primary,
  },
  social_engineering: {
    label: "Social Engineering",
    meaning: "Pressure and urgency applied — warnings, deadlines, threats.",
    color: BRAND.medium,
  },
  credential_theft: {
    label: "Credential Theft",
    meaning: "Passwords, OTPs or PINs requested from the victim.",
    color: BRAND.high,
  },
  financial_transaction: {
    label: "Money Movement",
    meaning: "A payment, transfer or wallet transaction took place.",
    color: BRAND.critical,
  },
  post_attack: {
    label: "After the Attack",
    meaning: "The aftermath — scammer vanishes, victim reports the fraud.",
    color: "#a970ff",
  },
};

const UNSTAGED_META: StageMeta = {
  label: "Unattributed",
  meaning: "Events the engine could not tie to a specific attack stage.",
  color: "#8c9bba",
};

/** Fallback hues for stages an investigator has added via configuration. */
const EXTRA_COLORS = ["#00c2a8", "#36cfc9", "#f759ab", "#73d13d", "#597ef7"];

export function stageMeta(stage: string, index = 0): StageMeta {
  if (stage === UNSTAGED) return UNSTAGED_META;
  return (
    STAGE_META[stage] ?? {
      label: titleCase(stage),
      meaning: "A custom attack stage defined for this deployment.",
      color: EXTRA_COLORS[index % EXTRA_COLORS.length],
    }
  );
}
