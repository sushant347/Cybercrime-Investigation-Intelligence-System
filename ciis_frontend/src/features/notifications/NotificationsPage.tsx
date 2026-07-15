import DoneAllIcon from "@mui/icons-material/DoneAll";
import NotificationsOffIcon from "@mui/icons-material/NotificationsOff";
import {
  Box,
  Button,
  Card,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Stack,
  TablePagination,
  TextField,
} from "@mui/material";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { notificationsApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { formatDateTime } from "@/lib/format";

import { notificationIcon } from "./notificationIcon";

const TYPES = [
  "processing_complete",
  "high_priority",
  "forgery_warning",
  "threat_detected",
  "report_generated",
  "system_error",
] as const;

/** Module 12 - Notification center. */
export default function NotificationsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [type, setType] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const { data, isPending } = useQuery({
    queryKey: ["notifications", "page", { type, unreadOnly, page, pageSize }],
    queryFn: () =>
      notificationsApi.list({
        type: type || undefined,
        unread: unreadOnly ? 1 : undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  });

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markRead(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <Box>
      <PageHeader
        title="Notifications"
        subtitle={`Unread: ${data?.unread_count ?? 0}`}
        actions={
          <Button
            variant="outlined"
            startIcon={<DoneAllIcon />}
            onClick={() => markAll.mutate()}
            disabled={markAll.isPending}
          >
            Mark all read
          </Button>
        }
      />
      <Card>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ p: 2 }}>
          <TextField
            select
            size="small"
            label="Type"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="">All types</MenuItem>
            {TYPES.map((t) => (
              <MenuItem key={t} value={t} sx={{ textTransform: "capitalize" }}>
                {t.replace(/_/g, " ")}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Show"
            value={unreadOnly ? "unread" : "all"}
            onChange={(e) => {
              setUnreadOnly(e.target.value === "unread");
              setPage(0);
            }}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="unread">Unread only</MenuItem>
          </TextField>
        </Stack>

        {isPending ? (
          <TableSkeleton />
        ) : (data?.results ?? []).length === 0 ? (
          <EmptyState
            icon={<NotificationsOffIcon />}
            title="No notifications"
            description="Processing completions, high-priority alerts, forgery warnings, and system errors will appear here."
          />
        ) : (
          <>
            <List>
              {data!.results.map((n) => (
                <ListItemButton
                  key={n.id}
                  onClick={() => {
                    void notificationsApi.markRead([n.id]).then(() => {
                      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
                    });
                    if (n.case_id) navigate(`/cases/${n.case_id}`);
                  }}
                  sx={{ opacity: n.read ? 0.65 : 1 }}
                >
                  <Stack direction="row" spacing={2} alignItems="flex-start" sx={{ width: "100%" }}>
                    {notificationIcon(n.type)}
                    <ListItemText
                      primary={n.title}
                      secondary={`${n.message}${n.case_id ? ` · ${n.case_id}` : ""} · ${formatDateTime(n.created_at)}`}
                      slotProps={{ primary: { fontWeight: n.read ? 400 : 700 } }}
                    />
                  </Stack>
                </ListItemButton>
              ))}
            </List>
            <TablePagination
              component="div"
              count={data!.count}
              page={page}
              rowsPerPage={pageSize}
              onPageChange={(_, p) => setPage(p)}
              onRowsPerPageChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(0);
              }}
              rowsPerPageOptions={[10, 25, 50]}
            />
          </>
        )}
      </Card>
    </Box>
  );
}
