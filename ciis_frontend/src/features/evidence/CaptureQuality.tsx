import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";

import { StatusChip } from "@/components/common/StatusChip";
import { brandTone, severityColor } from "@/theme/theme";

/**
 * Phase-1 capture quality, shown beside the text it predicted.
 *
 * The quality module scores how readable a file was *before* any text was
 * extracted, grades it, and predicts the OCR accuracy that grade usually
 * yields. All three were computed and stored on every item and none reached
 * the interface — they existed only inside the raw artifact dump, where an
 * investigator would have to know the field name to find them.
 *
 * They belong next to the OCR output because that is the comparison that makes
 * them mean something: a poor grade beside a high line confidence is the
 * engine saying "I am sure about the little I could read", which neither
 * number conveys on its own.
 */

type QualityReport = {
  overall_score?: number;
  quality_grade?: string;
  expected_ocr_accuracy?: number;
  readability_score?: number;
  sub_scores?: Record<string, number>;
  notes?: string[];
  recommended_operations?: string[];
};

/** Grade bands from the quality service, in the order it evaluates them. */
const BANDS = [
  { label: "UNUSABLE", from: 0, to: 25, tone: "critical" as const },
  { label: "POOR", from: 25, to: 45, tone: "critical" as const },
  { label: "FAIR", from: 45, to: 65, tone: "medium" as const },
  { label: "GOOD", from: 65, to: 82, tone: "low" as const },
  { label: "EXCELLENT", from: 82, to: 100, tone: "low" as const },
];

/** What each measurement actually looks at, in one plain sentence. */
const MEASURES: Record<string, string> = {
  blur: "Edge sharpness. Low means the capture was out of focus or shaken.",
  brightness: "Overall exposure. Both too dark and blown-out hide text.",
  contrast: "How far the text stands out from its background.",
  noise: "Sensor grain and compression speckle that confuse letter shapes.",
  resolution: "Pixel detail available per character.",
  skew: "How far the page is rotated away from level.",
  compression: "How heavily the file was re-encoded before it reached us.",
  readability: "Whether the image looks like a page of text at all.",
};

const ORDER = [
  "blur", "contrast", "resolution", "brightness",
  "noise", "skew", "compression", "readability",
];

const label = (key: string) =>
  key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** The 0–100 grade scale with this item's score marked on it. */
function GradeScale({ score, grade }: { score: number; grade: string }) {
  const theme = useTheme();
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <Box sx={{ pt: 1, pb: 2.5, position: "relative" }}>
      <Stack direction="row" sx={{ height: 10, borderRadius: 5, overflow: "hidden" }}>
        {BANDS.map((band) => {
          const active = band.label === grade.toUpperCase();
          return (
            <Box
              key={band.label}
              sx={{
                width: `${band.to - band.from}%`,
                bgcolor: severityColor(band.tone, theme),
                opacity: active ? 1 : 0.22,
                transition: "opacity 150ms",
              }}
            />
          );
        })}
      </Stack>

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

      <Box sx={{ position: "relative", height: 14, mt: 0.5 }}>
        {BANDS.map((band) => (
          <Typography
            key={band.label}
            variant="caption"
            sx={{
              position: "absolute",
              left: `${band.from}%`,
              color:
                band.label === grade.toUpperCase()
                  ? severityColor(band.tone, theme)
                  : "text.secondary",
              fontWeight: band.label === grade.toUpperCase() ? 700 : 400,
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

/** One measurement, with a bar and the reason it is being shown. */
function MeasureRow({
  name,
  value,
  weakest,
}: {
  name: string;
  value: number;
  weakest: boolean;
}) {
  const theme = useTheme();
  const color = brandTone(
    value >= 65 ? "low" : value >= 45 ? "medium" : "critical",
    theme,
  );

  return (
    <Tooltip title={MEASURES[name] ?? ""} placement="left">
      <Box>
        <Stack direction="row" justifyContent="space-between" alignItems="baseline">
          <Stack direction="row" spacing={0.75} alignItems="baseline">
            <Typography variant="body2">{label(name)}</Typography>
            {weakest && (
              <Typography variant="caption" sx={{ color, fontWeight: 700 }}>
                weakest
              </Typography>
            )}
          </Stack>
          <Typography
            variant="body2"
            sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 700, color }}
          >
            {value.toFixed(1)}
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={Math.max(0, Math.min(100, value))}
          sx={{
            height: 6,
            borderRadius: 3,
            mt: 0.5,
            // Without this the unfilled remainder keeps MUI's primary-tinted
            // track, which reads as a second value sitting beside the first.
            backgroundColor: `${color}26`,
            "& .MuiLinearProgress-bar": { bgcolor: color },
          }}
        />
      </Box>
    </Tooltip>
  );
}

export function CaptureQuality({
  report,
  achievedConfidence,
  lineCount,
}: {
  report: QualityReport;
  /** Mean OCR confidence actually achieved on this page, 0–1. */
  achievedConfidence: number | null;
  lineCount: number;
}) {
  const theme = useTheme();
  const score = Number(report.overall_score);
  const grade = String(report.quality_grade ?? "");
  const expected = Number(report.expected_ocr_accuracy);
  if (!Number.isFinite(score)) return null;

  const subs = report.sub_scores ?? {};
  const present = ORDER.filter((k) => Number.isFinite(Number(subs[k])));
  const lowest = present.length
    ? present.reduce((a, b) => (Number(subs[a]) <= Number(subs[b]) ? a : b))
    : null;

  const achieved =
    achievedConfidence === null ? null : achievedConfidence * 100;
  // The prediction is a population average, so only a wide gap is meaningful.
  const gap =
    achieved !== null && Number.isFinite(expected) ? achieved - expected : null;

  return (
    <Card sx={{ width: "100%" }}>
      <CardHeader
        title="Capture Quality"
        subheader="How readable this file was before any text was extracted"
        titleTypographyProps={{ variant: "subtitle1" }}
      />
      <Divider />
      <CardContent>
        <Stack spacing={2}>
          <Box>
            <Stack direction="row" spacing={1.5} alignItems="baseline" flexWrap="wrap">
              <Typography variant="h3" sx={{ fontWeight: 800, lineHeight: 1 }}>
                {score.toFixed(1)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                / 100
              </Typography>
              {grade && <StatusChip value={grade.toLowerCase()} label={grade} />}
            </Stack>
          </Box>

          <GradeScale score={score} grade={grade} />

          {/* The comparison that gives the prediction meaning. */}
          {Number.isFinite(expected) && (
            <Box
              sx={{
                p: 1.5,
                borderRadius: 1,
                border: 1,
                borderColor: "divider",
                bgcolor: "action.hover",
              }}
            >
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={{ xs: 1.5, sm: 4 }}
              >
                <Box>
                  <Typography variant="overline" color="text.secondary">
                    Expected OCR accuracy
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    {expected.toFixed(1)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Predicted from the grade above
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="overline" color="text.secondary">
                    Actually achieved
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      fontWeight: 700,
                      color:
                        gap === null
                          ? undefined
                          : brandTone(gap >= 0 ? "low" : "high", theme),
                    }}
                  >
                    {achieved === null ? "—" : `${achieved.toFixed(1)}%`}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Mean confidence over {lineCount} recognised line
                    {lineCount === 1 ? "" : "s"}
                  </Typography>
                </Box>
              </Stack>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: "block", mt: 1.25 }}
              >
                Confidence describes the text the engine <em>did</em> read — it
                cannot report what it never detected. On a poor capture the two
                figures separate because whole lines go missing rather than
                being read badly, so read the line count alongside them.
              </Typography>
            </Box>
          )}

          {present.length > 0 && (
            <Box>
              <Typography variant="overline" color="text.secondary">
                What was measured
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: "block", mb: 1.5 }}
              >
                Each measurement is scored 0–100 and weighted into the figure
                above. Hover any row for what it looks at.
              </Typography>
              <Stack spacing={1.5}>
                {present.map((key) => (
                  <MeasureRow
                    key={key}
                    name={key}
                    value={Number(subs[key])}
                    weakest={key === lowest && present.length > 1}
                  />
                ))}
              </Stack>
            </Box>
          )}

          {(report.recommended_operations ?? []).length > 0 && (
            <Box>
              <Typography variant="overline" color="text.secondary">
                Repairs the engine applied
              </Typography>
              <Typography variant="body2">
                {(report.recommended_operations ?? [])
                  .map((op) => label(op))
                  .join(" · ")}
              </Typography>
            </Box>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
