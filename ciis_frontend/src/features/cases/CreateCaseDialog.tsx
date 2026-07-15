import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
} from "@mui/material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { casesApi } from "@/api";
import { apiErrorMessage } from "@/lib/apiClient";

interface FormValues {
  title: string;
  description: string;
  notes: string;
  tags: string;
}

export function CreateCaseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: { title: "", description: "", notes: "", tags: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      casesApi.create({
        title: values.title,
        description: values.description,
        notes: values.notes,
        tags: values.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      reset();
      onClose();
      navigate(`/cases/${created.case_id}`);
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Open New Case</DialogTitle>
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} noValidate>
        <DialogContent>
          <Stack spacing={2}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="Case title"
              autoFocus
              required
              error={!!errors.title}
              helperText={errors.title?.message}
              {...register("title", { required: "A case title is required" })}
            />
            <TextField
              label="Description"
              multiline
              minRows={2}
              {...register("description")}
            />
            <TextField
              label="Investigator notes"
              multiline
              minRows={2}
              {...register("notes")}
            />
            <TextField
              label="Tags (comma separated)"
              placeholder="phishing, esewa, sms-scam"
              {...register("tags")}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create Case"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
