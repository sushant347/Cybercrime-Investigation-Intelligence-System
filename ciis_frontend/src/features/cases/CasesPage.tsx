import AddIcon from "@mui/icons-material/Add";
import FolderOffIcon from "@mui/icons-material/FolderOff";
import {
  Box,
  Button,
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
  TableSortLabel,
  TextField,
} from "@mui/material";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { casesApi } from "@/api";
import { EmptyState, ErrorState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { SearchField } from "@/components/common/SearchField";
import { StatusChip } from "@/components/common/StatusChip";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";

import { CreateCaseDialog } from "./CreateCaseDialog";

type SortKey = "case_id" | "created_at" | "title" | "evidence_count" | "status";

export default function CasesPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sort, setSort] = useState<SortKey>("created_at");
  const [desc, setDesc] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    if ((location.state as { openCreate?: boolean })?.openCreate) setCreateOpen(true);
  }, [location.state]);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["cases", { search, status, priority, page, pageSize, sort, desc }],
    queryFn: () =>
      casesApi.list({
        search: search || undefined,
        status: status || undefined,
        priority: priority || undefined,
        include_archived: status === "archived" ? 1 : undefined,
        page: page + 1,
        page_size: pageSize,
        ordering: `${desc ? "-" : ""}${sort}`,
      }),
    placeholderData: keepPreviousData,
  });

  const toggleSort = (key: SortKey) => {
    if (sort === key) setDesc(!desc);
    else {
      setSort(key);
      setDesc(true);
    }
  };

  return (
    <Box>
      <PageHeader
        title="Case Management"
        subtitle="Search, triage, and open investigations"
        actions={
          hasPermission("case.manage") && (
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              New Case
            </Button>
          )
        }
      />

      <Card>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ p: 2 }}>
          <SearchField
            value={search}
            onSearch={(v) => {
              setSearch(v);
              setPage(0);
            }}
            placeholder="Search case ID, title, tags…"
            sx={{ flex: 1, minWidth: 220 }}
          />
          <TextField
            select
            size="small"
            label="Status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="">All (unarchived)</MenuItem>
            {["open", "active", "completed", "archived"].map((s) => (
              <MenuItem key={s} value={s} sx={{ textTransform: "capitalize" }}>
                {s}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Priority"
            value={priority}
            onChange={(e) => {
              setPriority(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="">Any</MenuItem>
            {["critical", "high", "medium", "low"].map((p) => (
              <MenuItem key={p} value={p} sx={{ textTransform: "capitalize" }}>
                {p}
              </MenuItem>
            ))}
          </TextField>
        </Stack>

        {isPending ? (
          <TableSkeleton />
        ) : isError ? (
          <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />
        ) : data.results.length === 0 ? (
          <EmptyState
            icon={<FolderOffIcon />}
            title="No cases found"
            description="Adjust your filters, or create a new case to begin an investigation."
          />
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {(
                    [
                      ["case_id", "Case ID"],
                      ["title", "Title"],
                      ["status", "Status"],
                      ["evidence_count", "Evidence"],
                      ["created_at", "Created"],
                    ] as [SortKey, string][]
                  ).map(([key, label]) => (
                    <TableCell key={key} sortDirection={sort === key ? (desc ? "desc" : "asc") : false}>
                      <TableSortLabel
                        active={sort === key}
                        direction={sort === key && !desc ? "asc" : "desc"}
                        onClick={() => toggleSort(key)}
                      >
                        {label}
                      </TableSortLabel>
                    </TableCell>
                  ))}
                  <TableCell>Priority</TableCell>
                  <TableCell>Tags</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.results.map((c) => (
                  <TableRow
                    key={c.case_id}
                    hover
                    sx={{ cursor: "pointer" }}
                    onClick={() => navigate(`/cases/${c.case_id}`)}
                  >
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 600 }}>
                      {c.case_id}
                    </TableCell>
                    <TableCell>{c.title || <em>Untitled</em>}</TableCell>
                    <TableCell>
                      <StatusChip value={c.status} />
                    </TableCell>
                    <TableCell>{c.evidence_count}</TableCell>
                    <TableCell>{formatDateTime(c.created_at)}</TableCell>
                    <TableCell>
                      {c.priority ? (
                        <StatusChip value={c.priority_override || c.priority.priority_level} />
                      ) : (
                        <Chip size="small" label="Not analyzed" variant="outlined" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5}>
                        {c.tags.slice(0, 3).map((t) => (
                          <Chip key={t} size="small" label={t} />
                        ))}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
              rowsPerPageOptions={[10, 25, 50, 100]}
            />
          </Box>
        )}
      </Card>

      <CreateCaseDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </Box>
  );
}
