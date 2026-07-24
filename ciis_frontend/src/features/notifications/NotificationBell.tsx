import DoneAllIcon from "@mui/icons-material/DoneAll";
import NotificationsIcon from "@mui/icons-material/Notifications";
import {
  Badge,
  Box,
  Button,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { notificationsApi } from "@/api";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime } from "@/lib/format";
import type { AppNotification } from "@/types";

import { notificationIcon } from "./notificationIcon";

const POLL_MS = 30_000;

/** Header bell: unread badge + recent-notifications menu, polled from the API. */
export function NotificationBell() {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isError, error } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationsApi.list({ page_size: 10 }),
    refetchInterval: POLL_MS,
  });

  const markRead = useMutation({
    mutationFn: (ids?: number[]) => notificationsApi.markRead(ids),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const items: AppNotification[] = data?.results ?? [];
  const unread = data?.unread_count ?? 0;

  const openMenu = (e: React.MouseEvent<HTMLElement>) => setAnchor(e.currentTarget);
  const closeMenu = () => setAnchor(null);

  const handleClick = (n: AppNotification) => {
    if (!n.read) markRead.mutate([n.id]);
    closeMenu();
    if (n.case_id) {
      navigate(`/cases/${n.case_id}${n.evidence_id ? `/evidence/${n.evidence_id}` : ""}`);
    }
  };

  return (
    <>
      <Tooltip title="Notifications">
        <IconButton onClick={openMenu} aria-label={`Notifications (${unread} unread)`}>
          <Badge badgeContent={unread} color="error" max={99}>
            <NotificationsIcon />
          </Badge>
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={closeMenu}
        slotProps={{ paper: { sx: { width: 380, maxWidth: "100vw" } } }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2">Notifications</Typography>
          <Button
            size="small"
            startIcon={<DoneAllIcon />}
            disabled={unread === 0 || markRead.isPending}
            onClick={() => markRead.mutate(undefined)}
          >
            Mark all read
          </Button>
        </Stack>
        <Divider />

        {isError && (
          <MenuItem disabled>
            <ListItemText primary="Could not load notifications" secondary={apiErrorMessage(error)} />
          </MenuItem>
        )}
        {!isError && items.length === 0 && (
          <MenuItem disabled>
            <ListItemText primary="No notifications yet" />
          </MenuItem>
        )}
        {items.map((n) => (
          <MenuItem
            key={n.id}
            onClick={() => handleClick(n)}
            sx={{ alignItems: "flex-start", py: 1, bgcolor: n.read ? "transparent" : "action.hover" }}
          >
            <ListItemIcon sx={{ mt: 0.5 }}>{notificationIcon(n.type)}</ListItemIcon>
            <ListItemText
              primary={
                <Typography variant="body2" sx={{ fontWeight: n.read ? 400 : 600 }} noWrap>
                  {n.title}
                </Typography>
              }
              secondary={
                <Box component="span" sx={{ display: "block" }}>
                  <Typography variant="caption" color="text.secondary" component="span" sx={{ display: "block" }}>
                    {n.message}
                  </Typography>
                  <Typography variant="caption" color="text.disabled" component="span">
                    {formatDateTime(n.created_at)}
                  </Typography>
                </Box>
              }
            />
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
