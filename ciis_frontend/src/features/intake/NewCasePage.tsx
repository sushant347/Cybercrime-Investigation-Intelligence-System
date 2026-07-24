import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CreateNewFolderIcon from "@mui/icons-material/CreateNewFolder";
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
import { useNavigate } from "react-router-dom";

import { intakeApi } from "@/api";
import { apiErrorMessage } from "@/lib/apiClient";

/** Step 2a: name a new case, then go straight into it. */
export default function NewCasePage() {
  const navigate = useNavigate();
  const [reference, setReference] = useState("");
  const [title, setTitle] = useState("");
  const [taken, setTaken] = useState(false);

  const create = useMutation({
    mutationFn: async () => {
      // A reference maps to exactly one case, so refuse to silently reopen
      // someone else's work under the guise of creating a new case.
      const existing = await intakeApi.resolve(reference);
      if (existing.exists) {
        setTaken(true);
        return null;
      }
      return intakeApi.open(reference, title);
    },
    onSuccess: (data) => {
      if (data) navigate(`/cases/${data.case_id}/evidence`);
    },
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setTaken(false);
    if (reference.trim()) create.mutate();
  };

  return (
    <Box sx={{ maxWidth: 620, mx: "auto", py: { xs: 2, md: 5 } }}>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/")} sx={{ mb: 2 }}>
        Back
      </Button>

      <Card>
        <CardContent sx={{ p: { xs: 3, md: 4 } }}>
          <Stack spacing={1} sx={{ mb: 3 }}>
            <CreateNewFolderIcon color="primary" sx={{ fontSize: 40 }} />
            <Typography variant="h5">Start a new case</Typography>
            <Typography variant="body2" color="text.secondary">
              The reference is how you get back to this case later — there are no accounts,
              so write it down.
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
                helperText="Capitalisation and extra spaces don't matter."
              />
              <TextField
                label="Case title (optional)"
                placeholder="A short description of the case"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                fullWidth
              />

              {taken && (
                <Alert
                  severity="warning"
                  action={
                    <Button
                      size="small"
                      onClick={() =>
                        navigate(`/open?reference=${encodeURIComponent(reference)}`)
                      }
                    >
                      Open it
                    </Button>
                  }
                >
                  A case with this reference already exists.
                </Alert>
              )}
              {create.isError && <Alert severity="error">{apiErrorMessage(create.error)}</Alert>}

              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={!reference.trim() || create.isPending}
              >
                {create.isPending ? "Creating…" : "Create case"}
              </Button>
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
