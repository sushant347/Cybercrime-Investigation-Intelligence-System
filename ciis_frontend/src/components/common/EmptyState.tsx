import InboxIcon from "@mui/icons-material/Inbox";
import { Box, Button, Typography } from "@mui/material";
import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Box
      sx={{
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        py: 8,
        px: 3,
        gap: 1,
      }}
    >
      <Box sx={{ color: "text.secondary", "& svg": { fontSize: 56 } }}>
        {icon ?? <InboxIcon />}
      </Box>
      <Typography variant="h6">{title}</Typography>
      {description && (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 520 }}>
          {description}
        </Typography>
      )}
      {action && <Box sx={{ mt: 1 }}>{action}</Box>}
    </Box>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <EmptyState
      title="Unable to load data"
      description={message}
      action={
        onRetry && (
          <Button variant="outlined" onClick={onRetry}>
            Try again
          </Button>
        )
      }
    />
  );
}
