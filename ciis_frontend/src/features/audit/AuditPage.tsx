import FactCheckIcon from "@mui/icons-material/FactCheck";
import {
  Box,
  Card,
  Chip,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { auditApi } from "@/api";
import { EmptyState, ErrorState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchField } from "@/components/common/SearchField";
import { StatusChip } from "@/components/common/StatusChip";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";

const SOURCE_LABEL: Record<string, string> = {
  evidence_pipeline: "Phase 1 · Evidence",
  investigation: "Phase 2 · Investigation",
  platform: "Platform · Users",
};

/** Module 10 - Unified audit trail (engine logs + platform activity). */
export default function AuditPage() {
  const [search, setSearch] = useState("");
  const [caseId, setCaseId] = useState("");
  const [module, setModule] = useState("");
  const [user, setUser] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["audit", { search, caseId, module, user, dateFrom, dateTo, page, pageSize }],
    queryFn: () =>
      auditApi.list({
        search: search || undefined,
        case_id: caseId || undefined,
        module: module || undefined,
        user: user || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  });

  return (
    <Box>
      <PageHeader
        title="Audit Log"
        subtitle="Complete trail: evidence acquisition, OCR, correlation, timeline, reports, and user activity"
      />
      <Card>
        <Stack
          direction={{ xs: "column", md: "row" }}
          spacing={2}
          sx={{ p: 2 }}
          flexWrap="wrap"
          useFlexGap
        >
          <SearchField
            value={search}
            onSearch={(v) => {
              setSearch(v);
              setPage(0);
            }}
            placeholder="Search detail, action, case…"
            sx={{ flex: 1, minWidth: 200 }}
          />
          <TextField
            size="small"
            label="Case ID"
            value={caseId}
            onChange={(e) => {
              setCaseId(e.target.value.trim());
              setPage(0);
            }}
            placeholder="CASE_0001"
            sx={{ minWidth: 140 }}
          />
          <TextField
            select
            size="small"
            label="Module"
            value={module}
            onChange={(e) => {
              setModule(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">All modules</MenuItem>
            {[
              "upload", "ocr", "pipeline", "correlation", "graph", "campaign",
              "suspect", "timeline", "analytics", "priority", "report",
              "cases", "evidence", "auth", "investigation",
            ].map((m) => (
              <MenuItem key={m} value={m} sx={{ textTransform: "capitalize" }}>
                {m}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="User"
            value={user}
            onChange={(e) => {
              setUser(e.target.value.trim());
              setPage(0);
            }}
            sx={{ minWidth: 130 }}
          />
          <TextField
            size="small"
            type="date"
            label="From"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            size="small"
            type="date"
            label="To"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />
        </Stack>

        {isPending ? (
          <TableSkeleton rows={10} />
        ) : isError ? (
          <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />
        ) : data.results.length === 0 ? (
          <EmptyState
            icon={<FactCheckIcon />}
            title="No audit entries match"
            description="Try widening the filters."
          />
        ) : (
          <>
            <Box sx={{ overflowX: "auto" }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Module</TableCell>
                    <TableCell>Action</TableCell>
                    <TableCell>Case</TableCell>
                    <TableCell>User</TableCell>
                    <TableCell>Level</TableCell>
                    <TableCell>Detail</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.results.map((entry, i) => (
                    <TableRow key={i} hover>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>
                        {formatDateTime(entry.timestamp)}
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={SOURCE_LABEL[entry.source] ?? entry.source}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>{entry.module || "—"}</TableCell>
                      <TableCell>{entry.action || "—"}</TableCell>
                      <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                        {entry.case_id || "—"}
                      </TableCell>
                      <TableCell>{entry.username || "system"}</TableCell>
                      <TableCell>
                        <StatusChip
                          value={
                            entry.level === "ERROR"
                              ? "failed"
                              : entry.level === "WARNING"
                                ? "high"
                                : "info"
                          }
                          label={entry.level || "INFO"}
                        />
                      </TableCell>
                      <TableCell sx={{ maxWidth: 380 }}>
                        <Typography variant="body2" noWrap title={entry.detail}>
                          {entry.detail}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
            <TablePagination
              component="div"
              count={data.count}
              page={page}
              rowsPerPage={pageSize}
              onPageChange={(_, p) => setPage(p)}
              onRowsPerPageChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(0);
              }}
              rowsPerPageOptions={[25, 50, 100, 200]}
            />
          </>
        )}
      </Card>
    </Box>
  );
}
