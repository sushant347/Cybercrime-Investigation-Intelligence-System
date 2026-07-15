import { Card, CardContent, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  icon,
  color,
  hint,
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  color?: string;
  hint?: string;
}) {
  return (
    <Card sx={{ flex: "1 1 200px", minWidth: 180 }}>
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
