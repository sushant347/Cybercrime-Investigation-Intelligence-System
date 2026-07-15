import {
  Card,
  CardContent,
  CardHeader,
  Divider,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";

import { KeyValueTable } from "@/components/common/KeyValueTable";
import { StatusChip } from "@/components/common/StatusChip";
import { formatDateTime } from "@/lib/format";
import type { CaseDetail } from "@/types";

/** Case overview: workflow details + the engine's priority verdict verbatim. */
export function CaseOverviewTab({ caseData }: { caseData: CaseDetail }) {
  const priority = caseData.priority;

  return (
    <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="flex-start">
      <Card sx={{ flex: 1, width: "100%" }}>
        <CardHeader title="Case Details" />
        <Divider />
        <KeyValueTable
          data={{
            case_id: caseData.case_id,
            title: caseData.title || "—",
            description: caseData.description || "—",
            investigator_notes: caseData.investigator_notes || "—",
            status: caseData.status,
            assigned_to: caseData.assigned_to ?? "Unassigned",
            evidence_count: caseData.evidence_count,
            created_at: formatDateTime(caseData.created_at),
            last_updated: formatDateTime(caseData.updated_at),
            tags: caseData.tags.join(", ") || "—",
          }}
        />
      </Card>

      <Card sx={{ flex: 1, width: "100%" }}>
        <CardHeader
          title="Case Priority"
          subheader="Computed by the Phase-2 prioritization engine"
          action={priority && <StatusChip value={priority.priority_level} />}
        />
        <Divider />
        <CardContent>
          {!priority ? (
            <Typography variant="body2" color="text.secondary">
              No priority verdict yet. Run the investigation analysis to generate one.
            </Typography>
          ) : (
            <Stack spacing={2}>
              <Stack direction="row" spacing={2} alignItems="baseline">
                <Typography variant="h3">{priority.priority_score.toFixed(1)}</Typography>
                <Typography variant="body2" color="text.secondary">
                  / 100 priority score · computed {formatDateTime(priority.computed_at)}
                </Typography>
              </Stack>

              {priority.explanation && (
                <Typography variant="body2">{priority.explanation}</Typography>
              )}

              {priority.investigation_recommendation && (
                <Typography variant="body2" sx={{ fontStyle: "italic" }}>
                  Recommendation: {priority.investigation_recommendation}
                </Typography>
              )}

              {priority.high_risk_indicators.length > 0 && (
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {priority.high_risk_indicators.map((ind) => (
                    <StatusChip key={ind} value="high" label={ind} />
                  ))}
                </Stack>
              )}

              <Divider />
              <Typography variant="subtitle2">Score components</Typography>
              {priority.components.map((component) => (
                <Tooltip key={component.name} title={component.explanation || component.name}>
                  <Stack spacing={0.5}>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" sx={{ textTransform: "capitalize" }}>
                        {component.name.replace(/_/g, " ")}
                        {!component.available && " (unavailable)"}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {component.score.toFixed(1)} × {component.weight.toFixed(2)}
                      </Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(100, component.score)}
                      sx={{ height: 6, borderRadius: 3 }}
                    />
                  </Stack>
                </Tooltip>
              ))}
            </Stack>
          )}
        </CardContent>
      </Card>
    </Stack>
  );
}
