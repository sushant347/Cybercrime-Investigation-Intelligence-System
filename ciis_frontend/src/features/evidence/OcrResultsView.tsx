import TextSnippetIcon from "@mui/icons-material/TextSnippet";
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { EmptyState } from "@/components/common/EmptyState";
import type { EvidenceOcr } from "@/types";

import { CaptureQuality } from "./CaptureQuality";

/**
 * Phase-1 OCR output: page text, per-line confidence — displayed verbatim.
 *
 * The capture-quality report is shown above the text because it is what the
 * engine knew *before* reading: the grade predicts the accuracy, and putting
 * the prediction next to the result is what lets an investigator judge either.
 */
export function OcrResultsView({
  ocr,
  forensics,
}: {
  ocr: EvidenceOcr | null;
  /** Phase-1 artifacts keyed by report name; may be absent entirely. */
  forensics?: Record<string, unknown>;
}) {
  const [pageIndex, setPageIndex] = useState(0);

  if (!ocr || ocr.pages.length === 0) {
    return (
      <EmptyState
        icon={<TextSnippetIcon />}
        title="No OCR results"
        description="This evidence item has no stored OCR output. It may still be processing, or processing may have failed."
      />
    );
  }

  const page = ocr.pages[Math.min(pageIndex, ocr.pages.length - 1)];

  // The artifact is stored under a "report" envelope; older items may be flat.
  const stored = (forensics ?? {})["quality_report"] as
    | { report?: Record<string, unknown> }
    | Record<string, unknown>
    | undefined;
  const quality = (stored as { report?: Record<string, unknown> } | undefined)
    ?.report ?? (stored as Record<string, unknown> | undefined);

  return (
    <Stack spacing={2}>
      {quality && (
        <CaptureQuality
          report={quality}
          achievedConfidence={
            typeof page.confidence === "number" ? page.confidence : null
          }
          lineCount={page.lines.length}
        />
      )}
      {ocr.pages.length > 1 && (
        <Tabs
          value={pageIndex}
          onChange={(_, v: number) => setPageIndex(v)}
          variant="scrollable"
        >
          {ocr.pages.map((p, i) => (
            <Tab key={p.page} value={i} label={`Page ${p.page}`} />
          ))}
        </Tabs>
      )}

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="flex-start">
        <Card sx={{ flex: 1, width: "100%" }}>
          <CardHeader
            title="Extracted Text"
            subheader={
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  Page confidence:
                </Typography>
                <ConfidenceBar value={page.confidence} scale="fraction" label="OCR confidence" />
              </Stack>
            }
          />
          <Divider />
          <CardContent>
            <Box
              component="pre"
              sx={{
                m: 0,
                whiteSpace: "pre-wrap",
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: "0.85rem",
                lineHeight: 1.7,
                maxHeight: "60vh",
                overflow: "auto",
              }}
            >
              {page.text || "(empty page)"}
            </Box>
          </CardContent>
        </Card>

        <Card sx={{ flex: 1, width: "100%" }}>
          <CardHeader
            title="Line-Level Confidence"
            subheader="Each recognized line with its OCR engine confidence"
          />
          <Divider />
          <Box sx={{ maxHeight: "60vh", overflow: "auto" }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell>
                  <TableCell>Text</TableCell>
                  <TableCell sx={{ width: 170 }}>Confidence</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {page.lines.map((line, i) => (
                  <TableRow key={i} hover>
                    <TableCell sx={{ color: "text.secondary" }}>{i + 1}</TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: "0.78rem" }}>
                      {line.text}
                    </TableCell>
                    <TableCell>
                      <ConfidenceBar value={line.confidence} scale="fraction" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        </Card>
      </Stack>
    </Stack>
  );
}
