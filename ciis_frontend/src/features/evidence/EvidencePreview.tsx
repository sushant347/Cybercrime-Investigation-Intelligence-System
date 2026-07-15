import DescriptionIcon from "@mui/icons-material/Description";
import { Box, Card, CardContent } from "@mui/material";
import { useEffect, useState } from "react";

import { evidenceApi } from "@/api";
import { EmptyState } from "@/components/common/EmptyState";
import { DetailSkeleton } from "@/components/common/LoadingSkeleton";
import type { EvidenceRow } from "@/types";

const IMAGE_EXT = [".png", ".jpg", ".jpeg"];
const TEXT_EXT = [".txt", ".csv"];

/** Authenticated inline preview for images, PDFs, and text documents. */
export function EvidencePreview({
  caseId,
  evidenceId,
  record,
}: {
  caseId: string;
  evidenceId: string;
  record: EvidenceRow;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const ext = record.file_extension.toLowerCase();
  const isImage = IMAGE_EXT.includes(ext);
  const isPdf = ext === ".pdf";
  const isText = TEXT_EXT.includes(ext);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    setObjectUrl(null);
    setText(null);

    evidenceApi
      .downloadBlob(caseId, evidenceId, true)
      .then(async (blob) => {
        if (cancelled) return;
        if (isText) {
          setText(await blob.text());
        } else {
          url = URL.createObjectURL(blob);
          setObjectUrl(url);
        }
      })
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [caseId, evidenceId, isText]);

  if (loading) return <DetailSkeleton />;
  if (failed) {
    return (
      <EmptyState
        icon={<DescriptionIcon />}
        title="Preview unavailable"
        description="The original file could not be loaded. Use Download Original instead."
      />
    );
  }

  if (isImage && objectUrl) {
    return (
      <Card>
        <CardContent sx={{ display: "grid", placeItems: "center", bgcolor: "background.default" }}>
          <Box
            component="img"
            src={objectUrl}
            alt={record.original_file_name}
            sx={{ maxWidth: "100%", maxHeight: "70vh", borderRadius: 1 }}
          />
        </CardContent>
      </Card>
    );
  }

  if (isPdf && objectUrl) {
    return (
      <Card>
        <Box
          component="iframe"
          src={objectUrl}
          title={record.original_file_name}
          sx={{ width: "100%", height: "75vh", border: 0 }}
        />
      </Card>
    );
  }

  if (text !== null) {
    return (
      <Card>
        <CardContent>
          <Box
            component="pre"
            sx={{
              m: 0,
              maxHeight: "70vh",
              overflow: "auto",
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: "0.82rem",
              whiteSpace: "pre-wrap",
            }}
          >
            {text}
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <EmptyState
      icon={<DescriptionIcon />}
      title={`No inline preview for ${ext || "this file type"}`}
      description="DOCX and other binary documents can be downloaded and opened locally. OCR-extracted text is available in the OCR Results tab."
    />
  );
}
