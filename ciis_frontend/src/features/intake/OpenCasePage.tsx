import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { intakeApi } from "@/api";
import { apiErrorMessage } from "@/lib/apiClient";

/** Step 2b: reopen a case by its reference. Never creates one. */
export default function OpenCasePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [reference, setReference] = useState(params.get("reference") ?? "");
  const [notFound, setNotFound] = useState(false);

  const open = useMutation({
    mutationFn: () => intakeApi.resolve(reference),
    onSuccess: (data) => {
      if (data.exists) navigate(`/cases/${data.case_id}/evidence`);
      else setNotFound(true);
    },
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setNotFound(false);
    if (reference.trim()) open.mutate();
  };

  return (
    <Box sx={{ maxWidth: 620, mx: "auto", py: { xs: 2, md: 5 } }}>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/")} sx={{ mb: 2 }}>
        Back
      </Button>

      <Card>
        <CardContent sx={{ p: { xs: 3, md: 4 } }}>
          <Stack spacing={1} sx={{ mb: 3 }}>
            <FolderOpenIcon color="primary" sx={{ fontSize: 40 }} />
            <Typography variant="h5">Open an existing case</Typography>
            <Typography variant="body2" color="text.secondary">
              Enter the reference you used when the case was created.
            </Typography>
          </Stack>

          <Box component="form" onSubmit={submit}>
            <Stack spacing={2.5}>
              <TextField
                label="Case reference"
                placeholder="e.g. esewa-lottery-scam-2026"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                required
                autoFocus
                fullWidth
              />

              {notFound && (
                <Alert
                  severity="warning"
                  action={
                    <Button size="small" onClick={() => navigate("/new")}>
                      Create it
                    </Button>
                  }
                >
                  No case found with that reference. Check the spelling, or create it as a
                  new case.
                </Alert>
              )}
              {open.isError && <Alert severity="error">{apiErrorMessage(open.error)}</Alert>}

              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={!reference.trim() || open.isPending}
              >
                {open.isPending ? "Looking up…" : "Open case"}
              </Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
