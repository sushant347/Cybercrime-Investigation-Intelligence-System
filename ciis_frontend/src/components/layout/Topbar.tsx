import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import MenuIcon from "@mui/icons-material/Menu";
import NotificationsIcon from "@mui/icons-material/Notifications";
import {
  AppBar,
  Badge,
  IconButton,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { notificationsApi } from "@/api";
import { NotificationsPopover } from "@/features/notifications/NotificationsPopover";
import { useColorMode } from "@/theme/ColorModeProvider";

import { SIDEBAR_WIDTH } from "./Sidebar";

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { mode, toggle } = useColorMode();
  const [notifEl, setNotifEl] = useState<HTMLElement | null>(null);

  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => notificationsApi.list({ unread: 1, page_size: 1 }),
    refetchInterval: 30_000,
  });

  return (
    <AppBar
      position="fixed"
      color="inherit"
      elevation={0}
      sx={{
        width: { md: `calc(100% - ${SIDEBAR_WIDTH}px)` },
        ml: { md: `${SIDEBAR_WIDTH}px` },
        borderBottom: 1,
        borderColor: "divider",
        backdropFilter: "blur(8px)",
      }}
    >
      <Toolbar sx={{ gap: 1 }}>
        <IconButton
          edge="start"
          onClick={onMenuClick}
          sx={{ display: { md: "none" } }}
          aria-label="Open navigation"
        >
          <MenuIcon />
        </IconButton>
        <Typography variant="subtitle1" sx={{ flex: 1, fontWeight: 700 }}>
          Cybercrime Investigation Intelligence System
        </Typography>

        <Tooltip title={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
          <IconButton onClick={toggle} aria-label="Toggle theme">
            {mode === "dark" ? <LightModeIcon /> : <DarkModeIcon />}
          </IconButton>
        </Tooltip>

        <Tooltip title="Notifications">
          <IconButton
            onClick={(e) => setNotifEl(e.currentTarget)}
            aria-label="Open notifications"
          >
            <Badge badgeContent={unread?.unread_count ?? 0} color="error" max={99}>
              <NotificationsIcon />
            </Badge>
          </IconButton>
        </Tooltip>
        <NotificationsPopover anchorEl={notifEl} onClose={() => setNotifEl(null)} />
      </Toolbar>
    </AppBar>
  );
}
