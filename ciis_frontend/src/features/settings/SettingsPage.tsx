import SettingsIcon from "@mui/icons-material/Settings";
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  FormControlLabel,
  Stack,
  Switch,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { settingsApi } from "@/api";
import { EmptyState, ErrorState } from "@/components/common/EmptyState";
import { KeyValueTable } from "@/components/common/KeyValueTable";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { apiErrorMessage } from "@/lib/apiClient";
import { useColorMode } from "@/theme/ColorModeProvider";

type TabKey = "appearance" | "ocr" | "preprocessing" | "storage" | "investigation";

/**
 * Module 11 - System settings.
 * Engine configuration is displayed READ-ONLY (the forensic engine owns its
 * tunables via environment variables); user preferences are editable.
 */
export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>("appearance");
  const { mode, setMode } = useColorMode();

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.get,
  });

  if (isPending) return <DetailSkeleton />;
  if (isError) return <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />;
  if (!data) return <EmptyState icon={<SettingsIcon />} title="No configuration available" />;

  return (
    <Box>
      <PageHeader
        title="System Settings"
        subtitle="Appearance and forensic engine configuration (engine values are read-only by design)"
      />

      <Tabs
        value={tab}
        onChange={(_, v: TabKey) => setTab(v)}
        variant="scrollable"
        allowScrollButtonsMobile
        sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}
      >
        <Tab value="appearance" label="Appearance" />
        <Tab value="ocr" label="OCR Configuration" />
        <Tab value="preprocessing" label="Image Preprocessing" />
        <Tab value="storage" label="Evidence Storage" />
        <Tab value="investigation" label="Investigation Engine" />
      </Tabs>

      {tab === "appearance" && (
        <Card sx={{ maxWidth: 560 }}>
          <CardHeader
            title="Appearance"
            subheader="Stored in this browser — the engine has no user accounts"
          />
          <Divider />
          <CardContent>
            <FormControlLabel
              control={
                <Switch
                  checked={mode === "dark"}
                  onChange={(e) => setMode(e.target.checked ? "dark" : "light")}
                />
              }
              label={`Theme: ${mode === "dark" ? "Dark" : "Light"}`}
            />
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
