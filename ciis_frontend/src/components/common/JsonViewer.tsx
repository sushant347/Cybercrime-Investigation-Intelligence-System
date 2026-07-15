import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { Box, IconButton, Paper, Tooltip } from "@mui/material";

/** Read-only, monospace rendering of any raw engine artifact. */
export function JsonViewer({ data, maxHeight = 420 }: { data: unknown; maxHeight?: number }) {
  const text = JSON.stringify(data, null, 2) ?? "null";
  return (
    <Paper variant="outlined" sx={{ position: "relative" }}>
      <Tooltip title="Copy JSON">
        <IconButton
          size="small"
          onClick={() => void navigator.clipboard.writeText(text)}
          sx={{ position: "absolute", top: 6, right: 6, zIndex: 1 }}
        >
          <ContentCopyIcon fontSize="inherit" />
        </IconButton>
      </Tooltip>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 2,
          maxHeight,
          overflow: "auto",
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: "0.78rem",
          lineHeight: 1.55,
        }}
      >
        {text}
      </Box>
    </Paper>
  );
}
