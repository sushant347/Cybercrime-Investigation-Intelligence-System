import { Chip, useTheme, type ChipProps } from "@mui/material";

import { severityColor } from "@/theme/theme";

/**
 * Single chip used for every engine-provided classification: priority
 * levels, relationship strengths, job statuses, case statuses, risk levels.
 * Color mapping is centralized in the theme (severityColor).
 */
export function StatusChip({
  value,
  size = "small",
  label: labelOverride,
  ...rest
}: { value: string | undefined | null } & Omit<ChipProps, "color">) {
  const theme = useTheme();
  const label = labelOverride ?? (value ?? "unknown").replace(/[_-]+/g, " ");
  const color = severityColor(value ?? undefined, theme);
  return (
    <Chip
      size={size}
      {...rest}
      label={label}
      sx={{
        color,
        borderColor: color,
        backgroundColor: `${color}1a`,
        textTransform: "capitalize",
        fontWeight: 700,
      }}
      variant="outlined"
    />
  );
}
