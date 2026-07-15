import PersonAddIcon from "@mui/icons-material/PersonAdd";
import {
  Alert,
  Box,
  Button,
  Card,
  CardHeader,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { authApi } from "@/api";
import { ErrorState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";
import type { Role } from "@/types";

const ROLES: Role[] = ["administrator", "investigator", "analyst", "viewer"];

interface NewUserForm {
  username: string;
  password: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  badge_number: string;
  department: string;
}

/** Module 1 (admin side) - users + configurable role permissions. */
export default function UsersPage() {
  const [tab, setTab] = useState<"users" | "permissions">("users");

  return (
    <Box>
      <PageHeader
        title="User Management"
        subtitle="Accounts and the configurable role → permission matrix"
      />
      <Tabs
        value={tab}
        onChange={(_, v: "users" | "permissions") => setTab(v)}
        sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}
      >
        <Tab value="users" label="Users" />
        <Tab value="permissions" label="Role Permissions" />
      </Tabs>
      {tab === "users" ? <UsersTable /> : <PermissionMatrix />}
    </Box>
  );
}

function UsersTable() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isPending, isError, error: qError, refetch } = useQuery({
    queryKey: ["users"],
    queryFn: () => authApi.listUsers({ page_size: 100 }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Record<string, unknown> }) =>
      authApi.updateUser(id, patch),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["users"] }),
    onError: (err) => setError(apiErrorMessage(err)),
  });

  const { register, handleSubmit, reset, formState } = useForm<NewUserForm>({
    defaultValues: { role: "viewer" } as NewUserForm,
  });

  const createMutation = useMutation({
    mutationFn: (values: NewUserForm) => authApi.createUser({ ...values }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      reset();
      setCreateOpen(false);
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  if (isPending) return <TableSkeleton />;
  if (isError) return <ErrorState message={apiErrorMessage(qError)} onRetry={() => void refetch()} />;

  return (
    <Card>
      <CardHeader
        title={`Accounts (${data.count})`}
        action={
          <Button
            variant="contained"
            startIcon={<PersonAddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            New User
          </Button>
        }
      />
      <Divider />
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Username</TableCell>
            <TableCell>Name</TableCell>
            <TableCell>Email</TableCell>
            <TableCell>Role</TableCell>
            <TableCell>Badge</TableCell>
            <TableCell>Active</TableCell>
            <TableCell>Last login</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.results.map((user) => (
            <TableRow key={user.id} hover>
              <TableCell sx={{ fontWeight: 600 }}>{user.username}</TableCell>
              <TableCell>
                {user.first_name} {user.last_name}
              </TableCell>
              <TableCell>{user.email}</TableCell>
              <TableCell>
                <TextField
                  select
                  size="small"
                  value={user.role}
                  onChange={(e) =>
                    updateMutation.mutate({ id: user.id, patch: { role: e.target.value } })
                  }
                  sx={{ minWidth: 150 }}
                >
                  {ROLES.map((role) => (
                    <MenuItem key={role} value={role} sx={{ textTransform: "capitalize" }}>
                      {role}
                    </MenuItem>
                  ))}
                </TextField>
              </TableCell>
              <TableCell>{user.badge_number || "—"}</TableCell>
              <TableCell>
                <Switch
                  checked={user.is_active}
                  onChange={(e) =>
                    updateMutation.mutate({ id: user.id, patch: { is_active: e.target.checked } })
                  }
                />
              </TableCell>
              <TableCell>{formatDateTime(user.last_login)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create User</DialogTitle>
        <form onSubmit={handleSubmit((v) => createMutation.mutate(v))} noValidate>
          <DialogContent>
            <Stack spacing={2}>
              <Stack direction="row" spacing={2}>
                <TextField
                  label="Username"
                  required
                  fullWidth
                  error={!!formState.errors.username}
                  {...register("username", { required: true })}
                />
                <TextField
                  label="Password"
                  type="password"
                  required
                  fullWidth
                  error={!!formState.errors.password}
                  {...register("password", { required: true, minLength: 8 })}
                />
              </Stack>
              <Stack direction="row" spacing={2}>
                <TextField label="First name" fullWidth {...register("first_name")} />
                <TextField label="Last name" fullWidth {...register("last_name")} />
              </Stack>
              <TextField label="Email" type="email" {...register("email")} />
              <Stack direction="row" spacing={2}>
                <TextField select label="Role" fullWidth defaultValue="viewer" {...register("role")}>
                  {ROLES.map((role) => (
                    <MenuItem key={role} value={role} sx={{ textTransform: "capitalize" }}>
                      {role}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField label="Badge number" fullWidth {...register("badge_number")} />
              </Stack>
              <TextField label="Department" {...register("department")} />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={createMutation.isPending}>
              Create
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Card>
  );
}

function PermissionMatrix() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string[]> | null>(null);
  const [savedRole, setSavedRole] = useState<string | null>(null);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["permission-matrix"],
    queryFn: authApi.permissionMatrix,
  });

  const saveMutation = useMutation({
    mutationFn: ({ role, permissions }: { role: string; permissions: string[] }) =>
      authApi.savePermissions(role, permissions),
    onSuccess: (_, variables) => {
      setSavedRole(variables.role);
      window.setTimeout(() => setSavedRole(null), 2500);
      void queryClient.invalidateQueries({ queryKey: ["permission-matrix"] });
    },
  });

  if (isPending) return <TableSkeleton />;
  if (isError) return <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />;

  const matrix = draft ?? data.matrix;

  const toggle = (role: string, permission: string) => {
    const current = matrix[role] ?? [];
    const next = current.includes(permission)
      ? current.filter((p) => p !== permission)
      : [...current, permission];
    setDraft({ ...matrix, [role]: next });
  };

  return (
    <Card>
      <CardHeader
        title="Role → Permission Matrix"
        subheader="Administrator role always retains every permission via superuser status. Changes apply immediately after saving a role."
      />
      <Divider />
      {savedRole && (
        <Alert severity="success">Permissions saved for role “{savedRole}”.</Alert>
      )}
      <Box sx={{ overflowX: "auto" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Permission</TableCell>
              {ROLES.map((role) => (
                <TableCell key={role} align="center" sx={{ textTransform: "capitalize" }}>
                  {role}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {data.available_permissions.map((perm) => (
              <TableRow key={perm.code} hover>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {perm.label}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {perm.code}
                  </Typography>
                </TableCell>
                {ROLES.map((role) => (
                  <TableCell key={role} align="center">
                    <Checkbox
                      size="small"
                      checked={(matrix[role] ?? []).includes(perm.code)}
                      onChange={() => toggle(role, perm.code)}
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
      <Divider />
      <Stack direction="row" spacing={1} sx={{ p: 2 }} justifyContent="flex-end">
        <Button onClick={() => setDraft(null)} disabled={!draft}>
          Discard changes
        </Button>
        {ROLES.map((role) => (
          <Button
            key={role}
            variant="outlined"
            size="small"
            disabled={!draft || saveMutation.isPending}
            onClick={() => saveMutation.mutate({ role, permissions: matrix[role] ?? [] })}
            sx={{ textTransform: "capitalize" }}
          >
            Save {role}
          </Button>
        ))}
      </Stack>
    </Card>
  );
}
