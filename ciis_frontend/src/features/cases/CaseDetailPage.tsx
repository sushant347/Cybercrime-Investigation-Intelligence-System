import ArchiveIcon from "@mui/icons-material/Archive";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import UnarchiveIcon from "@mui/icons-material/Unarchive";
import {
  Alert,
  Box,
  Button,
  Chip,
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
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { casesApi, investigationApi } from "@/api";
import { ErrorState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { StatusChip } from "@/components/common/StatusChip";
import { AnalyticsTab } from "@/features/analytics/AnalyticsTab";
import { useAuth } from "@/features/auth/AuthContext";
import { EvidenceTab } from "@/features/evidence/EvidenceTab";
import { GraphTab } from "@/features/graph/GraphTab";
import { InvestigationTab } from "@/features/investigation/InvestigationTab";
import { ReportsTab } from "@/features/reports/ReportsTab";
import { TimelineTab } from "@/features/timeline/TimelineTab";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";

import { CaseOverviewTab } from "./CaseOverviewTab";

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

  const activeTab: TabKey = TABS.includes(tab as TabKey) ? (tab as TabKey) : "overview";

  const caseQuery = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => casesApi.detail(caseId),
    enabled: !!caseId,
  });

  const analyzeMutation = useMutation({
    mutationFn: () => investigationApi.runAnalysis(caseId),
    onSuccess: (job) => {
      setToast(`Analysis started (job #${job.id}) — the report appears when it finishes.`);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      // Show the report as it is produced: land on it, then refresh the
      // artifacts once the engine has had a moment to write them.
      navigate(`/cases/${caseId}/reports`);
      window.setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: ["reports", caseId] });
        void queryClient.invalidateQueries({ queryKey: ["report-latest", caseId] });
        void queryClient.invalidateQueries({ queryKey: ["artifact", caseId] });
      }, 4000);
    },
    onError: (err) => setToast(apiErrorMessage(err)),
  });

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
              {caseData.tags.map((t) => (
                <Chip key={t} size="small" label={t} variant="outlined" />
              ))}
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
      {activeTab === "investigation" && <InvestigationTab caseId={caseId} />}
      {activeTab === "graph" && <GraphTab caseId={caseId} />}
      {activeTab === "timeline" && <TimelineTab caseId={caseId} />}
      {activeTab === "analytics" && <AnalyticsTab caseId={caseId} />}
      {activeTab === "reports" && (
        <ReportsTab caseId={caseId} caseReference={caseData.case_reference} />
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
