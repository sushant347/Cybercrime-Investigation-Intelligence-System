import AddIcon from "@mui/icons-material/Add";
import CampaignIcon from "@mui/icons-material/Campaign";
import FolderIcon from "@mui/icons-material/Folder";
import ImageSearchIcon from "@mui/icons-material/ImageSearch";
import PriorityHighIcon from "@mui/icons-material/PriorityHigh";
import TaskAltIcon from "@mui/icons-material/TaskAlt";
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
} from "recharts";

import { dashboardApi } from "@/api";
import { ErrorState } from "@/components/common/EmptyState";
import { CardGridSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { StatusChip } from "@/components/common/StatusChip";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/lib/apiClient";
import { timeAgo, titleCase } from "@/lib/format";
import { BRAND } from "@/theme/theme";

const PIE_COLORS = [BRAND.critical, BRAND.high, BRAND.medium, BRAND.low, BRAND.primary, BRAND.accent];

function toPieData(record: Record<string, number>) {
  return Object.entries(record).map(([name, value]) => ({ name: titleCase(name), value }));
}

export default function DashboardPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardApi.get,
    refetchInterval: 30_000,
  });

  if (isPending) return <CardGridSkeleton cards={6} />;
  if (isError) return <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />;

  const threatData = toPieData(data.threat_distribution);
  const priorityData = toPieData(data.priority_distribution);

  return (
    <Box>
      <PageHeader
        title="Command Dashboard"
        subtitle="Live overview of every investigation handled by this unit"
        actions={
          <>
            {hasPermission("case.manage") && (
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => navigate("/cases", { state: { openCreate: true } })}
              >
                New Case
              </Button>
            )}
            <Button variant="outlined" component={RouterLink} to="/cases">
              Browse Cases
            </Button>
          </>
        }
      />

      <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 3 }}>
        <StatCard label="Total Cases" value={data.totals.cases} icon={<FolderIcon />} />
        <StatCard
          label="Active Cases"
          value={data.totals.active_cases}
          icon={<FolderIcon />}
          color={BRAND.primary}
        />
        <StatCard
          label="Completed"
          value={data.totals.completed_cases}
          icon={<TaskAltIcon />}
          color={BRAND.low}
        />
        <StatCard
          label="Evidence Items"
          value={data.totals.evidence}
          icon={<ImageSearchIcon />}
          color={BRAND.accent}
        />
        <StatCard
          label="High Priority"
          value={data.totals.high_priority_cases}
          icon={<PriorityHighIcon />}
          color={BRAND.critical}
        />
        <StatCard
          label="Campaigns Detected"
          value={data.totals.campaigns}
          icon={<CampaignIcon />}
          color={BRAND.high}
        />
      </Stack>

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} sx={{ mb: 3 }}>
        <Card sx={{ flex: 1, minWidth: 0 }}>
          <CardHeader title="Threat Distribution" subheader="Aggregated from engine analytics" />
          <CardContent sx={{ height: 280 }}>
            {threatData.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No threat analytics generated yet. Run an investigation analysis on a case.
              </Typography>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={threatData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90}>
                    {threatData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <ChartTooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
        <Card sx={{ flex: 1, minWidth: 0 }}>
          <CardHeader title="Priority Distribution" subheader="Engine case prioritization verdicts" />
          <CardContent sx={{ height: 280 }}>
            {priorityData.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No priority scores yet.
              </Typography>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={priorityData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90}>
                    {priorityData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <ChartTooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
        <Card sx={{ flex: 1, minWidth: 0 }}>
          <CardHeader title="High Priority Queue" subheader="Ranked by engine priority score" />
          <List dense>
            {data.high_priority_cases.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ px: 2, pb: 2 }}>
                No high-priority cases right now.
              </Typography>
            )}
            {data.high_priority_cases.map((c) => (
              <ListItemButton key={c.case_id} component={RouterLink} to={`/cases/${c.case_id}`}>
                <ListItemText
                  primary={c.case_id}
                  secondary={c.score != null ? `Score ${Number(c.score).toFixed(1)}` : undefined}
                />
                <StatusChip value={c.band} />
              </ListItemButton>
            ))}
          </List>
        </Card>
      </Stack>

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2}>
        <Card sx={{ flex: 1, minWidth: 0 }}>
          <CardHeader title="Processing Status" subheader="Evidence pipeline & analysis jobs" />
          <List dense>
            {data.processing.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ px: 2, pb: 2 }}>
                No background jobs yet.
              </Typography>
            )}
            {data.processing.map((job) => (
              <ListItemButton
                key={job.id}
                component={RouterLink}
                to={job.case_id ? `/cases/${job.case_id}` : "/cases"}
              >
                <ListItemText
                  primary={`${titleCase(job.job_type)} — ${job.case_id || "—"}`}
                  secondary={`${job.detail || job.error || ""} · ${timeAgo(job.created_at)}`}
                />
                <StatusChip value={job.status} />
              </ListItemButton>
            ))}
          </List>
        </Card>
        <Card sx={{ flex: 1, minWidth: 0 }}>
          <CardHeader
            title="Recent Activity"
            subheader="Platform user actions (full trail in Audit Log)"
            action={
              <Button size="small" component={RouterLink} to="/audit">
                View all
              </Button>
            }
          />
          <Divider />
          <List dense>
            {data.recent_activity.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ px: 2, py: 2 }}>
                No recent activity.
              </Typography>
            )}
            {data.recent_activity.map((entry) => (
              <ListItemButton
                key={entry.id}
                component={RouterLink}
                to={entry.case_id ? `/cases/${entry.case_id}` : "/audit"}
              >
                <ListItemText
                  primary={
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip size="small" label={entry.module} variant="outlined" />
                      <Typography variant="body2">
                        {entry.username || "system"} · {titleCase(entry.action)}
                        {entry.case_id ? ` · ${entry.case_id}` : ""}
                      </Typography>
                    </Stack>
                  }
                  secondary={`${entry.detail} · ${timeAgo(entry.created_at)}`}
                />
              </ListItemButton>
            ))}
          </List>
        </Card>
      </Stack>
    </Box>
  );
}
