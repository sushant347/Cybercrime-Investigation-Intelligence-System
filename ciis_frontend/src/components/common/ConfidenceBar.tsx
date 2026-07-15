import { Box, LinearProgress, Stack, Tooltip, Typography } from "@mui/material";

import { BRAND } from "@/theme/theme";

/**
 * Displays an engine-computed confidence/score value (0-1 fraction or
 * 0-100 scale). Purely presentational - never derives new scores.
 */
export function ConfidenceBar({
  value,
  scale = "fraction",
  label,
  width = 120,
}: {
  value: number | null | undefined;
  scale?: "fraction" | "percent";
  label?: string;
  width?: number | string;
}) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <Typography variant="caption" color="text.secondary">
        —
      </Typography>
    );
  }
  const percent = scale === "fraction" ? value * 100 : value;
  const clamped = Math.max(0, Math.min(100, percent));
  const color =
    clamped >= 75 ? BRAND.low : clamped >= 45 ? BRAND.high : BRAND.critical;
  return (
    <Tooltip title={`${label ?? "Confidence"}: ${clamped.toFixed(1)}%`}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ width }}>
        <Box sx={{ flex: 1 }}>
          <LinearProgress
            variant="determinate"
            value={clamped}
            sx={{
              height: 6,
              borderRadius: 3,
              backgroundColor: `${color}26`,
              "& .MuiLinearProgress-bar": { backgroundColor: color },
            }}
          />
        </Box>
        <Typography variant="caption" sx={{ minWidth: 40, fontWeight: 700, color }}>
          {clamped.toFixed(0)}%
        </Typography>
      </Stack>
    </Tooltip>
  );
}
