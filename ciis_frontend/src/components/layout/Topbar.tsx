import DarkModeIcon from "@mui/icons-material/DarkMode";
import GppGoodIcon from "@mui/icons-material/GppGood";
import LightModeIcon from "@mui/icons-material/LightMode";
import { AppBar, Box, IconButton, Stack, Toolbar, Tooltip, Typography } from "@mui/material";
import { Link } from "react-router-dom";

import { useColorMode } from "@/theme/ColorModeProvider";

/** Minimal header: identity and theme only - no navigation, no case list. */
export function Topbar() {
  const { mode, toggle } = useColorMode();

  return (
    <AppBar
      position="fixed"
      color="inherit"
      elevation={0}
      sx={{ borderBottom: 1, borderColor: "divider", backdropFilter: "blur(8px)" }}
    >
      <Toolbar sx={{ gap: 1 }}>
        <Stack
          component={Link}
          to="/"
          direction="row"
          spacing={1.25}
          alignItems="center"
          sx={{ flex: 1, textDecoration: "none", color: "inherit" }}
        >
          <Box
            sx={{
              display: "grid",
              placeItems: "center",
              width: 34,
              height: 34,
              borderRadius: 2,
              bgcolor: "rgba(61,126,255,0.12)",
              color: "primary.main",
            }}
          >
            <GppGoodIcon fontSize="small" />
          </Box>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
              CIIS
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: { xs: "none", sm: "block" }, lineHeight: 1.2 }}
            >
              Cybercrime Investigation Intelligence Engine
            </Typography>
          </Box>
        </Stack>

        <Tooltip title={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
          <IconButton onClick={toggle} aria-label="Toggle theme">
            {mode === "dark" ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Tooltip>
      </Toolbar>
    </AppBar>
  );
}
