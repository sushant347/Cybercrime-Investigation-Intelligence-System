import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  useTheme,
} from "@mui/material";

import { StatusChip } from "@/components/common/StatusChip";
import { formatDateTime } from "@/lib/format";
import { BRAND, severityColor } from "@/theme/theme";
import type { CasePriority, PriorityComponent } from "@/types";

/**
 * Priority score, shown as arithmetic the reader can check.
 *
 * The engine (Module 8) scores six dimensions out of 100, weights each one,
 * drops any dimension whose input is missing, and renormalises the surviving
 * weights so they still total 1. The old panel showed only `score × weight`
 * per row, which does not reconstruct the headline number — the renormalisation
 * step was invisible, so the score looked arbitrary. This panel shows each
 * dimension's *share* of the final score and the points it contributes, and
 * those points add up to the headline exactly.
 */

/**
 * What each dimension measures, in plain language.
 *
 * Deliberately free of the engine's numeric thresholds (full-campaign size,
 * critical-event count): those live in InvestigationConfig and would silently
 * go stale here. The measured value always comes from the engine's own
 * `explanation` string, rendered alongside.
 */
const DIMENSION_HELP: Record<string, string> = {
  evidence_confidence:
    "How much the engine trusts the evidence itself — the average confidence Phase 1 assigned to the items in this case.",
  threat_intelligence:
    "How much of the evidence touches an indicator that threat intelligence flagged as malicious.",
  forgery_risk:
    "The most suspicious single item — the highest tampering score Phase 1 measured anywhere in the case.",
  campaign_size:
    "How large the biggest coordinated group of evidence is, measured against the size the engine treats as a full campaign.",
  correlation_strength:
    "How strongly the two most closely related pieces of evidence link to each other.",
  timeline_criticality:
    "How many critical moments — OTP or financial events — the timeline reconstruction found.",
};

/**
 * Band edges as defined by `InvestigationConfig.priority_bands`.
 *
 * Used only to draw the scale. The verdict itself is always the engine's
 * `priority_level`, never re-derived here, so a config change can at worst
 * make the scale's tick marks stale — it can never make this panel disagree
 * with the engine about the case.
 */
const BANDS = [
  { label: "LOW", from: 0, to: 30 },
  { label: "MEDIUM", from: 30, to: 55 },
  { label: "HIGH", from: 55, to: 75 },
  { label: "CRITICAL", from: 75, to: 100 },
];

const titleCase = (name: string) =>
  name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** The 0–100 scale with every band drawn and this case's score marked. */
function BandScale({ score, level }: { score: number; level: string }) {
  const theme = useTheme();
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <Box sx={{ pt: 1, pb: 3, position: "relative" }}>
      <Stack direction="row" sx={{ height: 10, borderRadius: 5, overflow: "hidden" }}>
        {BANDS.map((band) => {
          const active = band.label === level.toUpperCase();
          const color = severityColor(band.label, theme);
          return (
            <Box
              key={band.label}
              sx={{
                width: `${band.to - band.from}%`,
                bgcolor: color,
                opacity: active ? 1 : 0.22,
                transition: "opacity 150ms",
              }}
            />
          );
        })}
      </Stack>

      {/* Marker for this case's score. */}
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: `${clamped}%`,
          transform: "translateX(-50%)",
          width: 3,
          height: 18,
          borderRadius: 1,
          bgcolor: "text.primary",
          boxShadow: theme.shadows[2],
        }}
      />

      <Box sx={{ position: "relative", height: 16, mt: 0.5 }}>
        {BANDS.map((band) => (
          <Typography
            key={band.label}
            variant="caption"
            color="text.secondary"
            sx={{
              position: "absolute",
              left: `${band.from}%`,
              fontWeight: band.label === level.toUpperCase() ? 700 : 400,
              color:
                band.label === level.toUpperCase()
                  ? severityColor(band.label, theme)
                  : "text.secondary",
            }}
          >
            {band.from}
          </Typography>
        ))}
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ position: "absolute", right: 0 }}
        >
          100
        </Typography>
      </Box>
    </Box>
  );
}

/** One row of the contribution table. */
function ContributionRow({
  component,
  share,
  points,
}: {
  component: PriorityComponent;
  share: number;
  points: number;
}) {
  return (
    <TableRow>
      <TableCell sx={{ verticalAlign: "top", minWidth: 200 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          {titleCase(component.name)}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
          {DIMENSION_HELP[component.name] ?? ""}
        </Typography>
        {component.explanation && (
          <Typography
            variant="caption"
            sx={{ display: "block", mt: 0.5, fontStyle: "italic" }}
            color="text.secondary"
          >
            Measured: {component.explanation}
          </Typography>
        )}
      </TableCell>
      <TableCell align="right" sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
        <Typography variant="body2" sx={{ fontWeight: 700 }}>
          {component.score.toFixed(1)}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          / 100
        </Typography>
      </TableCell>
      <TableCell align="right" sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
        <Typography variant="body2">{component.weight.toFixed(2)}</Typography>
      </TableCell>
      <TableCell align="right" sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
        <Typography variant="body2">{(share * 100).toFixed(0)}%</Typography>
      </TableCell>
      <TableCell align="right" sx={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
        <Typography variant="body2" sx={{ fontWeight: 700, color: BRAND.primary }}>
          {points.toFixed(1)}
        </Typography>
      </TableCell>
    </TableRow>
  );
}

export function PriorityBreakdown({ priority }: { priority: CasePriority }) {
  const available = priority.components.filter((c) => c.available);
  const excluded = priority.components.filter((c) => !c.available);
  const totalWeight = available.reduce((sum, c) => sum + c.weight, 0);

  // Mirrors PrioritizationService: contribution = score × (weight ÷ Σweight),
  // and the contributions total the headline score.
  const rows = available.map((component) => {
    const share = totalWeight > 0 ? component.weight / totalWeight : 0;
    return { component, share, points: component.score * share };
  });
  const summed = rows.reduce((sum, r) => sum + r.points, 0);

  return (
    <Stack spacing={2}>
      {/* ------------------------------------------------------- the verdict */}
      <Box>
        <Stack direction="row" spacing={2} alignItems="baseline" flexWrap="wrap">
          <Typography variant="h2" sx={{ fontWeight: 800, lineHeight: 1 }}>
            {priority.priority_score.toFixed(1)}
          </Typography>
          <Typography variant="h6" color="text.secondary">
            / 100
          </Typography>
          <StatusChip value={priority.priority_level} />
        </Stack>
        <Typography variant="caption" color="text.secondary">
          Computed {formatDateTime(priority.computed_at)} from{" "}
          {available.length} of {priority.components.length} dimensions
        </Typography>
      </Box>

      <BandScale score={priority.priority_score} level={priority.priority_level} />

      {priority.investigation_recommendation && (
        <Box
          sx={{
            p: 1.5,
            borderRadius: 1,
            borderLeft: 3,
            borderColor: "primary.main",
            bgcolor: "action.hover",
          }}
        >
          <Typography variant="overline" color="text.secondary">
            Recommended next step
          </Typography>
          <Typography variant="body2">
            {priority.investigation_recommendation}
          </Typography>
        </Box>
      )}

      {priority.high_risk_indicators.length > 0 && (
        <Box>
          <Typography variant="overline" color="text.secondary">
            What pushed this case up
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
            {priority.high_risk_indicators.map((indicator) => (
              <StatusChip key={indicator} value="high" label={indicator} />
            ))}
          </Stack>
        </Box>
      )}

      {/* ------------------------------------------------- the working-out */}
      <Accordion disableGutters sx={{ bgcolor: "transparent" }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0 }}>
          <Typography variant="subtitle2">How this score is calculated</Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ px: 0 }}>
          <Stack spacing={2}>
            <Typography variant="body2" color="text.secondary">
              The engine scores this case on six dimensions, each out of 100,
              and each carrying a fixed weight. A dimension whose input is
              missing is dropped entirely rather than counted as zero — so the
              remaining weights are rescaled to still total 100%. That rescaled
              figure is the <strong>share</strong> column. Multiply a
              dimension's score by its share and you get the{" "}
              <strong>points</strong> it contributes; the points add up to the
              headline score.
            </Typography>

            <Box sx={{ overflowX: "auto" }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Dimension</TableCell>
                    <TableCell align="right">Score</TableCell>
                    <TableCell align="right">Weight</TableCell>
                    <TableCell align="right">Share</TableCell>
                    <TableCell align="right">Points</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => (
                    <ContributionRow key={row.component.name} {...row} />
                  ))}
                  <TableRow>
                    <TableCell sx={{ borderBottom: 0 }}>
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>
                        Total
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {rows
                          .map((r) => `${r.component.score.toFixed(0)}×${(r.share * 100).toFixed(0)}%`)
                          .join("  +  ")}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ borderBottom: 0 }} />
                    <TableCell align="right" sx={{ borderBottom: 0 }}>
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>
                        {totalWeight.toFixed(2)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: 0 }}>
                      <Typography variant="body2" sx={{ fontWeight: 700 }}>
                        100%
                      </Typography>
                    </TableCell>
                    <TableCell align="right" sx={{ borderBottom: 0 }}>
                      <Typography
                        variant="body2"
                        sx={{ fontWeight: 800, color: BRAND.primary }}
                      >
                        {summed.toFixed(1)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </Box>

            {excluded.length > 0 && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Not counted ({excluded.length})
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 1 }}
                  >
                    These dimensions had no input for this case. They were left
                    out of the average rather than scored zero, so they neither
                    raise nor lower the result.
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {excluded.map((component) => (
                      <Chip
                        key={component.name}
                        size="small"
                        variant="outlined"
                        label={titleCase(component.name)}
                      />
                    ))}
                  </Stack>
                </Box>
              </>
            )}

            {priority.explanation && (
              <>
                <Divider />
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    The engine&apos;s own summary
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {priority.explanation}
                  </Typography>
                </Box>
              </>
            )}

            <Divider />
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                How the score becomes a level
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {BANDS.map((band) => (
                  <Chip
                    key={band.label}
                    size="small"
                    variant={
                      band.label === priority.priority_level.toUpperCase()
                        ? "filled"
                        : "outlined"
                    }
                    label={`${band.label} ${band.from}–${band.to}`}
                    sx={{ textTransform: "capitalize" }}
                  />
                ))}
              </Stack>
            </Box>
          </Stack>
        </AccordionDetails>
      </Accordion>
    </Stack>
  );
}
