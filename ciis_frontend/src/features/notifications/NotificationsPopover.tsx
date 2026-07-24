import DoneAllIcon from "@mui/icons-material/DoneAll";
import {
  Button,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Popover,
  Stack,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { notificationsApi } from "@/api";
import { timeAgo } from "@/lib/format";

import { notificationIcon } from "./notificationIcon";

export function NotificationsPopover({
  anchorEl,
  onClose,
}: {
  anchorEl: HTMLElement | null;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ["notifications", "popover"],
    queryFn: () => notificationsApi.list({ page_size: 8 }),
    enabled: !!anchorEl,
  });

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markRead(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <Popover
      open={!!anchorEl}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      transformOrigin={{ vertical: "top", horizontal: "right" }}
      slotProps={{ paper: { sx: { width: 380, maxWidth: "90vw" } } }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1.5 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Notifications
        </Typography>
        <Button
          size="small"
          startIcon={<DoneAllIcon />}
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending}
        >
          Mark all read
        </Button>
      </Stack>
      <Divider />
      <List dense sx={{ maxHeight: 420, overflow: "auto" }}>
        {(data?.results ?? []).length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            No notifications.
          </Typography>
        )}
        {(data?.results ?? []).map((n) => (
          <ListItemButton
            key={n.id}
            onClick={() => {
              void notificationsApi.markRead([n.id]).then(() => {
                void queryClient.invalidateQueries({ queryKey: ["notifications"] });
              });
              onClose();
              if (n.case_id) navigate(`/cases/${n.case_id}`);
            }}
            sx={{ opacity: n.read ? 0.6 : 1 }}
          >
            <Stack direction="row" spacing={1.5} alignItems="flex-start" sx={{ width: "100%" }}>
              {notificationIcon(n.type)}
              <ListItemText
                primary={n.title}
                secondary={`${n.message} · ${timeAgo(n.created_at)}`}
                slotProps={{
                  primary: { fontWeight: n.read ? 400 : 700, fontSize: "0.85rem" },
                  secondary: { fontSize: "0.75rem" },
                }}
              />
            </Stack>
          </ListItemButton>
        ))}
      </List>
      <Divider />
      <Button
        fullWidth
        onClick={() => {
          onClose();
          navigate("/notifications");
        }}
      >
        View all notifications
      </Button>
    </Popover>
  );
}
