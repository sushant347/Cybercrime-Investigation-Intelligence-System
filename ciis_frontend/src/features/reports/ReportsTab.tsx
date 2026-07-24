import ArticleIcon from "@mui/icons-material/Article";
import DownloadIcon from "@mui/icons-material/Download";
import VisibilityIcon from "@mui/icons-material/Visibility";
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { reportsApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { formatBytes, formatDateTime } from "@/lib/format";

/** Module 9 - Report center: versioned Phase-2 investigation reports. */
export function ReportsTab({ caseId }: { caseId: string }) {
  const [preview, setPreview] = useState<{ fileName: string; content: string } | null>(null);
  const [jsonPreview, setJsonPreview] = useState(false);

  const listQuery = useQuery({
    queryKey: ["reports", caseId],
    queryFn: () => reportsApi.list(caseId),
  });
  const latestQuery = useQuery({
    queryKey: ["report-latest", caseId],
    queryFn: () => reportsApi.latest(caseId),
    retry: false,
  });

  if (listQuery.isPending) return <TableSkeleton />;

  const reports = listQuery.data?.reports ?? [];
  if (reports.length === 0) {
    return (
      <EmptyState
        icon={<ArticleIcon />}
        title="No reports generated"
        description="Run the investigation analysis — the Phase-2 report generator produces a versioned JSON + Markdown report for this case."
      />
    );
  }

  const download = async (fileName: string) => {
    const blob = await reportsApi.downloadBlob(caseId, fileName);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  };

  const openPreview = async (fileName: string) => {
    const content = await reportsApi.previewMarkdown(caseId, fileName);
    setPreview({ fileName, content });
  };

  return (
    <Stack spacing={2}>
      <Card>
        <CardHeader
          title="Report History"
          subheader="Every stored version — reports are never overwritten"
          action={
            latestQuery.data && (
              <Button size="small" startIcon={<VisibilityIcon />} onClick={() => setJsonPreview(true)}>
                Preview latest (JSON)
              </Button>
            )
          }
        />
        <Divider />
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>File</TableCell>
              <TableCell>Format</TableCell>
              <TableCell>Generated</TableCell>
              <TableCell>Size</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {reports.map((report) => (
              <TableRow key={report.file_name} hover>
                <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                  {report.file_name}
                </TableCell>
                <TableCell>
                  <Chip size="small" label={report.format} variant="outlined" />
                </TableCell>
                <TableCell>
                  {report.generated_at
                    ? formatDateTime(report.generated_at)
                    : formatDateTime(new Date(report.modified_at * 1000).toISOString())}
                </TableCell>
                <TableCell>{formatBytes(report.size_bytes)}</TableCell>
                <TableCell align="right">
                  <Stack direction="row" spacing={1} justifyContent="flex-end">
                    {report.format === "markdown" && (
                      <Button
                        size="small"
                        startIcon={<VisibilityIcon />}
                        onClick={() => void openPreview(report.file_name)}
                      >
                        Preview
                      </Button>
                    )}
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={() => void download(report.file_name)}
                    >
                      Download
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {latestQuery.data && (
        <Card>
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              Latest report generated {formatDateTime(latestQuery.data.generated_at)} · version{" "}
              {latestQuery.data.report_version} · schema {latestQuery.data.schema_version}
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Markdown preview */}
      <Dialog open={!!preview} onClose={() => setPreview(null)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
          {preview?.fileName}
        </DialogTitle>
        <DialogContent dividers>
          <Box
            component="pre"
            sx={{
              m: 0,
              whiteSpace: "pre-wrap",
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: "0.82rem",
              lineHeight: 1.7,
            }}
          >
            {preview?.content}
          </Box>
        </DialogContent>
        <DialogActions>
          {preview && (
            <Button startIcon={<DownloadIcon />} onClick={() => void download(preview.fileName)}>
              Download
            </Button>
          )}
          <Button onClick={() => setPreview(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Latest JSON preview */}
      <Dialog open={jsonPreview} onClose={() => setJsonPreview(false)} maxWidth="md" fullWidth>
        <DialogTitle>Latest Investigation Report (JSON)</DialogTitle>
        <DialogContent dividers>
          {latestQuery.data && <JsonViewer data={latestQuery.data} maxHeight={560} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setJsonPreview(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
