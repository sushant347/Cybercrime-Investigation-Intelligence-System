import FactCheckIcon from "@mui/icons-material/FactCheck";
import FolderSpecialIcon from "@mui/icons-material/FolderSpecial";
import GppGoodIcon from "@mui/icons-material/GppGood";
import NotificationsIcon from "@mui/icons-material/Notifications";
import SettingsIcon from "@mui/icons-material/Settings";
import SpaceDashboardIcon from "@mui/icons-material/SpaceDashboard";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import {
  Box,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { NavLink } from "react-router-dom";

export const SIDEBAR_WIDTH = 248;

const NAV_ITEMS = [
  { to: "/", label: "Evidence Intake", icon: <UploadFileIcon /> },
  { to: "/cases", label: "Cases", icon: <FolderSpecialIcon /> },
  { to: "/dashboard", label: "Dashboard", icon: <SpaceDashboardIcon /> },
  { to: "/audit", label: "Audit Log", icon: <FactCheckIcon /> },
  { to: "/notifications", label: "Notifications", icon: <NotificationsIcon /> },
  { to: "/settings", label: "Settings", icon: <SettingsIcon /> },
] as const;

export function Sidebar({
  mobileOpen,
  onClose,
}: {
  mobileOpen: boolean;
  onClose: () => void;
}) {
  const content = (
    <Stack sx={{ height: "100%" }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ p: 2.5 }}>
        <GppGoodIcon color="primary" sx={{ fontSize: 34 }} />
        <Box>
          <Typography variant="h6" sx={{ lineHeight: 1.1 }}>
            CIIS
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Investigation Platform
          </Typography>
        </Box>
      </Stack>
      <Divider />
      <List sx={{ px: 1.5, py: 2, flex: 1 }}>
        {NAV_ITEMS.map(
          (item) => (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              onClick={onClose}
              end={item.to === "/"}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                "&.active": {
                  bgcolor: "primary.main",
                  color: "#fff",
                  "& .MuiListItemIcon-root": { color: "#fff" },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>{item.icon}</ListItemIcon>
              <ListItemText
                primary={item.label}
                slotProps={{ primary: { fontWeight: 600, fontSize: "0.9rem" } }}
              />
            </ListItemButton>
          ),
        )}
      </List>
      <Divider />
      <Stack sx={{ p: 2 }} spacing={0.25}>
        <Typography variant="subtitle2">Case-centric engine</Typography>
        <Typography variant="caption" color="text.secondary">
          CSV storage · no accounts
        </Typography>
      </Stack>
    </Stack>
  );

  return (
    <>
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: "block", md: "none" },
          "& .MuiDrawer-paper": { width: SIDEBAR_WIDTH },
        }}
      >
        {content}
      </Drawer>
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: "none", md: "block" },
          width: SIDEBAR_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: SIDEBAR_WIDTH,
            boxSizing: "border-box",
            borderRight: 1,
            borderColor: "divider",
          },
        }}
        open
      >
        {content}
      </Drawer>
    </>
  );
}
