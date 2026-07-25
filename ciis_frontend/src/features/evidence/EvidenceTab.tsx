import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import VerifiedIcon from "@mui/icons-material/Verified";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import {
  Alert,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  MenuItem,
  Snackbar,
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
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import type { EvidenceRow } from "@/types";

import { UploadEvidenceDialog } from "./UploadEvidenceDialog";

/**
 * An item can be withdrawn only while it has produced nothing.
 *
 * The server is the authority (it also checks for OCR text, entities and
 * forensic reports and answers 409 otherwise); this is the cheap client-side
 * read of the same rule, so the button is not offered where it cannot work.
 * Anything already processed is part of the case record and stays.
 */
const isRemovable = (row: EvidenceRow) =>
  row.status === "failed" || row.status === "uploaded";

export function EvidenceTab({ caseId }: { caseId: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<EvidenceRow | null>(null);
  const [toast, setToast] = useState<string | null>(null);

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

  const deleteMutation = useMutation({
    mutationFn: (evidenceId: string) => evidenceApi.remove(caseId, evidenceId),
    onSuccess: (result) => {
      setPendingDelete(null);
      setToast(`${result.evidence_id} removed from the case.`);
      // The item is gone from the register and from every derived artifact,
      // so the case header, evidence list and Phase-2 views all need re-reading.
      void queryClient.invalidateQueries({ queryKey: ["evidence", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["artifact", caseId] });
    },
    onError: (err) => {
      setPendingDelete(null);
      setToast(apiErrorMessage(err));
    },
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
                {hasPermission("evidence.upload") && <TableCell align="right" />}
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
                  {hasPermission("evidence.upload") && (
                    <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                      <Tooltip
                        title={
                          isRemovable(row)
                            ? "Remove this unprocessed item"
                            : "Processed evidence is part of the case record and cannot be deleted"
                        }
                      >
                        <span>
                          <IconButton
                            size="small"
                            aria-label={`Delete ${row.evidence_id}`}
                            disabled={!isRemovable(row) || deleteMutation.isPending}
                            onClick={() => setPendingDelete(row)}
                          >
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </TableCell>
                  )}
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

      <Dialog open={!!pendingDelete} onClose={() => setPendingDelete(null)}>
        <DialogTitle>Remove this evidence item?</DialogTitle>
        <DialogContent>
          <DialogContentText component="div">
            <Typography variant="body2" gutterBottom>
              <strong>{pendingDelete?.evidence_id}</strong> —{" "}
              {pendingDelete?.original_file_name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              This item has not been processed, so nothing in the case cites it.
              The uploaded file, its chain-of-custody row and any partial output
              are deleted permanently. This cannot be undone.
            </Typography>
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)}>Cancel</Button>
          <Button
            color="error"
            variant="contained"
            disabled={deleteMutation.isPending}
            onClick={() =>
              pendingDelete && deleteMutation.mutate(pendingDelete.evidence_id)
            }
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

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
    </Card>
  );
}
