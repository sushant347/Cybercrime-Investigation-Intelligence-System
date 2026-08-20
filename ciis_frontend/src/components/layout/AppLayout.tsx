import { Box, Toolbar } from "@mui/material";
import { Outlet } from "react-router-dom";

import { ErrorBoundary } from "@/components/common/ErrorBoundary";

import { Topbar } from "./Topbar";

/** Single-column shell. No sidebar: the flow is one screen at a time. */
export function AppLayout() {
  return (
    <Box sx={{ minHeight: "100vh" }}>
      <Topbar />
      {/*
        The case assistant's floating button is fixed to the bottom-right at
        the same z-index as a dialog, so anything that ends up under it cannot
        be clicked. On the Reports tab that was the last "Download" button in
        the artifacts list: it sits at the very bottom of the page, right
        aligned, with nothing left to scroll past, so the button stayed pinned
        under the button and the PDF could not be fetched. Reserving the
        button's height plus its margin at the end of the page means every row
        can always be scrolled clear of it.
      */}
      <Box
        component="main"
        sx={{ p: { xs: 2, sm: 3 }, pb: { xs: 12, sm: 14 } }}
      >
        <Toolbar />
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </Box>
    </Box>
  );
}
