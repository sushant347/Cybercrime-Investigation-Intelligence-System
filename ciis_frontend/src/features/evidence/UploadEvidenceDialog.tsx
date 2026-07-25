import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { evidenceApi } from "@/api";
import { StatusChip } from "@/components/common/StatusChip";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatBytes } from "@/lib/format";
import type { BackgroundJob } from "@/types";

const ACCEPT = ".png,.jpg,.jpeg,.pdf,.txt,.csv,.docx";

type Mode = "file" | "url";

export function UploadEvidenceDialog({
  caseId,
  open,
  onClose,
}: {
  caseId: string;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [mode, setMode] = useState<Mode>("file");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<BackgroundJob | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      mode === "url"
        ? evidenceApi.submitUrl(caseId, url.trim(), notes)
        : evidenceApi.upload(caseId, file!, notes),
    onSuccess: (created) => setJob(created),
    onError: (err) => setError(apiErrorMessage(err)),
  });

  // Poll the processing job until it finishes, then refresh the lists.
  useQuery({
    queryKey: ["job", job?.id],
    queryFn: async () => {
      const latest = await evidenceApi.job(job!.id);
      setJob(latest);
      if (latest.status === "completed" || latest.status === "failed") {
        void queryClient.invalidateQueries({ queryKey: ["evidence", caseId] });
        void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
        void queryClient.invalidateQueries({ queryKey: ["artifact", caseId] });
        void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      }
      return latest;
    },
    enabled: !!job && (job.status === "queued" || job.status === "running"),
    refetchInterval: 2500,
  });

  const reset = useCallback(() => {
    setFile(null);
    setUrl("");
    setMode("file");
    setNotes("");
    setError(null);
    setJob(null);
    mutation.reset();
  }, [mutation]);

  const handleClose = () => {
    reset();
    onClose();
  };

  const pickFile = (picked: File | undefined | null) => {
    if (!picked) return;
    setError(null);
    setFile(picked);
  };

  const processing = job && (job.status === "queued" || job.status === "running");

  return (
    <Dialog open={open} onClose={processing ? undefined : handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Upload Evidence — {caseId}</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}

          {!job && (
            <>
              <Tabs
                value={mode}
                onChange={(_, next: Mode) => {
                  setMode(next);
                  setError(null);
                }}
                sx={{ borderBottom: 1, borderColor: "divider" }}
              >
                <Tab value="file" label="Upload a file" />
                <Tab value="url" label="Submit a link" />
              </Tabs>
            </>
          )}

          {!job && mode === "url" && (
            <>
              <TextField
                label="Evidence URL"
                placeholder="https://suspicious-site.example/login"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                fullWidth
                autoFocus
                helperText="The link is hashed and stored like any other evidence, then scored by threat intelligence and matched across cases."
              />
              <TextField
                label="Investigator notes (chain of custody)"
                multiline
                minRows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </>
          )}

          {!job && mode === "file" && (
            <>
              <Box
                onClick={() => inputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  pickFile(e.dataTransfer.files?.[0]);
                }}
                sx={{
                  border: "2px dashed",
                  borderColor: dragOver ? "primary.main" : "divider",
                  borderRadius: 2,
                  p: 4,
                  textAlign: "center",
                  cursor: "pointer",
                  bgcolor: dragOver ? "action.hover" : "transparent",
                }}
              >
                <CloudUploadIcon color="primary" sx={{ fontSize: 40 }} />
                <Typography variant="subtitle1">
                  {file ? file.name : "Drop a file here or click to browse"}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {file
                    ? formatBytes(file.size)
                    : "PNG, JPG, PDF, TXT, CSV, DOCX — max 50 MB. SHA-256 is computed on acquisition."}
                </Typography>
                <input
                  ref={inputRef}
                  hidden
                  type="file"
                  accept={ACCEPT}
                  onChange={(e) => pickFile(e.target.files?.[0])}
                />
              </Box>
              <TextField
                label="Investigator notes (chain of custody)"
                multiline
                minRows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </>
          )}

          {job && (
            <Stack spacing={1.5} alignItems="center" sx={{ py: 2 }}>
              <StatusChip value={job.status} size="medium" />
              {processing && <LinearProgress sx={{ width: "100%" }} />}
              <Typography variant="body2" color="text.secondary" align="center">
                {job.status === "completed" &&
                  `Processed successfully${job.evidence_id ? ` as ${job.evidence_id}` : ""}. Chain of custody, hashes, and OCR artifacts are ready.`}
                {job.status === "failed" && (job.error || "Processing failed.")}
                {processing &&
                  "The Phase-1 pipeline is acquiring, hashing, preprocessing, and running OCR. This can take a minute for large files."}
              </Typography>
            </Stack>
          )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {!job ? (
          <>
            <Button onClick={handleClose}>Cancel</Button>
            <Button
              variant="contained"
              disabled={
                mutation.isPending || (mode === "url" ? !url.trim() : !file)
              }
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending
                ? "Submitting…"
                : mode === "url"
                  ? "Submit & Process"
                  : "Upload & Process"}
            </Button>
          </>
        ) : (
          <Button variant="contained" disabled={!!processing} onClick={handleClose}>
            {processing ? "Processing…" : "Done"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
