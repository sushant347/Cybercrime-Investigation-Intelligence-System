import { Box, Chip, Stack, Tooltip, Typography, useTheme } from "@mui/material";

import { MetricLabel } from "@/components/common/MetricLabel";
import { BRAND, metricDirection, toneColor } from "@/theme/theme";

export interface ScoreComponentRow {
  name: string;
  score: number;
  weight: number;
  available?: boolean;
  explanation?: string;
}

/**
 * The weighted breakdown behind a composite score.
 *
 * Three things the previous flat-bar rendering got wrong, all of which
 * actively misinformed the reader:
 *
 * 1. **Every bar was the same blue.** A forgery risk of 90 looked exactly as
 *    reassuring as an evidence confidence of 90. Bars are now coloured by
 *    direction, so "bad when high" metrics read as warnings.
 * 2. **The weight was shown but never applied.** `44.4 × 0.20` leaves the
 *    reader to work out what that actually did to the final number. The real
 *    contribution is rendered explicitly.
 * 3. **Unavailable components looked like zeros.** The engine *excludes* them
 *    from the weighted mean rather than scoring them zero, so they are shown
 *    dimmed and stated as excluded — not as a component that scored nothing.
 *
 * Contribution mirrors the engine exactly: `sum(score × weight) / sum(weight)`
 * over available components only, so the parts add up to the headline score.
 */
export function ScoreComponents({
  components,
  total,
}: {
  components: ScoreComponentRow[];
  /** The headline score, used to sanity-check the contribution maths. */
  total?: number;
}) {
  const theme = useTheme();
  const mode = theme.palette.mode === "dark" ? "dark" : "light";

  const available = components.filter((c) => c.available !== false);
  const totalWeight = available.reduce((sum, c) => sum + c.weight, 0);

  // Largest contribution drives the bar scale, so the dominant driver of the
  // score is visually obvious rather than every bar sitting near the same width.
  const contributionOf = (c: ScoreComponentRow) =>
    totalWeight > 0 ? (c.score * c.weight) / totalWeight : 0;
  const maxContribution = Math.max(...available.map(contributionOf), 1);

  const sorted = [...components].sort((a, b) => {
    if ((a.available !== false) !== (b.available !== false)) {
      return a.available === false ? 1 : -1;
    }
    return contributionOf(b) - contributionOf(a);
  });

  return (
    <Stack spacing={1.75}>
      {sorted.map((component) => {
        const isAvailable = component.available !== false;
        const direction = metricDirection(component.name);
        const contribution = contributionOf(component);

        // A "higher is bad" metric turns red as it climbs; a "higher is good"
        // one turns green. Neutral metrics keep the brand accent.
        const intensity = Math.min(100, component.score) / 100;
        const barColor = !isAvailable
          ? theme.palette.text.disabled
          : direction === "higher_is_bad"
            ? intensity >= 0.66
              ? toneColor("bad", mode)
              : intensity >= 0.33
                ? toneColor("warn", mode)
                : toneColor("good", mode)
            : direction === "higher_is_good"
              ? intensity >= 0.66
                ? toneColor("good", mode)
                : intensity >= 0.33
                  ? toneColor("warn", mode)
                  : toneColor("bad", mode)
              : BRAND.primary;

        return (
          <Stack key={component.name} spacing={0.75} sx={{ opacity: isAvailable ? 1 : 0.5 }}>
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="baseline"
              spacing={1}
            >
              <Stack direction="row" spacing={0.75} alignItems="center" sx={{ minWidth: 0 }}>
                <MetricLabel
                  name={component.name}
                  engineNote={isAvailable ? component.explanation : undefined}
                />
                {!isAvailable && (
                  <Tooltip title="No input data for this component. The engine leaves it out of the weighted average rather than scoring it zero, so it does not drag the case score down.">
                    <Chip
                      size="small"
                      label="excluded"
                      variant="outlined"
                      sx={{ height: 18, fontSize: "0.65rem" }}
                    />
                  </Tooltip>
                )}
              </Stack>

              <Stack direction="row" spacing={1} alignItems="baseline" flexShrink={0}>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 800, color: barColor, fontVariantNumeric: "tabular-nums" }}
                >
                  {isAvailable ? component.score.toFixed(1) : "—"}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontVariantNumeric: "tabular-nums" }}
                >
                  × {component.weight.toFixed(2)}
                </Typography>
              </Stack>
            </Stack>

            {/* Score track, with the weighted contribution marked on it. */}
            <Box
              sx={{
                position: "relative",
                height: 8,
                borderRadius: 4,
                bgcolor: "action.hover",
                overflow: "hidden",
              }}
            >
              <Box
                sx={{
                  position: "absolute",
                  inset: 0,
                  width: `${Math.min(100, Math.max(0, component.score))}%`,
                  bgcolor: barColor,
                  borderRadius: 4,
                  transition: "width 520ms cubic-bezier(0.22, 1, 0.36, 1)",
                }}
              />
            </Box>

            {isAvailable && (
              <Stack direction="row" spacing={0.75} alignItems="center">
                <Box
                  sx={{
                    height: 3,
                    borderRadius: 2,
                    bgcolor: barColor,
                    opacity: 0.55,
                    width: `${(contribution / maxContribution) * 42}%`,
                    minWidth: 4,
                    transition: "width 520ms cubic-bezier(0.22, 1, 0.36, 1)",
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  contributes{" "}
                  <Box component="span" sx={{ fontWeight: 700, color: "text.primary" }}>
                    {contribution.toFixed(1)}
                  </Box>{" "}
                  pts
                </Typography>
              </Stack>
            )}
          </Stack>
        );
      })}

      {total !== undefined && available.length > 0 && (
        <Typography variant="caption" color="text.secondary" sx={{ pt: 0.5 }}>
          {available.length} of {components.length} components had data; the
          weighted average of those is the case score of{" "}
          <Box component="span" sx={{ fontWeight: 700, color: "text.primary" }}>
            {total.toFixed(1)}
          </Box>
          .
        </Typography>
      )}
    </Stack>
  );
}
