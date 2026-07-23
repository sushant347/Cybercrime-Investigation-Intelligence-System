import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import LoginIcon from "@mui/icons-material/Login";
import ScienceIcon from "@mui/icons-material/Science";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { intakeApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";

/**
 * Case intake - the engine's front door.
 *
 * No accounts: an investigator types a case reference, which the engine hashes
 * into a stable case id. Entering the same reference again reopens the same
 * case with its evidence and reports.
 */
export default function IntakePage() {
  const navigate = useNavigate();
  const [reference, setReference] = useState("");
  const [title, setTitle] = useState("");

  const casesQuery = useQuery({
    queryKey: ["intake", "cases"],
    queryFn: intakeApi.list,
  });

  const openCase = useMutation({
    mutationFn: () => intakeApi.open(reference, title),
    onSuccess: (data) => navigate(`/cases/${data.case_id}/evidence`),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (reference.trim()) openCase.mutate();
  };

  const cases = casesQuery.data?.cases ?? [];

  return (
    <Box>
      <PageHeader
        title="Evidence Intake"
        subtitle="Open a case by its reference, add evidence files, and the engine produces the analysis and report"
      />

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="flex-start">
        <Card sx={{ flex: "1 1 420px", width: "100%" }}>
          <CardHeader
            title="Open or start a case"
            subheader="The reference is your handle - type the same one later to return to this case"
          />
          <Divider />
          <CardContent>
            <Box component="form" onSubmit={submit}>
              <Stack spacing={2}>
                <TextField
                  label="Case reference"
                  placeholder="e.g. nabil-bank-phishing-2026"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  required
                  autoFocus
                  fullWidth
                  helperText="Case- and spacing-insensitive. The engine hashes this into a unique case id."
                />
                <TextField
                  label="Title (optional)"
                  placeholder="Shown in listings; defaults to the reference"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  fullWidth
                />
                {openCase.isError && (
                  <Alert severity="error">{apiErrorMessage(openCase.error)}</Alert>
                )}
                <Button
                  type="submit"
                  variant="contained"
                  size="large"
                  startIcon={<LoginIcon />}
                  disabled={!reference.trim() || openCase.isPending}
                >
                  {openCase.isPending ? "Opening…" : "Open case"}
                </Button>
              </Stack>
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ flex: "1 1 420px", width: "100%" }}>
          <CardHeader
            title="How it works"
            subheader="Case-centric digital evidence processing"
            avatar={<ScienceIcon color="primary" />}
          />
          <Divider />
          <CardContent>
            <Stack spacing={1.5}>
              {[
                "Enter a case reference — it is hashed into a unique case id, so the same reference always reopens the same case.",
                "Upload evidence (images, PDFs, chat exports). Each file is hashed for chain of custody and read by the OCR engine.",
                "Run the analysis — correlation, relationship graph, timeline, campaigns, suspects, and case priority.",
                "Read the report: charts and findings generated from your evidence, downloadable as JSON or Markdown.",
              ].map((line, i) => (
                <Stack key={i} direction="row" spacing={1.5} alignItems="flex-start">
                  <Chip label={i + 1} size="small" color="primary" />
                  <Typography variant="body2">{line}</Typography>
                </Stack>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Stack>

      <Card sx={{ mt: 2 }}>
        <CardHeader
          title="Registered cases"
          subheader="Recorded in storage/case_registry.csv — no database"
        />
        <Divider />
        {casesQuery.isPending ? (
          <TableSkeleton />
        ) : cases.length === 0 ? (
          <EmptyState
            icon={<FolderOpenIcon />}
            title="No cases yet"
            description="Open a case above to get started — the engine will register it in the CSV case registry."
          />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Reference</TableCell>
                <TableCell>Case ID</TableCell>
                <TableCell>Title</TableCell>
                <TableCell align="right">Evidence</TableCell>
                <TableCell>Last opened</TableCell>
                <TableCell align="right" />
              </TableRow>
            </TableHead>
            <TableBody>
              {cases.map((c) => (
                <TableRow key={c.case_id} hover>
                  <TableCell>{c.case_reference}</TableCell>
                  <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                    {c.case_id}
                  </TableCell>
                  <TableCell>{c.title}</TableCell>
                  <TableCell align="right">{c.evidence_count}</TableCell>
                  <TableCell>{formatDateTime(c.last_opened_at || c.created_at)}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => navigate(`/cases/${c.case_id}/evidence`)}>
                      Open
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </Box>
  );
}
