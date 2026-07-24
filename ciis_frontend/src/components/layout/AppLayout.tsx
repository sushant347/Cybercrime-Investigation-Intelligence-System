import { Box, Toolbar } from "@mui/material";
import { Outlet } from "react-router-dom";

import { ErrorBoundary } from "@/components/common/ErrorBoundary";

import { Topbar } from "./Topbar";

/** Single-column shell. No sidebar: the flow is one screen at a time. */
export function AppLayout() {
  return (
    <Box sx={{ minHeight: "100vh" }}>
      <Topbar />
      <Box component="main" sx={{ p: { xs: 2, sm: 3 } }}>
        <Toolbar />
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </Box>
    </Box>
  );
}
