import { Box, Stack, Tooltip, Typography, useTheme } from "@mui/material";

import { BRAND } from "@/theme/theme";
import type { JobStage } from "@/types";

/**
 * Live view of what the engine is doing to one piece of evidence.
 *
 * The steps mirror `api.constants.EvidenceStage.ORDER` — the actual order the
 * worker executes — so the segments track real work rather than a timer. Steps
 * the engine legitimately skips (forensics can be disabled; the timeline
 * rebuild is deferred to the last upload of a batch) simply never light up.
 */

/** Must stay in sync with `EvidenceStage.ORDER` on the API. */
export const EVIDENCE_STAGES: { key: string; label: string; hint: string }[] = [
  {
    key: "acquire",
    label: "Acquire",
    hint: "Copy the file into evidence storage and compute its SHA-256 fingerprint.",
  },
  {
    key: "extract",
    label: "Extract",
    hint: "Read the text: OCR for images, the text layer for PDFs, verbatim for text files.",
  },
  {
    key: "verify",
    label: "Verify",
    hint: "Re-hash the stored file and compare — proves the evidence was not altered.",
  },
  {
    key: "store",
    label: "Store",
    hint: "Write the chain-of-custody row and the OCR result to the case record.",
  },
  {
    key: "enrich",
    label: "Entities",
    hint: "Clean and enhance the text, then extract phones, emails, URLs, wallets and amounts.",
  },
  {
    key: "forensics",
    label: "Forensics",
    hint: "Metadata/EXIF, image quality, forgery indicators, brand logos, confidence score.",
  },
  {
    key: "correlate",
    label: "Correlate",
    hint: "Rebuild the case correlation, timeline and relationship graph.",
  },
];

const formatMs = (ms: number | null | undefined): string => {
  if (ms === null || ms === undefined) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
};

export function ProcessingStages({
  current,
  note,
  stages,
  done,
  failed,
}: {
  /** Stage key the engine is on now; empty once the job has settled. */
  current: string;
  note?: string;
  /** Steps already started, with measured durations. */
  stages: JobStage[];
  done?: boolean;
  failed?: boolean;
}) {
  const theme = useTheme();
  const timings = new Map(stages.map((s) => [s.key, s]));
  const currentIndex = EVIDENCE_STAGES.findIndex((s) => s.key === current);

  const totalMs = stages.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
  const activeStage = EVIDENCE_STAGES[currentIndex];

  return (
    <Box>
      <Stack direction="row" spacing={0.5} sx={{ mb: 0.75 }}>
        {EVIDENCE_STAGES.map((stage, i) => {
          const record = timings.get(stage.key);
          const isActive = i === currentIndex;
          // Anything the engine started and closed off counts as complete; on a
          // finished job every recorded step is complete.
          const isComplete = !!record && (done || !isActive);
          const skipped = done && !record;

          const color = failed && isActive
            ? BRAND.critical
            : isComplete
              ? BRAND.low
              : isActive
                ? BRAND.primary
                : theme.palette.divider;

          return (
            <Tooltip
              key={stage.key}
              title={
                <Box>
                  <Typography variant="caption" sx={{ fontWeight: 700, display: "block" }}>
                    {stage.label}
                    {record?.duration_ms != null ? ` — ${formatMs(record.duration_ms)}` : ""}
                    {skipped ? " — not needed" : ""}
                  </Typography>
                  <Typography variant="caption">{stage.hint}</Typography>
                </Box>
              }
            >
              <Box
                sx={{
                  flex: 1,
                  height: 6,
                  borderRadius: 3,
                  bgcolor: color,
                  opacity: skipped ? 0.35 : 1,
                  transition: "background-color 220ms ease",
                  // A gentle pulse marks the step actually executing right now.
                  ...(isActive && !done && !failed
                    ? {
                        animation: "ciis-stage-pulse 1.3s ease-in-out infinite",
                        "@keyframes ciis-stage-pulse": {
                          "0%, 100%": { opacity: 1 },
                          "50%": { opacity: 0.4 },
                        },
                      }
                    : {}),
                }}
              />
            </Tooltip>
          );
        })}
      </Stack>

      <Typography
        variant="caption"
        color={failed ? "error" : "text.secondary"}
        sx={{ display: "block", overflowWrap: "anywhere" }}
      >
        {done
          ? `All steps complete${totalMs ? ` in ${formatMs(totalMs)}` : ""} · ${
              stages.length
            } step${stages.length === 1 ? "" : "s"} recorded`
          : activeStage
            ? `Step ${currentIndex + 1} of ${EVIDENCE_STAGES.length}: ${activeStage.label}${
                note ? ` — ${note}` : ""
              }`
            : "Waiting for the engine…"}
      </Typography>
    </Box>
  );
}
