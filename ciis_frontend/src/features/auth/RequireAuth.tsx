import { Box, CircularProgress } from "@mui/material";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";

import { useAuth } from "./AuthContext";

export function RequireAuth({
  children,
  permission,
}: {
  children: ReactNode;
  permission?: string;
}) {
  const { user, initializing, hasPermission } = useAuth();
  const location = useLocation();

  if (initializing) {
    return (
      <Box sx={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (permission && !hasPermission(permission)) {
    return (
      <EmptyState
        title="Access restricted"
        description={`Your role (${user.role}) does not include the '${permission}' permission. Contact an administrator if you believe this is a mistake.`}
      />
    );
  }
  return <>{children}</>;
}
