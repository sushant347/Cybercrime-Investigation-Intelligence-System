import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CloseIcon from "@mui/icons-material/Close";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { evidenceApi } from "@/api";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatBytes } from "@/lib/format";

const ACCEPT = ".png,.jpg,.jpeg,.pdf,.txt,.csv,.docx";
const POLL_MS = 2500;

type ItemStatus = "waiting" | "uploading" | "processing" | "completed" | "failed";

interface QueueItem {
  file: File;
  status: ItemStatus;
  evidenceId?: string;
  error?: string;
}

/**
 * Multi-file evidence upload.
 *
 * Files are sent ONE at a time and each is polled to completion before the
 * next starts. The backend serialises Phase-1 processing behind a single
 * pipeline lock anyway (engine CSV storage is not concurrent-safe), so
 * parallel uploads would only queue server-side with no visibility — this
 * way the queue lives client-side where the investigator can see it.
 */
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
  const [items, setItems] = useState<QueueItem[]>([]);
  const [notes, setNotes] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [running, setRunning] = useState(false);
  // Guards the async loop against state updates after unmount/close.
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  const reset = useCallback(() => {
    setItems([]);
    setNotes("");
    setRunning(false);
  }, []);

  const handleClose = () => {
    if (running) return; // finish the queue first — closing mid-run loses status
    reset();
    onClose();
  };

  const addFiles = (list: FileList | File[] | null | undefined) => {
    if (!list) return;
    const incoming = Array.from(list);
    setItems((prev) => {
      // De-dupe on name+size so dropping the same selection twice is harmless.
      const seen = new Set(prev.map((i) => `${i.file.name}:${i.file.size}`));
      const fresh = incoming
        .filter((f) => !seen.has(`${f.name}:${f.size}`))
        .map<QueueItem>((file) => ({ file, status: "waiting" }));
      return [...prev, ...fresh];
    });
  };

  const removeItem = (index: number) =>
    setItems((prev) => prev.filter((_, i) => i !== index));

  const patch = (index: number, changes: Partial<QueueItem>) =>
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...changes } : it)));

  const refreshCaseQueries = () => {
    void queryClient.invalidateQueries({ queryKey: ["evidence", caseId] });
    void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
    void queryClient.invalidateQueries({ queryKey: ["artifact", caseId] });
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const runQueue = async () => {
    setRunning(true);
    // Snapshot indexes of everything still waiting (supports "add more, run again").
    const pending = items
      .map((it, i) => ({ it, i }))
      .filter(({ it }) => it.status === "waiting" || it.status === "failed");

    for (const { it, i } of pending) {
      if (cancelled.current) break;
      patch(i, { status: "uploading", error: undefined });
      try {
        const job = await evidenceApi.upload(caseId, it.file, notes);
        patch(i, { status: "processing" });
        // Poll this job until it settles. Transient poll failures (dev-server
        // restart, brief timeout) are retried, not treated as job failure.
        let done = false;
        while (!done && !cancelled.current) {
          await sleep(POLL_MS);
          try {
            const latest = await evidenceApi.job(job.id);
            if (latest.status === "completed") {
              patch(i, { status: "completed", evidenceId: latest.evidence_id });
              done = true;
            } else if (latest.status === "failed") {
              patch(i, { status: "failed", error: latest.error || "Processing failed." });
              done = true;
            }
          } catch {
            // keep polling — the job is still running server-side
          }
        }
        // Evidence list updates after every file, not only at the end.
        refreshCaseQueries();
      } catch (err) {
        patch(i, { status: "failed", error: apiErrorMessage(err) });
      }
    }
    if (!cancelled.current) setRunning(false);
  };

  const waiting = items.filter((i) => i.status === "waiting" || i.status === "failed");
  const completedCount = items.filter((i) => i.status === "completed").length;
  const failedCount = items.filter((i) => i.status === "failed").length;
  const allSettled =
    items.length > 0 && items.every((i) => i.status === "completed" || i.status === "failed");

  const statusIcon = (status: ItemStatus) => {
    switch (status) {
      case "completed":
        return <CheckCircleIcon color="success" fontSize="small" />;
      case "failed":
        return <ErrorIcon color="error" fontSize="small" />;
      case "uploading":
      case "processing":
        return <CircularProgress size={18} />;
      default:
        return <HourglassEmptyIcon color="disabled" fontSize="small" />;
    }
  };

  const statusText = (it: QueueItem) => {
    switch (it.status) {
      case "waiting":
        return formatBytes(it.file.size);
      case "uploading":
        return "Uploading…";
      case "processing":
        return "OCR + entity extraction…";
      case "completed":
        return it.evidenceId ? `Processed as ${it.evidenceId}` : "Processed";
      case "failed":
        return it.error || "Failed";
    }
  };

  return (
    <Dialog open={open} onClose={running ? undefined : handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Upload Evidence — {caseId}</DialogTitle>
      <DialogContent>
        <Stack spacing={2}>
          {!running && (
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
                addFiles(e.dataTransfer.files);
              }}
              sx={{
                border: "2px dashed",
                borderColor: dragOver ? "primary.main" : "divider",
                borderRadius: 2,
                p: 3,
                textAlign: "center",
                cursor: "pointer",
                bgcolor: dragOver ? "action.hover" : "transparent",
              }}
            >
              <CloudUploadIcon color="primary" sx={{ fontSize: 40 }} />
              <Typography variant="subtitle1">
                Drop files here or click to browse
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Multiple files supported — PNG, JPG, PDF, TXT, CSV, DOCX, max 50 MB each.
                SHA-256 is computed on acquisition.
              </Typography>
              <input
                ref={inputRef}
                hidden
                multiple
                type="file"
                accept={ACCEPT}
                onChange={(e) => {
                  addFiles(e.target.files);
                  e.target.value = ""; // allow re-selecting the same files
                }}
              />
            </Box>
          )}

          {items.length > 0 && (
            <List dense disablePadding sx={{ border: 1, borderColor: "divider", borderRadius: 2 }}>
              {items.map((it, i) => (
                <ListItem
                  key={`${it.file.name}:${it.file.size}`}
                  divider={i < items.length - 1}
                  secondaryAction={
                    !running && it.status === "waiting" ? (
                      <IconButton edge="end" size="small" onClick={() => removeItem(i)}>
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    ) : undefined
                  }
                >
                  <ListItemIcon sx={{ minWidth: 34 }}>{statusIcon(it.status)}</ListItemIcon>
                  <ListItemText
                    primary={it.file.name}
                    secondary={statusText(it)}
                    primaryTypographyProps={{ variant: "body2", noWrap: true }}
                    secondaryTypographyProps={{
                      variant: "caption",
                      color: it.status === "failed" ? "error" : "text.secondary",
                    }}
                  />
                </ListItem>
              ))}
            </List>
          )}

          {running && (
            <Stack spacing={1}>
              <LinearProgress
                variant="determinate"
                value={items.length ? (completedCount + failedCount) / items.length * 100 : 0}
              />
              <Typography variant="caption" color="text.secondary" align="center">
                Processing {completedCount + failedCount + 1 > items.length
                  ? items.length
                  : completedCount + failedCount + 1} of {items.length} — each file runs
                acquisition, hashing, OCR, and entity extraction. Large images take longer.
              </Typography>
            </Stack>
          )}

          {allSettled && !running && (
            <Alert severity={failedCount ? "warning" : "success"}>
              {completedCount} file{completedCount === 1 ? "" : "s"} processed
              {failedCount
                ? `, ${failedCount} failed — you can retry the failed ones with Upload.`
                : ". Chain of custody, hashes, and OCR artifacts are ready."}
            </Alert>
          )}

          {!running && (
            <TextField
              label="Investigator notes (chain of custody)"
              multiline
              minRows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              helperText={items.length > 1 ? "Applied to every file in this batch." : undefined}
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={running}>
          {allSettled ? "Done" : "Cancel"}
        </Button>
        <Button
          variant="contained"
          disabled={running || waiting.length === 0}
          onClick={() => void runQueue()}
        >
          {running
            ? "Processing…"
            : failedCount && completedCount + failedCount === items.length
              ? `Retry ${failedCount} failed`
              : `Upload ${waiting.length || ""} & Process`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
