import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import VerifiedIcon from "@mui/icons-material/Verified";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import {
  Button,
  Card,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { evidenceApi } from "@/api";
import { EmptyState, ErrorState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { SearchField } from "@/components/common/SearchField";
import { StatusChip } from "@/components/common/StatusChip";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatBytes, formatDateTime, truncateHash } from "@/lib/format";

import { UploadEvidenceDialog } from "./UploadEvidenceDialog";

export function EvidenceTab({ caseId }: { caseId: string }) {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [uploadOpen, setUploadOpen] = useState(false);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["evidence", caseId, { search, status, page, pageSize }],
    queryFn: () =>
      evidenceApi.list(caseId, {
        search: search || undefined,
        status: status || undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  });

  return (
    <Card>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ p: 2 }}>
        <SearchField
          value={search}
          onSearch={(v) => {
            setSearch(v);
            setPage(0);
          }}
          placeholder="Search evidence ID or file name…"
          sx={{ flex: 1, minWidth: 200 }}
        />
        <TextField
          select
          size="small"
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="">All</MenuItem>
          {["uploaded", "processed", "failed"].map((s) => (
            <MenuItem key={s} value={s} sx={{ textTransform: "capitalize" }}>
              {s}
            </MenuItem>
          ))}
        </TextField>
        {hasPermission("evidence.upload") && (
          <Button
            variant="contained"
            startIcon={<CloudUploadIcon />}
            onClick={() => setUploadOpen(true)}
          >
            Upload Evidence
          </Button>
        )}
      </Stack>

      {isPending ? (
        <TableSkeleton />
      ) : isError ? (
        <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />
      ) : data.results.length === 0 ? (
        <EmptyState
          icon={<ImageSearchIcon />}
          title="No evidence in this case"
          description="Upload screenshots, PDFs, chat exports, or documents. The Phase-1 pipeline acquires, hashes, and OCRs every file automatically."
          action={
            hasPermission("evidence.upload") && (
              <Button variant="contained" onClick={() => setUploadOpen(true)}>
                Upload the first item
              </Button>
            )
          }
        />
      ) : (
        <>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Evidence ID</TableCell>
                <TableCell>File</TableCell>
                <TableCell>Size</TableCell>
                <TableCell>SHA-256</TableCell>
                <TableCell>Integrity</TableCell>
                <TableCell>Uploaded</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.results.map((row) => (
                <TableRow
                  key={row.evidence_id}
                  hover
                  sx={{ cursor: "pointer" }}
                  onClick={() => navigate(`/cases/${caseId}/evidence/${row.evidence_id}`)}
                >
                  <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 600 }}>
                    {row.evidence_id}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 260 }}>
                    <Typography variant="body2" noWrap title={row.original_file_name}>
                      {row.original_file_name}
                    </Typography>
                  </TableCell>
                  <TableCell>{formatBytes(row.file_size_bytes)}</TableCell>
                  <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                    <Tooltip title={row.sha256_before}>
                      <span>{truncateHash(row.sha256_before)}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    {String(row.hash_verified) === "True" ? (
                      <Tooltip title="Hash verified before and after acquisition">
                        <VerifiedIcon color="success" fontSize="small" />
                      </Tooltip>
                    ) : (
                      <Tooltip title="Hash verification not confirmed">
                        <WarningAmberIcon color="warning" fontSize="small" />
                      </Tooltip>
                    )}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {formatDateTime(row.upload_time)}
                  </TableCell>
                  <TableCell>
                    <StatusChip value={row.status} />
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
            rowsPerPageOptions={[10, 25, 50]}
          />
        </>
      )}

      <UploadEvidenceDialog
        caseId={caseId}
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
      />
    </Card>
  );
}
