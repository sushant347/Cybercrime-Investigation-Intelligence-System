import GppGoodIcon from "@mui/icons-material/GppGood";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { apiErrorMessage } from "@/lib/apiClient";

import { useAuth } from "./AuthContext";

interface LoginForm {
  username: string;
  password: string;
}

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>();

  if (user) return <Navigate to="/" replace />;

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/";

  const onSubmit = async (data: LoginForm) => {
    setError(null);
    try {
      await login(data.username, data.password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        p: 2,
        background:
          "radial-gradient(1200px 600px at 20% -10%, rgba(61,126,255,0.25), transparent), radial-gradient(900px 500px at 110% 110%, rgba(0,194,168,0.18), transparent)",
      }}
    >
      <Card sx={{ width: "100%", maxWidth: 420 }}>
        <CardContent sx={{ p: 4 }}>
          <Stack spacing={3}>
            <Stack spacing={1} alignItems="center">
              <GppGoodIcon color="primary" sx={{ fontSize: 48 }} />
              <Typography variant="h5" align="center">
                CIIS
              </Typography>
              <Typography variant="body2" color="text.secondary" align="center">
                Cybercrime Investigation Intelligence System
                <br />
                Authorized personnel only. All activity is audited.
              </Typography>
            </Stack>

            {error && <Alert severity="error">{error}</Alert>}

            <form onSubmit={handleSubmit(onSubmit)} noValidate>
              <Stack spacing={2}>
                <TextField
                  label="Username"
                  autoComplete="username"
                  autoFocus
                  fullWidth
                  error={!!errors.username}
                  helperText={errors.username?.message}
                  {...register("username", { required: "Username is required" })}
                />
                <TextField
                  label="Password"
                  type="password"
                  autoComplete="current-password"
                  fullWidth
                  error={!!errors.password}
                  helperText={errors.password?.message}
                  {...register("password", { required: "Password is required" })}
                />
                <Button
                  type="submit"
                  variant="contained"
                  size="large"
                  disabled={isSubmitting}
                  startIcon={isSubmitting ? <CircularProgress size={18} /> : undefined}
                >
                  Sign in
                </Button>
              </Stack>
            </form>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
