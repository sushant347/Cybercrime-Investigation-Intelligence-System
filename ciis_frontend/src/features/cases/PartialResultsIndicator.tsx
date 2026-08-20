import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { Box, Stack, Tooltip, Typography } from "@mui/material";

/**
 * "The last analysis completed with warnings", as a hover target.
 *
 * This used to be a full-width warning banner above the tabs. Partial results
 * are the *normal* outcome for a case whose evidence files have been cleared
 * from disk, so the banner was permanent — it shouted on every tab of every
 * visit, pushed the tabs down the page, and trained the investigator to
 * ignore exactly the colour the interface reserves for real problems. The
 * information is unchanged and still one hover away; it simply no longer
 * claims the top of the screen for a condition the user already knows about.
 */

type Note = { label: string; body: string };

/**
 * Turn the job's `detail` string into readable lines.
 *
 * The engine writes it as `key=value` segments joined with "; ", except the
 * `warnings=` value is itself a "; "-joined list, so a plain split yields a
 * mix of pairs and continuation fragments. Both are handled: a fragment that
 * looks like `key=value` becomes a labelled note, anything else continues the
 * previous one. Segments reporting nothing ("none", "0") are dropped.
 */
export function parseAnalysisDetail(detail: string): Note[] {
  const notes: Note[] = [];
  const empty = /^(none|0|0 item\(s\))$/i;

  for (const rawSegment of (detail || "").split(";")) {
    const segment = rawSegment.trim();
    if (!segment) continue;

    const pair = /^([a-z0-9_]+)=(.*)$/i.exec(segment);
    if (pair) {
      const [, key, value] = pair;
      const body = value.trim();
      if (empty.test(body)) continue;
      notes.push({ label: humanLabel(key), body: body || "reported a problem" });
    } else if (notes.length > 0) {
      // A continuation of the previous value, e.g. the second entry of a
      // "; "-joined warnings list.
      notes[notes.length - 1].body += `; ${segment}`;
    } else {
      notes.push({ label: "Warning", body: segment });
    }
  }
  return notes;
}

/** `rag_index` -> "Rag index"; `phase2_failures` -> "Phase2 failures". */
function humanLabel(key: string): string {
  const known: Record<string, string> = {
    warnings: "Warnings",
    phase2_failures: "Module failures",
    rag_index: "Case assistant index",
  };
  return (
    known[key] ?? key.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
  );
}

export function PartialResultsIndicator({ detail }: { detail: string }) {
  const notes = parseAnalysisDetail(detail);

  return (
    <Tooltip
      // Keyboard users get the same content: the icon is focusable, and MUI
      // opens the tooltip on focus as well as hover.
      title={
        <Stack spacing={1} sx={{ py: 0.5 }}>
          <Typography variant="subtitle2">
            Latest analysis produced partial results
          </Typography>
          <Typography variant="caption" color="inherit">
            Timeline, graph, analytics and report artifacts were still
            regenerated. Review them with these notes in mind:
          </Typography>
          {notes.length === 0 ? (
            <Typography variant="caption" color="inherit">
              {detail || "No detail was recorded."}
            </Typography>
          ) : (
            <Stack spacing={0.75}>
              {notes.map((note) => (
                <Box key={note.label}>
                  <Typography variant="caption" sx={{ fontWeight: 700, display: "block" }}>
                    {note.label}
                  </Typography>
                  <Typography variant="caption" sx={{ wordBreak: "break-word" }}>
                    {note.body}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </Stack>
      }
      slotProps={{ tooltip: { sx: { maxWidth: 420 } } }}
    >
      <Box
        component="span"
        tabIndex={0}
        aria-label="Latest analysis produced partial results"
        sx={{
          display: "inline-flex",
          alignItems: "center",
          color: "warning.main",
          cursor: "help",
          borderRadius: "50%",
          p: 0.25,
          "&:focus-visible": { outline: 2, outlineColor: "warning.main" },
          "& svg": { fontSize: 20, display: "block" },
        }}
      >
        <WarningAmberIcon />
      </Box>
    </Tooltip>
  );
}
