import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CloseIcon from "@mui/icons-material/Close";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import LinkIcon from "@mui/icons-material/Link";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
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
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { evidenceApi } from "@/api";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatBytes } from "@/lib/format";
import type { JobStage } from "@/types";

import { ProcessingStages } from "./ProcessingStages";

const ACCEPT = ".png,.jpg,.jpeg,.pdf,.txt,.csv,.docx";
/** Fast enough that each engine step is actually visible as it happens. */
const POLL_MS = 1100;
/** First check comes sooner: a small screenshot is often already done. */
const FIRST_POLL_MS = 500;

type ItemStatus =
  | "waiting"
  | "uploading"
  | "processing"
  | "completed"
  | "completed_with_warnings"
  | "failed";

type Mode = "file" | "url";

/**
 * One queued piece of evidence: either an uploaded file or a submitted link.
 * Links go through the same Phase-1 pipeline (hashing, chain of custody,
 * entity extraction) — they are just extracted differently server-side.
 */
interface QueueItem {
  /** Display name: the file name, or the link itself. */
  label: string;
  /** Stable de-dupe key within the queue. */
  key: string;
  file?: File;
  url?: string;
  status: ItemStatus;
  evidenceId?: string;
  error?: string;
  /** Live engine step for this item, mirrored from its job. */
  stage?: string;
  stageNote?: string;
  stages?: JobStage[];
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
  const [mode, setMode] = useState<Mode>("file");
  const [urlDraft, setUrlDraft] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
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
    setMode("file");
    setUrlDraft("");
    setUrlError(null);
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
      const seen = new Set(prev.map((i) => i.key));
      const fresh = incoming
        .filter((f) => !seen.has(`file:${f.name}:${f.size}`))
        .map<QueueItem>((file) => ({
          file,
          label: file.name,
          key: `file:${file.name}:${file.size}`,
          status: "waiting",
        }));
      return [...prev, ...fresh];
    });
  };

  /** Queue the link currently typed in the URL tab. */
  const addLink = () => {
    const url = urlDraft.trim();
    if (!url) return;
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        throw new Error("protocol");
      }
    } catch {
      setUrlError("Enter a full http:// or https:// link.");
      return;
    }
    setUrlError(null);
    setItems((prev) =>
      prev.some((i) => i.key === `url:${url}`)
        ? prev
        : [...prev, { url, label: url, key: `url:${url}`, status: "waiting" }],
    );
    setUrlDraft("");
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

  /**
   * Upload everything first, then watch the jobs.
   *
   * This used to run the whole cycle per file: upload, then sit polling until
   * the server had finished OCR, entity extraction, forensics *and* the
   * timeline/graph rebuild before even sending the next file. Ten screenshots
   * meant ten full round trips end to end, with the network idle for most of
   * it — and because only one job was ever queued, the server rebuilt the
   * case graph once per file instead of once for the batch.
   *
   * Submitting first means transfer overlaps with processing, and the server
   * sees the whole burst at once (it coalesces the artifact rebuild to the
   * last item). Processing itself is still serialised server-side by the
   * engine's pipeline lock — that is a storage-safety constraint, not a
   * latency one we can remove here.
   */
  const runQueue = async () => {
    setRunning(true);
    // Snapshot indexes of everything still waiting (supports "add more, run again").
    const pending = items
      .map((it, i) => ({ it, i }))
      .filter(({ it }) => it.status === "waiting" || it.status === "failed");

    // ---- phase 1: submit -------------------------------------------------
    const jobs: { index: number; jobId: number }[] = [];
    for (const { it, i } of pending) {
      if (cancelled.current) break;
      patch(i, { status: "uploading", error: undefined });
      try {
        const job = it.url
          ? await evidenceApi.submitUrl(caseId, it.url, notes)
          : await evidenceApi.upload(caseId, it.file!, notes);
        patch(i, { status: "processing" });
        jobs.push({ index: i, jobId: job.id });
      } catch (err) {
        patch(i, { status: "failed", error: apiErrorMessage(err) });
      }
    }

    // ---- phase 2: watch --------------------------------------------------
    const outstanding = new Map(jobs.map((j) => [j.jobId, j.index]));
    let firstPoll = true;
    while (outstanding.size > 0 && !cancelled.current) {
      // Poll quickly once (small files often finish fast), then back off.
      await sleep(firstPoll ? FIRST_POLL_MS : POLL_MS);
      firstPoll = false;
      const settled: number[] = [];
      await Promise.all(
        [...outstanding].map(async ([jobId, index]) => {
          try {
            const latest = await evidenceApi.job(jobId);
            // Mirror the engine's real step onto the row on every poll, so the
            // investigator watches the work rather than an opaque spinner.
            const progress = {
              stage: latest.stage,
              stageNote: latest.stage_note,
              stages: latest.stages ?? [],
            };
            if (latest.status === "completed") {
              patch(index, {
                ...progress,
                status: "completed",
                evidenceId: latest.evidence_id,
              });
              settled.push(jobId);
            } else if (latest.status === "completed_with_warnings") {
              patch(index, {
                ...progress,
                status: "completed_with_warnings",
                evidenceId: latest.evidence_id,
                error: latest.detail,
              });
              settled.push(jobId);
            } else if (latest.status === "failed") {
              patch(index, {
                ...progress,
                status: "failed",
                error: latest.error || "Processing failed.",
              });
              settled.push(jobId);
            } else {
              patch(index, progress);
            }
          } catch {
            // Transient poll failure (dev-server restart, brief timeout):
            // keep watching — the job is still running server-side.
          }
        }),
      );
      if (settled.length) {
        settled.forEach((id) => outstanding.delete(id));
        // Reflect progress as items land, not only at the very end.
        refreshCaseQueries();
      }
    }

    refreshCaseQueries();
    if (!cancelled.current) setRunning(false);
  };

  const waiting = items.filter((i) => i.status === "waiting" || i.status === "failed");
  const completedCount = items.filter(
    (i) => i.status === "completed" || i.status === "completed_with_warnings",
  ).length;
  const failedCount = items.filter((i) => i.status === "failed").length;
  const allSettled =
    items.length > 0 &&
    items.every(
      (i) =>
        i.status === "completed" ||
        i.status === "completed_with_warnings" ||
        i.status === "failed",
    );

  const statusIcon = (status: ItemStatus) => {
    switch (status) {
      case "completed":
        return <CheckCircleIcon color="success" fontSize="small" />;
      case "completed_with_warnings":
        return <WarningAmberIcon color="warning" fontSize="small" />;
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
        return it.url ? "Link — ready to submit" : formatBytes(it.file!.size);
      case "uploading":
        return "Transferring to the engine…";
      case "processing":
        // The per-step bar below carries the live detail; don't repeat it here.
        return it.url ? "Link submitted — processing" : "In the engine";
      case "completed":
        return it.evidenceId ? `Processed as ${it.evidenceId}` : "Processed";
      case "completed_with_warnings":
        return it.error || "Processed with warnings";
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
            <Tabs
              value={mode}
              onChange={(_, next: Mode) => setMode(next)}
              sx={{ borderBottom: 1, borderColor: "divider" }}
            >
              <Tab value="file" label="Upload files" />
              <Tab value="url" label="Submit a link" />
            </Tabs>
          )}

          {!running && mode === "url" && (
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <TextField
                label="Evidence URL"
                placeholder="https://suspicious-site.example/login"
                value={urlDraft}
                onChange={(e) => {
                  setUrlDraft(e.target.value);
                  setUrlError(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addLink();
                  }
                }}
                error={!!urlError}
                helperText={
                  urlError ??
                  "Hashed and logged like any other evidence, then matched across cases."
                }
                fullWidth
                size="small"
              />
              <Button
                variant="outlined"
                startIcon={<LinkIcon />}
                onClick={addLink}
                disabled={!urlDraft.trim()}
                sx={{ mt: 0.25, flexShrink: 0 }}
              >
                Add
              </Button>
            </Stack>
          )}

          {!running && mode === "file" && (
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
              {items.map((it, i) => {
                const showStages =
                  it.status === "processing" ||
                  it.status === "completed" ||
                  it.status === "completed_with_warnings" ||
                  (it.status === "failed" && (it.stages?.length ?? 0) > 0);
                return (
                  <ListItem
                    key={it.key}
                    divider={i < items.length - 1}
                    alignItems="flex-start"
                    sx={{ display: "block", py: 1.25 }}
                    secondaryAction={
                      !running && it.status === "waiting" ? (
                        <IconButton edge="end" size="small" onClick={() => removeItem(i)}>
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      ) : undefined
                    }
                  >
                    <Stack direction="row" spacing={1} alignItems="flex-start">
                      <Box sx={{ pt: 0.25 }}>{statusIcon(it.status)}</Box>
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="body2" noWrap title={it.label}>
                          {it.label}
                        </Typography>
                        <Typography
                          variant="caption"
                          color={
                            it.status === "failed"
                              ? "error"
                              : it.status === "completed_with_warnings"
                                ? "warning.main"
                                : "text.secondary"
                          }
                          sx={{ display: "block", overflowWrap: "anywhere" }}
                        >
                          {statusText(it)}
                        </Typography>
                        {showStages && (
                          <Box sx={{ mt: 1 }}>
                            <ProcessingStages
                              current={it.stage ?? ""}
                              note={it.stageNote}
                              stages={it.stages ?? []}
                              done={
                                it.status === "completed" ||
                                it.status === "completed_with_warnings"
                              }
                              failed={it.status === "failed"}
                            />
                          </Box>
                        )}
                      </Box>
                    </Stack>
                  </ListItem>
                );
              })}
            </List>
          )}

          {running && (
            <Stack spacing={1}>
              <LinearProgress
                variant="determinate"
                value={items.length ? ((completedCount + failedCount) / items.length) * 100 : 0}
              />
              <Typography variant="caption" color="text.secondary" align="center">
                {completedCount + failedCount} of {items.length} finished. Hover any step above
                to see what it does; the engine processes one item at a time so the case
                records stay consistent.
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
              : `Submit ${waiting.length || ""} & Process`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
