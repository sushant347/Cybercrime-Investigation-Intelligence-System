import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/Download";
import VerifiedIcon from "@mui/icons-material/Verified";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Divider,
  IconButton,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { evidenceApi } from "@/api";
import { ErrorState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { KeyValueTable } from "@/components/common/KeyValueTable";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import { StatusChip } from "@/components/common/StatusChip";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatBytes, formatDateTime } from "@/lib/format";

import { EvidencePreview } from "./EvidencePreview";
import { OcrResultsView } from "./OcrResultsView";

type TabKey = "preview" | "ocr" | "custody" | "forensics";

export default function EvidenceDetailPage() {
  const { caseId = "", evidenceId = "" } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("preview");
  const [downloading, setDownloading] = useState(false);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["evidence-detail", caseId, evidenceId],
    queryFn: () => evidenceApi.detail(caseId, evidenceId),
  });

  useEffect(() => setTab("preview"), [evidenceId]);

  if (isPending) return <DetailSkeleton />;
  if (isError) return <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />;

  const { record, ocr, forensics } = data;
  const hashVerified = String(record.hash_verified) === "True";
  const forgeryKeys = Object.keys(forensics);

  const download = async () => {
    setDownloading(true);
    try {
      const blob = await evidenceApi.downloadBlob(caseId, evidenceId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = record.original_file_name;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Box>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        alignItems={{ md: "center" }}
        sx={{ mb: 2 }}
      >
        <Stack direction="row" spacing={1} alignItems="center" sx={{ flex: 1, minWidth: 0 }}>
          <IconButton
            onClick={() => navigate(`/cases/${caseId}/evidence`)}
            aria-label="Back to evidence list"
          >
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h5" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                {evidenceId}
              </Typography>
              <StatusChip value={record.status} />
              {hashVerified ? (
                <Tooltip title="SHA-256 verified before and after acquisition — integrity intact">
                  <VerifiedIcon color="success" />
                </Tooltip>
              ) : (
                <Tooltip title="Hash verification not confirmed">
                  <WarningAmberIcon color="warning" />
                </Tooltip>
              )}
            </Stack>
            <Typography variant="body2" color="text.secondary" noWrap>
              {record.original_file_name} · {formatBytes(record.file_size_bytes)} · uploaded{" "}
              {formatDateTime(record.upload_time)}
            </Typography>
          </Box>
        </Stack>
        <Button
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={() => void download()}
          disabled={downloading}
        >
          Download Original
        </Button>
      </Stack>

      <Tabs
        value={tab}
        onChange={(_, v: TabKey) => setTab(v)}
        variant="scrollable"
        allowScrollButtonsMobile
        sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}
      >
        <Tab value="preview" label="Preview" />
        <Tab value="ocr" label={`OCR Results${ocr ? ` (${ocr.pages.length} pg)` : ""}`} />
        <Tab value="custody" label="Chain of Custody" />
        <Tab value="forensics" label={`Forensic Artifacts (${forgeryKeys.length})`} />
      </Tabs>

      {tab === "preview" && (
        <EvidencePreview caseId={caseId} evidenceId={evidenceId} record={record} />
      )}

      {tab === "ocr" && <OcrResultsView ocr={ocr} forensics={forensics} />}

      {tab === "custody" && (
        <Card>
          <CardHeader
            title="Chain of Custody & Integrity"
            subheader="Recorded by the Phase-1 acquisition pipeline — immutable"
          />
          <Divider />
          <KeyValueTable
            data={{
              evidence_id: record.evidence_id,
              case_id: record.case_id,
              original_file_name: record.original_file_name,
              stored_file_name: record.stored_file_name,
              file_extension: record.file_extension,
              file_size: formatBytes(record.file_size_bytes),
              sha256_before_acquisition: record.sha256_before,
              sha256_after_acquisition: record.sha256_after,
              hash_verified: hashVerified ? "Verified ✓" : "Not verified",
              upload_time: formatDateTime(record.upload_time),
              processing_time: formatDateTime(record.processing_time),
              status: record.status,
              investigator_notes: record.investigator_notes || "—",
            }}
          />
        </Card>
      )}

      {tab === "forensics" && (
        <Stack spacing={2}>
          {forgeryKeys.length === 0 ? (
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  No stored forensic artifact files were found for this evidence item
                  (forgery detection, logo detection, metadata extraction outputs). If the
                  forensics pipeline has been run, artifacts appear here automatically.
                </Typography>
              </CardContent>
            </Card>
          ) : (
            forgeryKeys.map((key) => (
              <Card key={key}>
                <CardHeader title={key} subheader="Raw engine artifact (verbatim)" />
                <Divider />
                <CardContent>
                  <JsonViewer data={forensics[key]} />
                </CardContent>
              </Card>
            ))
          )}
        </Stack>
      )}
    </Box>
  );
}
