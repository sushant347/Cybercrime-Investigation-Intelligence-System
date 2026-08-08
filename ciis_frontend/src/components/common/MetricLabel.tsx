import { Box, Stack, Tooltip, Typography } from "@mui/material";
import type { ReactNode } from "react";

import { lookupTerm, type GlossaryEntry } from "@/lib/glossary";

/**
 * A piece of forensic terminology that explains itself on hover.
 *
 * Two deliberate choices:
 *
 * 1. **The affordance is visible.** A tooltip nobody knows to hover over is
 *    the same as no tooltip, so the term carries a dotted underline and a
 *    help cursor. That is the conventional signal for "there is a definition
 *    here" and it costs almost no visual weight.
 * 2. **It is reachable without a mouse.** The trigger is focusable, so the
 *    definition opens on keyboard focus as well as hover. Tooltip-only
 *    explanations are invisible to keyboard and screen-reader users.
 *
 * The engine's own per-case explanation (e.g. "max Phase-1 forgery score 25")
 * is shown *underneath* the general definition rather than replacing it: the
 * reader needs to know what the metric means before the specific number for
 * this case means anything.
 */
export function MetricLabel({
  name,
  label,
  engineNote,
  entry,
  children,
  variant = "body2",
}: {
  /** Engine key or display label — resolved against the glossary. */
  name: string;
  /** Override the displayed text (defaults to the glossary term). */
  label?: string;
  /** The engine's case-specific explanation string, if there is one. */
  engineNote?: string;
  /** Supply an entry directly instead of looking `name` up. */
  entry?: GlossaryEntry;
  children?: ReactNode;
  variant?: "body2" | "caption" | "subtitle2" | "inherit";
}) {
  const found = entry ?? lookupTerm(name);
  const text = label ?? found?.term ?? name.replace(/_/g, " ");

  // Nothing to explain: render plain text rather than a dead affordance that
  // opens an empty tooltip.
  if (!found && !engineNote) {
    return (
      <Typography variant={variant === "inherit" ? "body2" : variant} component="span">
        {children ?? text}
      </Typography>
    );
  }

  return (
    <Tooltip
      arrow
      enterTouchDelay={0}
      leaveTouchDelay={6000}
      title={
        <Stack spacing={0.75} sx={{ py: 0.5, maxWidth: 300 }}>
          <Typography variant="caption" sx={{ fontWeight: 800, fontSize: "0.78rem" }}>
            {found?.term ?? text}
          </Typography>
          {found && (
            <Typography variant="caption" sx={{ lineHeight: 1.55 }}>
              {found.definition}
            </Typography>
          )}
          {found?.reading && (
            <Typography
              variant="caption"
              sx={{ lineHeight: 1.55, opacity: 0.82, fontStyle: "italic" }}
            >
              {found.reading}
            </Typography>
          )}
          {engineNote && (
            <Typography
              variant="caption"
              sx={{
                lineHeight: 1.5,
                pt: 0.5,
                mt: 0.25,
                borderTop: "1px solid rgba(255,255,255,0.18)",
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: "0.68rem",
              }}
            >
              This case: {engineNote}
            </Typography>
          )}
        </Stack>
      }
    >
      <Box
        component="span"
        tabIndex={0}
        sx={{
          cursor: "help",
          textDecoration: "underline dotted",
          textDecorationColor: "text.disabled",
          textUnderlineOffset: "3px",
          transition: "text-decoration-color 160ms ease, color 160ms ease",
          "&:hover, &:focus-visible": { textDecorationColor: "primary.main" },
          "&:focus-visible": { outline: "none", color: "primary.main" },
        }}
      >
        {children ?? (
          <Typography
            variant={variant === "inherit" ? "body2" : variant}
            component="span"
            sx={{ textTransform: "none" }}
          >
            {text}
          </Typography>
        )}
      </Box>
    </Tooltip>
  );
}
