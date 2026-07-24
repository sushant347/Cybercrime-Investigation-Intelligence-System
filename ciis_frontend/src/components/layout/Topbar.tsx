import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import NotificationsIcon from "@mui/icons-material/Notifications";
import {
  AppBar,
  Avatar,
  Badge,
  Divider,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { notificationsApi } from "@/api";
import { useAuth } from "@/features/auth/AuthContext";
import { NotificationsPopover } from "@/features/notifications/NotificationsPopover";
import { useColorMode } from "@/theme/ColorModeProvider";

import { SIDEBAR_WIDTH } from "./Sidebar";

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, logout } = useAuth();
  const { mode, toggle } = useColorMode();
  const navigate = useNavigate();
  const [userMenuEl, setUserMenuEl] = useState<HTMLElement | null>(null);
  const [notifEl, setNotifEl] = useState<HTMLElement | null>(null);

  const { data: unread } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => notificationsApi.list({ unread: 1, page_size: 1 }),
    refetchInterval: 30_000,
  });

  const handleLogout = async () => {
    setUserMenuEl(null);
    await logout();
    navigate("/login");
  };

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

        <Tooltip title="Account">
          <IconButton onClick={(e) => setUserMenuEl(e.currentTarget)} sx={{ ml: 0.5 }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: "primary.main", fontSize: 14 }}>
              {(user?.first_name?.[0] ?? user?.username?.[0] ?? "?").toUpperCase()}
            </Avatar>
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={userMenuEl}
          open={!!userMenuEl}
          onClose={() => setUserMenuEl(null)}
        >
          <Stack sx={{ px: 2, py: 1 }}>
            <Typography variant="subtitle2">
              {user?.first_name} {user?.last_name}
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ textTransform: "capitalize" }}
            >
              {user?.role}
            </Typography>
          </Stack>
          <Divider />
          <MenuItem onClick={handleLogout}>
            <ListItemIcon>
              <LogoutIcon fontSize="small" />
            </ListItemIcon>
            Sign out
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
}
