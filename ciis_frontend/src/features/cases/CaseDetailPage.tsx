import ArchiveIcon from "@mui/icons-material/Archive";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import UnarchiveIcon from "@mui/icons-material/Unarchive";
import {
  Alert,
  Box,
  Button,
  IconButton,
  MenuItem,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { casesApi, evidenceApi, investigationApi } from "@/api";
import { ErrorState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { StatusChip } from "@/components/common/StatusChip";
import { useAuth } from "@/features/auth/AuthContext";
import { EvidenceTab } from "@/features/evidence/EvidenceTab";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";

import { CaseOverviewTab } from "./CaseOverviewTab";

// Analysis tabs are independent investigation surfaces. Loading each one only
// when selected keeps Cytoscape, timeline rendering, analytics charts, report
// tooling, and their data-display code out of the initial case-detail bundle.
const InvestigationTab = lazy(() =>
  import("@/features/investigation/InvestigationTab").then((module) => ({
    default: module.InvestigationTab,
  })),
);
const GraphTab = lazy(() =>
  import("@/features/graph/GraphTab").then((module) => ({ default: module.GraphTab })),
);
const TimelineTab = lazy(() =>
  import("@/features/timeline/TimelineTab").then((module) => ({
    default: module.TimelineTab,
  })),
);
const AnalyticsTab = lazy(() =>
  import("@/features/analytics/AnalyticsTab").then((module) => ({
    default: module.AnalyticsTab,
  })),
);
const ReportsTab = lazy(() =>
  import("@/features/reports/ReportsTab").then((module) => ({
    default: module.ReportsTab,
  })),
);

/** How often to check a running analysis job. */
const ANALYSIS_POLL_MS = 2500;

const TABS = [
  "overview",
  "evidence",
  "investigation",
  "graph",
  "timeline",
  "analytics",
  "reports",
] as const;

type TabKey = (typeof TABS)[number];

export default function CaseDetailPage() {
  const { caseId = "", tab = "overview" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [toast, setToast] = useState<string | null>(null);
  const [analysisJobId, setAnalysisJobId] = useState<number | null>(null);

  const activeTab: TabKey = TABS.includes(tab as TabKey) ? (tab as TabKey) : "overview";

  const caseQuery = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => casesApi.detail(caseId),
    enabled: !!caseId,
  });

  const analysisHistoryQuery = useQuery({
    queryKey: ["jobs", caseId],
    queryFn: () => evidenceApi.jobs({ case_id: caseId }),
    enabled: !!caseId,
  });
  const latestAnalysisJob = analysisHistoryQuery.data?.results.find(
    (job) => job.job_type === "case_analysis",
  );

  const analyzeMutation = useMutation({
    mutationFn: () => investigationApi.runAnalysis(caseId),
    onSuccess: (job) => {
      setToast(`Analysis started (job #${job.id}) — results appear when it finishes.`);
      setAnalysisJobId(job.id);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/cases/${caseId}/reports`);
    },
    onError: (err) => setToast(apiErrorMessage(err)),
  });

  /**
   * Watch the analysis job and refresh everything it produces when it lands.
   *
   * Previously this fired a blind 4-second timer and refreshed the report
   * artifacts only — never ``["case", caseId]``, which is the payload that
   * carries the priority verdict. Analysis takes longer than four seconds, so
   * the one refresh happened before the engine had written anything and none
   * followed. The priority therefore appeared only after the page was
   * remounted (navigating away to admin and back), which is exactly the
   * "priority doesn't come automatically" symptom.
   */
  const analysisJob = useQuery({
    queryKey: ["job", analysisJobId],
    queryFn: () => evidenceApi.job(analysisJobId as number),
    enabled: analysisJobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" ||
        status === "completed_with_warnings" ||
        status === "failed"
        ? false
        : ANALYSIS_POLL_MS;
    },
  });

  useEffect(() => {
    const job = analysisJob.data;
    if (!job || analysisJobId === null) return;
    if (job.status === "completed" || job.status === "completed_with_warnings") {
      setAnalysisJobId(null);
      setToast(
        job.status === "completed_with_warnings"
          ? `Analysis completed with warnings: ${job.detail}`
          : "Analysis complete — priority, findings and report updated.",
      );
      // The case payload (priority verdict), every Phase-2 artifact and the
      // report list are all downstream of this job.
      for (const key of [
        ["case", caseId],
        ["artifact", caseId],
        ["reports", caseId],
        ["report-latest", caseId],
        ["cases"],
        ["jobs", caseId],
      ]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    } else if (job.status === "failed") {
      setAnalysisJobId(null);
      setToast(`Analysis failed: ${job.error || "see the audit trail for details"}`);
    }
  }, [analysisJob.data, analysisJobId, caseId, queryClient]);

  const statusMutation = useMutation({
    mutationFn: (patch: Record<string, unknown>) => casesApi.update(caseId, patch),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
    onError: (err) => setToast(apiErrorMessage(err)),
  });

  const archiveMutation = useMutation({
    mutationFn: (unarchive: boolean) => casesApi.archive(caseId, unarchive),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
    onError: (err) => setToast(apiErrorMessage(err)),
  });

  if (caseQuery.isPending) return <DetailSkeleton />;
  if (caseQuery.isError) {
    return (
      <ErrorState
        message={apiErrorMessage(caseQuery.error)}
        onRetry={() => void caseQuery.refetch()}
      />
    );
  }

  const caseData = caseQuery.data;
  const archived = caseData.status === "archived";

  return (
    <Box>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        alignItems={{ md: "center" }}
        sx={{ mb: 2 }}
      >
        <Stack direction="row" spacing={1} alignItems="center" sx={{ flex: 1, minWidth: 0 }}>
          <IconButton onClick={() => navigate("/")} aria-label="Back to start">
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="h5" noWrap>
                {caseData.case_reference || caseData.case_id}
              </Typography>
              <StatusChip value={caseData.status} />
              {caseData.priority && (
                <Tooltip title={caseData.priority.explanation || "Engine priority verdict"}>
                  <span>
                    <StatusChip
                      value={caseData.priority_override || caseData.priority.priority_level}
                    />
                  </span>
                </Tooltip>
              )}
            </Stack>
            <Typography variant="body2" color="text.secondary" noWrap>
              <Box component="span" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                {caseData.case_id}
              </Box>
              {" · "}
              {caseData.title || "Untitled case"} · opened {formatDateTime(caseData.created_at)} ·{" "}
              {caseData.evidence_count} evidence item(s)
            </Typography>
          </Box>
        </Stack>

        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {hasPermission("case.manage") && (
            <TextField
              select
              size="small"
              label="Status"
              value={caseData.status}
              onChange={(e) => statusMutation.mutate({ status: e.target.value })}
              sx={{ minWidth: 140 }}
              disabled={statusMutation.isPending}
            >
              {["open", "active", "completed", "archived"].map((s) => (
                <MenuItem key={s} value={s} sx={{ textTransform: "capitalize" }}>
                  {s}
                </MenuItem>
              ))}
            </TextField>
          )}
          {hasPermission("investigation.run") && (
            <Button
              variant="contained"
              startIcon={<PlayArrowIcon />}
              onClick={() => analyzeMutation.mutate()}
              disabled={analyzeMutation.isPending}
            >
              Run Analysis
            </Button>
          )}
          {hasPermission("case.manage") && (
            <Button
              variant="outlined"
              color={archived ? "success" : "warning"}
              startIcon={archived ? <UnarchiveIcon /> : <ArchiveIcon />}
              onClick={() => archiveMutation.mutate(archived)}
              disabled={archiveMutation.isPending}
            >
              {archived ? "Unarchive" : "Archive"}
            </Button>
          )}
        </Stack>
      </Stack>

      {latestAnalysisJob?.status === "completed_with_warnings" && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <strong>Latest analysis produced partial results.</strong> Timeline, graph,
          analytics, and report artifacts were regenerated, but should be reviewed with
          these warnings: {latestAnalysisJob.detail}
        </Alert>
      )}

      <Tabs
        value={activeTab}
        onChange={(_, value: TabKey) =>
          navigate(value === "overview" ? `/cases/${caseId}` : `/cases/${caseId}/${value}`)
        }
        variant="scrollable"
        allowScrollButtonsMobile
        sx={{
          borderBottom: 1,
          borderColor: "divider",
          mb: 3,
          position: "sticky",
          top: { xs: 56, sm: 64 },
          zIndex: (theme) => theme.zIndex.appBar - 1,
          bgcolor: "background.default",
        }}
      >
        {TABS.map((t) => (
          <Tab key={t} value={t} label={t} sx={{ textTransform: "capitalize" }} />
        ))}
      </Tabs>

      {activeTab === "overview" && <CaseOverviewTab caseData={caseData} />}
      {activeTab === "evidence" && <EvidenceTab caseId={caseId} />}
      {activeTab === "investigation" && (
        <Suspense fallback={<DetailSkeleton />}>
          <InvestigationTab key={caseId} caseId={caseId} />
        </Suspense>
      )}
      {activeTab === "graph" && (
        <Suspense fallback={<DetailSkeleton />}>
          <GraphTab key={caseId} caseId={caseId} />
        </Suspense>
      )}
      {activeTab === "timeline" && (
        <Suspense fallback={<DetailSkeleton />}>
          <TimelineTab key={caseId} caseId={caseId} />
        </Suspense>
      )}
      {activeTab === "analytics" && (
        <Suspense fallback={<DetailSkeleton />}>
          <AnalyticsTab key={caseId} caseId={caseId} />
        </Suspense>
      )}
      {activeTab === "reports" && (
        <Suspense fallback={<DetailSkeleton />}>
          <ReportsTab
            key={caseId}
            caseId={caseId}
            caseReference={caseData.case_reference}
          />
        </Suspense>
      )}

      <Snackbar
        open={!!toast}
        autoHideDuration={6000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity="info" variant="filled" onClose={() => setToast(null)}>
          {toast}
        </Alert>
      </Snackbar>
    </Box>
  );
}
