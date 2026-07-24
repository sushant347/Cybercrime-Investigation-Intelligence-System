import SettingsIcon from "@mui/icons-material/Settings";
import {
  Alert,
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  FormControlLabel,
  MenuItem,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { authApi, settingsApi } from "@/api";
import { EmptyState, ErrorState } from "@/components/common/EmptyState";
import { KeyValueTable } from "@/components/common/KeyValueTable";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/lib/apiClient";
import { useColorMode } from "@/theme/ColorModeProvider";

type TabKey = "preferences" | "ocr" | "preprocessing" | "storage" | "investigation";

/**
 * Module 11 - System settings.
 * Engine configuration is displayed READ-ONLY (the forensic engine owns its
 * tunables via environment variables); user preferences are editable.
 */
export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>("preferences");
  const { user, refreshUser } = useAuth();
  const { mode, setMode } = useColorMode();
  const [saved, setSaved] = useState(false);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
  });

  const prefMutation = useMutation({
    mutationFn: authApi.updatePreferences,
    onSuccess: async () => {
      setSaved(true);
      await refreshUser();
      window.setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isPending) return <DetailSkeleton />;
  if (isError) return <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />;
  if (!data) return <EmptyState icon={<SettingsIcon />} title="No configuration available" />;

  const pref = user?.preference;

  return (
    <Box>
      <PageHeader
        title="System Settings"
        subtitle="User preferences and forensic engine configuration (engine values are read-only by design)"
      />

      <Tabs
        value={tab}
        onChange={(_, v: TabKey) => setTab(v)}
        variant="scrollable"
        allowScrollButtonsMobile
        sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}
      >
        <Tab value="preferences" label="My Preferences" />
        <Tab value="ocr" label="OCR Configuration" />
        <Tab value="preprocessing" label="Image Preprocessing" />
        <Tab value="storage" label="Evidence Storage" />
        <Tab value="investigation" label="Investigation Engine" />
      </Tabs>

      {tab === "preferences" && (
        <Card sx={{ maxWidth: 560 }}>
          <CardHeader title="User Preferences" subheader="Stored on your account" />
          <Divider />
          <CardContent>
            <Stack spacing={2.5}>
              {saved && <Alert severity="success">Preferences saved.</Alert>}
              <FormControlLabel
                control={
                  <Switch
                    checked={mode === "dark"}
                    onChange={(e) => {
                      const next = e.target.checked ? "dark" : "light";
                      setMode(next);
                      prefMutation.mutate({ theme: next });
                    }}
                  />
                }
                label={`Theme: ${mode === "dark" ? "Dark" : "Light"}`}
              />
              <TextField
                select
                label="Language"
                value={pref?.language ?? "en"}
                onChange={(e) => prefMutation.mutate({ language: e.target.value })}
                sx={{ maxWidth: 240 }}
              >
                <MenuItem value="en">English</MenuItem>
                <MenuItem value="ne">नेपाली (Nepali)</MenuItem>
              </TextField>
              <FormControlLabel
                control={
                  <Switch
                    checked={pref?.notifications_enabled ?? true}
                    onChange={(e) =>
                      prefMutation.mutate({ notifications_enabled: e.target.checked })
                    }
                  />
                }
                label="Enable notifications"
              />
              <TextField
                select
                label="Rows per page (default)"
                value={pref?.items_per_page ?? 25}
                onChange={(e) => prefMutation.mutate({ items_per_page: Number(e.target.value) })}
                sx={{ maxWidth: 240 }}
              >
                {[10, 25, 50, 100].map((n) => (
                  <MenuItem key={n} value={n}>
                    {n}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          </CardContent>
        </Card>
      )}

      {tab === "ocr" && (
        <Card>
          <CardHeader
            title="OCR Configuration"
            subheader="Phase-1 engine settings (override via EVIDENCE_* environment variables)"
          />
          <Divider />
          <KeyValueTable data={data.ocr} />
          <Divider />
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              Supported evidence formats:
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
              {data.supported_extensions.map((ext) => (
                <Chip key={ext} size="small" label={ext} variant="outlined" />
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

      {tab === "preprocessing" && (
        <Card>
          <CardHeader
            title="Intelligent Image Preprocessing"
            subheader="Quality thresholds used before OCR (read-only)"
          />
          <Divider />
          <KeyValueTable data={data.preprocessing} />
        </Card>
      )}

      {tab === "storage" && (
        <Card>
          <CardHeader
            title="Evidence Storage"
            subheader="Engine storage layout and limits (read-only)"
          />
          <Divider />
          <KeyValueTable data={data.storage} />
        </Card>
      )}

      {tab === "investigation" && (
        <Card>
          <CardHeader
            title="Investigation Engine Configuration"
            subheader="Phase-2 weights, thresholds, bands, and report settings — including threat intelligence and correlation factors (override via INVESTIGATION_* environment variables)"
          />
          <Divider />
          <KeyValueTable data={data.investigation} />
        </Card>
      )}
    </Box>
  );
}
