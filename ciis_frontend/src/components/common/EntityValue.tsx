import { Box, Tooltip, Typography } from "@mui/material";

import { nodeColor } from "@/theme/theme";

/**
 * An extracted identifier — a phone, wallet, email, bank account.
 *
 * These are the nouns of the whole system: they are what an investigator
 * scans for, copies out, and carries into the next case. Rendering them at
 * the same weight as the surrounding prose made them disappear into the row.
 *
 * They are set in the monospace face at heavy weight so digits align down the
 * column and a transposed character is visible, and tinted by entity type
 * using the *same* colour map as the relationship graph — so a phone number
 * is the same teal here as it is on the graph, and the eye learns one
 * vocabulary rather than two.
 */
export function EntityValue({
  value,
  type,
  size = "body2",
  truncate = true,
}: {
  value: string;
  /** Engine entity type (`phones`, `esewa_ids`, …). Drives the accent colour. */
  type?: string;
  size?: "body2" | "caption" | "subtitle2";
  truncate?: boolean;
}) {
  const accent = type ? nodeColor(type) : undefined;

  return (
    <Tooltip title={value} enterDelay={600}>
      <Box
        component="span"
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.75,
          minWidth: 0,
          maxWidth: "100%",
        }}
      >
        {accent && (
          <Box
            component="span"
            sx={{
              width: 3,
              alignSelf: "stretch",
              minHeight: 16,
              borderRadius: 2,
              bgcolor: accent,
              flexShrink: 0,
            }}
          />
        )}
        <Typography
          variant={size}
          component="span"
          sx={{
            fontFamily: '"JetBrains Mono", ui-monospace, monospace',
            fontWeight: 700,
            letterSpacing: "-0.01em",
            color: "text.primary",
            minWidth: 0,
            ...(truncate
              ? { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }
              : { wordBreak: "break-all" }),
          }}
        >
          {value}
        </Typography>
      </Box>
    </Tooltip>
  );
}
