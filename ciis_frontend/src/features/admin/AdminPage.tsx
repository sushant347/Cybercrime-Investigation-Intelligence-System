import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import DeleteForeverIcon from "@mui/icons-material/DeleteForever";
import LogoutIcon from "@mui/icons-material/Logout";
import RefreshIcon from "@mui/icons-material/Refresh";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  IconButton,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { adminApi, dashboardApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { adminToken, apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";
import type { AdminCase, AdminDeleteResult } from "@/types";

/** Password gate — the admin role is unlocked by a shared password. */
function AdminLogin({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");

  const login = useMutation({
    mutationFn: () => adminApi.login(password),
    onSuccess: (data) => {
      adminToken.set(data.token);
      onSuccess();
    },
  });

  return (
    <Box sx={{ maxWidth: 480, mx: "auto", py: { xs: 2, md: 6 } }}>
      <Card>
        <CardContent sx={{ p: { xs: 3, md: 4 } }}>
          <Stack spacing={1} sx={{ mb: 3 }}>
            <AdminPanelSettingsIcon color="primary" sx={{ fontSize: 40 }} />
            <Typography variant="h5">Administrator access</Typography>
            <Typography variant="body2" color="text.secondary">
              Enter the admin password to view every case and remove cases.
              Investigators do not need this — they reach their own case by
              reference.
            </Typography>
          </Stack>

          <Box
            component="form"
            onSubmit={(e) => {
              e.preventDefault();
              if (password) login.mutate();
            }}
          >
            <Stack spacing={2.5}>
              <TextField
                label="Admin password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                fullWidth
                required
              />
              {login.isError && (
                <Alert severity="error">{apiErrorMessage(login.error)}</Alert>
              )}
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={!password || login.isPending}
              >
                {login.isPending ? "Checking…" : "Unlock admin"}
              </Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

/**
 * Cross-case overview.
 *
 * Deliberately only on this page: the product has no dashboard for
 * investigators, because a case is private to whoever knows its reference and
 * a cross-case view would expose one case to another. The administrator is
 * already past that boundary, so the aggregates belong here.
 */
function SystemOverview() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardApi.get,
    retry: false,
  });

  if (isPending) return <TableSkeleton />;
  if (isError) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        {apiErrorMessage(error)}
      </Alert>
    );
  }

  const totals = data.totals;
  const threat = data.threat_distribution ?? {};
  const priority = data.priority_distribution ?? {};
  const analysed = totals.analysed_cases ?? 0;
  const threatTotal = Object.values(threat).reduce((sum, n) => sum + n, 0);

  return (
    <Stack spacing={2} sx={{ mb: 3 }}>
      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
        <StatCard label="Cases" value={totals.cases} hint={`${totals.active_cases} active`} />
        <StatCard
          label="Evidence"
          value={totals.evidence}
          hint={`${totals.entities_extracted ?? 0} entities extracted`}
        />
        <StatCard
          label="Analysed"
          value={`${analysed}/${totals.cases}`}
          hint={
            analysed < totals.cases
              ? `${totals.cases - analysed} case(s) never analysed`
              : "every case has findings"
          }
        />
        <StatCard
          label="Cases with threats"
          value={totals.cases_with_threats ?? 0}
          hint={`${totals.campaigns} campaign(s) detected`}
        />
      </Stack>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="subtitle2" gutterBottom>
              Threat verdicts across all cases
            </Typography>
            {threatTotal === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {analysed === 0
                  ? "No case has been analysed yet, so nothing has been checked."
                  : "No URLs or domains were found in any analysed case."}
              </Typography>
            ) : (
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {Object.entries(threat).map(([verdict, count]) => (
                  <Chip
                    key={verdict}
                    size="small"
                    label={`${verdict}: ${count}`}
                    color={
                      verdict === "malicious"
                        ? "error"
                        : verdict === "suspicious"
                          ? "warning"
                          : "default"
                    }
                    variant={verdict === "benign" ? "outlined" : "filled"}
                  />
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>

        <Card sx={{ flex: 1 }}>
          <CardContent>
            <Typography variant="subtitle2" gutterBottom>
              Priority distribution
            </Typography>
            {Object.keys(priority).length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No priority verdicts yet — they are produced by a case analysis.
              </Typography>
            ) : (
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {Object.entries(priority).map(([band, count]) => (
                  <Chip key={band} size="small" variant="outlined" label={`${band}: ${count}`} />
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>
      </Stack>
    </Stack>
  );
}

/** Everything an administrator can do: see all cases, delete one. */
export default function AdminPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [unlocked, setUnlocked] = useState(adminToken.isPresent);
  const [target, setTarget] = useState<AdminCase | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AdminDeleteResult | null>(null);

  const casesQuery = useQuery({
    queryKey: ["admin", "cases"],
    queryFn: adminApi.listCases,
    enabled: unlocked,
    retry: false,
  });

  const remove = useMutation({
    mutationFn: (caseId: string) => adminApi.deleteCase(caseId),
    onSuccess: (result) => {
      setTarget(null);
      setLastResult(result);
      const refreshed = result.refreshed_cases?.length ?? 0;
      setToast(
        `Deleted ${result.case_id}` +
          (refreshed ? ` · ${refreshed} linked case(s) re-analysed` : ""),
      );
      // Every case view may now be stale (cross-case links changed).
      void queryClient.invalidateQueries();
    },
    onError: (err) => setToast(apiErrorMessage(err)),
  });

  if (!unlocked) {
    return <AdminLogin onSuccess={() => setUnlocked(true)} />;
  }

  const cases = casesQuery.data?.cases ?? [];

  return (
    <Box>
      <PageHeader
        title="Administration"
        subtitle="Every case in the system. Deleting a case also refreshes the cases it was linked to."
        actions={
          <Stack direction="row" spacing={1}>
            <Tooltip title="Refresh">
              <IconButton onClick={() => void casesQuery.refetch()}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Button
              size="small"
              startIcon={<LogoutIcon />}
              onClick={() => {
                adminToken.clear();
                setUnlocked(false);
                navigate("/");
              }}
            >
              Lock
            </Button>
          </Stack>
        }
      />

      <SystemOverview />

      {casesQuery.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {apiErrorMessage(casesQuery.error)}
        </Alert>
      )}

      {lastResult && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setLastResult(null)}>
          <strong>{lastResult.case_id}</strong> removed — {lastResult.evidence_removed}{" "}
          evidence item(s) and {lastResult.paths_deleted.length} stored file(s) deleted.
          {lastResult.refreshed_cases.length > 0 ? (
            <>
              {" "}
              Re-analysed: {lastResult.refreshed_cases.join(", ")} (their cross-case
              links, timeline, graph and reports no longer reference it).
            </>
          ) : (
            " No other case was linked to it."
          )}
        </Alert>
      )}

      <Card>
        {casesQuery.isPending ? (
          <TableSkeleton />
        ) : cases.length === 0 ? (
          <EmptyState
            icon={<AdminPanelSettingsIcon />}
            title="No cases in the system"
            description="Cases appear here as investigators create them."
          />
        ) : (
          <>
            <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
              <Typography variant="body2" color="text.secondary">
                {cases.length} case(s)
              </Typography>
            </CardContent>
            <Divider />
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Reference</TableCell>
                  <TableCell>Case ID</TableCell>
                  <TableCell align="right">Evidence</TableCell>
                  <TableCell>Analysed</TableCell>
                  <TableCell>Linked cases</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {cases.map((row) => (
                  <TableRow key={row.case_id} hover>
                    <TableCell>{row.case_reference || "—"}</TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                      {row.case_id}
                    </TableCell>
                    <TableCell align="right">{row.evidence_count}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={row.analysed ? "yes" : "no"}
                        color={row.analysed ? "success" : "default"}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      {row.linked_case_ids.length ? (
                        <Chip
                          size="small"
                          label={`${row.linked_case_ids.length} linked`}
                          color="warning"
                          variant="outlined"
                        />
                      ) : (
                        <Typography variant="caption" color="text.secondary">
                          none
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>{formatDateTime(row.created_at)}</TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button
                          size="small"
                          onClick={() => navigate(`/cases/${row.case_id}/evidence`)}
                        >
                          Open
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          startIcon={<DeleteForeverIcon />}
                          onClick={() => setTarget(row)}
                        >
                          Delete
                        </Button>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}
      </Card>

      {/* Delete confirmation — spells out the cascade. */}
      <Dialog open={!!target} onClose={() => setTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Delete {target?.case_reference || target?.case_id}?</DialogTitle>
        <DialogContent>
          <DialogContentText component="div">
            This permanently removes the case and everything derived from it:
            <ul>
              <li>{target?.evidence_count ?? 0} uploaded evidence file(s) and their OCR</li>
              <li>all analysis artifacts (correlation, timeline, graph, report)</li>
              <li>its entries in the cross-case entity index</li>
            </ul>
            {target && target.linked_case_ids.length > 0 && (
              <>
                <strong>{target.linked_case_ids.length} linked case(s)</strong> (
                {target.linked_case_ids.join(", ")}) will be re-analysed so their
                cross-case correlation, timeline, graph and reports stop referencing
                this case.
              </>
            )}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTarget(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={remove.isPending}
            onClick={() => target && remove.mutate(target.case_id)}
          >
            {remove.isPending ? "Deleting…" : "Delete case"}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={!!toast}
        autoHideDuration={6000}
        onClose={() => setToast(null)}
        message={toast}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      />
    </Box>
  );
}
