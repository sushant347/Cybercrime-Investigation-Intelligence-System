import CloseIcon from "@mui/icons-material/Close";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import SendIcon from "@mui/icons-material/Send";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  Fab,
  IconButton,
  Link,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link as RouterLink } from "react-router-dom";

import { ragApi } from "@/api";
import { apiErrorMessage } from "@/lib/apiClient";
import type { RAGAnswer } from "@/types";

const SUGGESTIONS = [
  "Summarize the strongest findings in this case.",
  "Which evidence items are connected, and why?",
  "What happened first in the reconstructed timeline?",
  "Which legal sections are engaged, and what requires manual review?",
];

type ConversationItem =
  | { role: "investigator"; text: string }
  | { role: "assistant"; text: string; result?: RAGAnswer; error?: boolean };

function SourceCard({ caseId, source }: { caseId: string; source: RAGAnswer["cited_sources"][number] }) {
  const isEvidence = source.evidence_id.startsWith("EVID_");
  return (
    <Paper variant="outlined" sx={{ p: 1.25 }}>
      <Stack spacing={0.75}>
        <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
          <FactCheckIcon color="success" sx={{ fontSize: 18 }} />
          <Typography variant="caption" sx={{ fontWeight: 700, flex: 1 }}>
            {source.title || source.file_name}
          </Typography>
          <Chip size="small" variant="outlined" label={source.evidence_id} />
        </Stack>
        {isEvidence && (
          <Link
            component={RouterLink}
            to={`/cases/${caseId}/evidence/${source.evidence_id}`}
            variant="caption"
          >
            Open evidence
          </Link>
        )}
        {source.url && (
          <Link href={source.url} target="_blank" rel="noreferrer" variant="caption">
            Open primary source
          </Link>
        )}
        {source.supporting_evidence_ids.length > 0 && !isEvidence && (
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {source.supporting_evidence_ids.map((evidenceId) => (
              <Chip
                key={evidenceId}
                size="small"
                label={evidenceId}
                component={RouterLink}
                to={`/cases/${caseId}/evidence/${evidenceId}`}
                clickable
              />
            ))}
          </Stack>
        )}
      </Stack>
    </Paper>
  );
}

export function CaseAssistant({ caseId }: { caseId: string }) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const endRef = useRef<HTMLDivElement | null>(null);

  const status = useQuery({
    queryKey: ["rag-status", caseId],
    queryFn: () => ragApi.status(caseId),
    enabled: open,
    retry: false,
    staleTime: 15_000,
  });

  const ask = useMutation({
    mutationFn: (value: string) => ragApi.ask(caseId, value),
    onSuccess: (result) => {
      setConversation((items) => [
        ...items,
        { role: "assistant", text: result.answer, result },
      ]);
    },
    onError: (error) => {
      setConversation((items) => [
        ...items,
        { role: "assistant", text: apiErrorMessage(error), error: true },
      ]);
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [conversation, ask.isPending]);

  const submit = (event?: FormEvent, suggested?: string) => {
    event?.preventDefault();
    const value = (suggested ?? question).trim();
    if (!value || ask.isPending || !status.data?.available) return;
    setConversation((items) => [...items, { role: "investigator", text: value }]);
    setQuestion("");
    ask.mutate(value);
  };

  return (
    <>
      <Tooltip title="Ask about evidence, timeline, links, reports, or law">
        <Fab
          variant="extended"
          color="primary"
          aria-label="Open case assistant"
          onClick={() => setOpen(true)}
          sx={{ position: "fixed", right: { xs: 16, sm: 24 }, bottom: { xs: 16, sm: 24 }, zIndex: 1200 }}
        >
          <SmartToyOutlinedIcon sx={{ mr: 1 }} />
          Ask this case
        </Fab>
      </Tooltip>

      <Drawer
        anchor="right"
        open={open}
        onClose={() => setOpen(false)}
        PaperProps={{
          sx: { width: { xs: "100%", sm: 460 }, maxWidth: "100vw" },
        }}
      >
        <Stack sx={{ height: "100%" }}>
          <Stack direction="row" spacing={1.25} alignItems="center" sx={{ p: 2 }}>
            <SmartToyOutlinedIcon color="primary" />
            <Box sx={{ flex: 1 }}>
              <Typography variant="h6">Case Assistant</Typography>
              <Typography variant="caption" color="text.secondary">
                Answers only from stored case sources
              </Typography>
            </Box>
            <IconButton aria-label="Close case assistant" onClick={() => setOpen(false)}>
              <CloseIcon />
            </IconButton>
          </Stack>
          <Divider />

          <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
            {status.isPending && (
              <Stack direction="row" spacing={1} alignItems="center">
                <CircularProgress size={18} />
                <Typography variant="body2">Checking the case index…</Typography>
              </Stack>
            )}
            {status.isError && <Alert severity="error">{apiErrorMessage(status.error)}</Alert>}
            {status.data && !status.data.available && (
              <Alert severity="warning">{status.data.detail}</Alert>
            )}
            {status.data?.available && conversation.length === 0 && (
              <Stack spacing={2}>
                <Alert severity="info" icon={<FactCheckIcon />}>
                  Verify the cited evidence and primary sources before relying on an answer.
                </Alert>
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Useful starting questions
                  </Typography>
                  <Stack spacing={1}>
                    {SUGGESTIONS.map((suggestion) => (
                      <Button
                        key={suggestion}
                        variant="outlined"
                        size="small"
                        sx={{ justifyContent: "flex-start", textAlign: "left" }}
                        onClick={() => submit(undefined, suggestion)}
                      >
                        {suggestion}
                      </Button>
                    ))}
                  </Stack>
                </Box>
              </Stack>
            )}

            <Stack spacing={1.5} sx={{ mt: conversation.length ? 0 : 2 }}>
              {conversation.map((item, index) => (
                <Box
                  key={`${item.role}-${index}`}
                  sx={{ alignSelf: item.role === "investigator" ? "flex-end" : "stretch", maxWidth: item.role === "investigator" ? "88%" : "100%" }}
                >
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 1.5,
                      bgcolor: item.role === "investigator" ? "primary.main" : "background.paper",
                      color: item.role === "investigator" ? "primary.contrastText" : "text.primary",
                    }}
                  >
                    <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                      {item.text}
                    </Typography>
                  </Paper>
                  {item.role === "assistant" && item.error && (
                    <Alert severity="error" sx={{ mt: 1 }}>The question could not be answered.</Alert>
                  )}
                  {item.role === "assistant" && item.result && (
                    <Stack spacing={1} sx={{ mt: 1 }}>
                      {item.result.insufficient_evidence && (
                        <Alert severity="warning">The indexed evidence was insufficient for a supported answer.</Alert>
                      )}
                      {item.result.cited_sources.length > 0 && (
                        <Box>
                          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
                            Cited sources
                          </Typography>
                          <Stack spacing={0.75} sx={{ mt: 0.5 }}>
                            {item.result.cited_sources.map((source) => (
                              <SourceCard key={source.evidence_id} caseId={caseId} source={source} />
                            ))}
                          </Stack>
                        </Box>
                      )}
                      {item.result.warnings.map((warning) => (
                        <Alert key={warning} severity="info">{warning}</Alert>
                      ))}
                    </Stack>
                  )}
                </Box>
              ))}
              {ask.isPending && (
                <Stack direction="row" spacing={1} alignItems="center" sx={{ py: 1 }}>
                  <CircularProgress size={18} />
                  <Typography variant="body2" color="text.secondary">
                    Retrieving and checking citations…
                  </Typography>
                </Stack>
              )}
              <div ref={endRef} />
            </Stack>
          </Box>

          <Divider />
          <Box component="form" onSubmit={(event) => submit(event)} sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} alignItems="flex-end">
              <TextField
                fullWidth
                multiline
                maxRows={4}
                size="small"
                label="Ask about this case"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                inputProps={{ maxLength: 2000 }}
                disabled={!status.data?.available || ask.isPending}
              />
              <IconButton
                type="submit"
                color="primary"
                aria-label="Send question"
                disabled={!question.trim() || !status.data?.available || ask.isPending}
              >
                <SendIcon />
              </IconButton>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>
              Case-scoped retrieval · cited answers · no evidence is sent to a remote model by default
            </Typography>
          </Box>
        </Stack>
      </Drawer>
    </>
  );
}
