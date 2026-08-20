import { Card, CardContent, Stack, Typography, useTheme } from "@mui/material";
import type { ReactNode } from "react";

import { lightModeEquivalent } from "@/theme/theme";

export function StatCard({
  label,
  value,
  icon,
  color: colorProp,
  hint,
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  color?: string;
  hint?: string;
}) {
  const theme = useTheme();
  // Callers pass a BRAND hex for emphasis. Those tones are mixed for the dark
  // surface and drop below 3:1 as light-mode text, so they are translated
  // rather than trusted verbatim.
  const color = lightModeEquivalent(colorProp, theme);
  return (
    <Card
      sx={{
        flex: "1 1 200px",
        minWidth: 180,
        "&:hover": { borderColor: color ?? "primary.main" },
      }}
    >
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Stack spacing={0.5}>
            <Typography
              variant="overline"
              color="text.secondary"
              sx={{ lineHeight: 1.4, letterSpacing: "0.08em" }}
            >
              {label}
            </Typography>
            <Typography variant="h4" sx={{ color }}>
              {value}
            </Typography>
            {hint && (
              <Typography variant="caption" color="text.secondary">
                {hint}
              </Typography>
            )}
          </Stack>
          {icon && (
            <Stack
              sx={{
                color: color ?? "primary.main",
                bgcolor: `${color ?? "#3d7eff"}1a`,
                borderRadius: 2,
                p: 1,
              }}
            >
              {icon}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
