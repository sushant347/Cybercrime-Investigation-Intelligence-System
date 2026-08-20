import AccountTreeIcon from "@mui/icons-material/AccountTree";
import GroupWorkIcon from "@mui/icons-material/GroupWork";
import InsightsIcon from "@mui/icons-material/Insights";
import PersonSearchIcon from "@mui/icons-material/PersonSearch";
import ScheduleIcon from "@mui/icons-material/Schedule";
import VerifiedUserIcon from "@mui/icons-material/VerifiedUser";
import { Box, Stack, Typography, useTheme } from "@mui/material";
import type { ReactElement } from "react";

import { brandTone, type BRAND } from "@/theme/theme";

/**
 * The report's key findings.
 *
 * These were a numbered stack of identical bordered rows: correct, complete
 * and completely flat, so the one finding naming a suspect read exactly like
 * the one restating the file count. The wording is engine output and is not
 * touched — every character still comes from the stored artifact. What is
 * added is structure the reader can skim: each finding is classified by what
 * it is *about*, given that subject's icon and colour, and the identifiers and
 * figures inside the sentence are lifted out of the prose so the eye lands on
 * them.
 */

type Subject = {
  key: string;
  label: string;
  icon: ReactElement;
  /** Resolved against the active theme — see `brandTone`. */
  tone: keyof typeof BRAND;
};

const SUBJECTS: Subject[] = [
  {
    key: "identity",
    label: "Identity lead",
    icon: <PersonSearchIcon />,
    tone: "critical",
  },
  {
    key: "campaign",
    label: "Campaign",
    icon: <GroupWorkIcon />,
    tone: "high",
  },
  {
    key: "links",
    label: "Case links",
    icon: <AccountTreeIcon />,
    tone: "accent",
  },
  {
    key: "chronology",
    label: "Chronology",
    icon: <ScheduleIcon />,
    tone: "medium",
  },
  {
    key: "integrity",
    label: "Integrity",
    icon: <VerifiedUserIcon />,
    tone: "low",
  },
  {
    key: "analysis",
    label: "Analysis",
    icon: <InsightsIcon />,
    tone: "primary",
  },
];

const SUBJECT_BY_KEY = Object.fromEntries(SUBJECTS.map((s) => [s.key, s]));

/**
 * Classify a finding by subject.
 *
 * Ordered most specific first: a sentence naming an identity lead also
 * mentions evidence items, so "identity" has to win over "integrity".
 */
export function findingSubject(line: string): Subject {
  const text = line.toLowerCase();
  if (/identity lead|highest-scoring|suspect/.test(text)) {
    return SUBJECT_BY_KEY.identity;
  }
  if (/campaign|clustering/.test(text)) return SUBJECT_BY_KEY.campaign;
  if (/linked to|cross-case|shared-entity|linked cases/.test(text)) {
    return SUBJECT_BY_KEY.links;
  }
  if (/chronolog|event times|timeline/.test(text)) {
    return SUBJECT_BY_KEY.chronology;
  }
  if (/integrity|sha-256|hash/.test(text)) return SUBJECT_BY_KEY.integrity;
  return SUBJECT_BY_KEY.analysis;
}

/**
 * Identifiers and figures worth landing on: quoted values, case/evidence/
 * campaign references, ratios like 11/11, scores like 79/100, percentages.
 * Split with a capturing group so the surrounding prose survives verbatim.
 */
const TOKEN = /('[^']+'|\bCASE_[A-Z0-9]+\b|\bEVID_\d+\b|\bCAMP_[A-Z0-9_]+\b|\b\d+\/\d+\b|\b\d+(?:\.\d+)?%|\bSHA-256\b)/g;

function Highlighted({ text, color }: { text: string; color: string }) {
  const parts = text.split(TOKEN);
  return (
    <>
      {parts.map((part, i) =>
        // Odd indices are the captured tokens.
        i % 2 === 1 ? (
          <Box
            key={i}
            component="span"
            sx={{
              fontFamily: '"JetBrains Mono", monospace',
              fontWeight: 700,
              color,
              bgcolor: `${color}1f`,
              borderRadius: 0.5,
              px: 0.4,
              py: 0.1,
              // Long identifiers must be able to wrap inside a sentence.
              wordBreak: "break-word",
            }}
          >
            {part}
          </Box>
        ) : (
          <Box component="span" key={i}>
            {part}
          </Box>
        ),
      )}
    </>
  );
}

export function KeyFindings({ findings }: { findings: string[] }) {
  const theme = useTheme();

  return (
    <Stack spacing={1}>
      {findings.map((line, index) => {
        const subject = findingSubject(line);
        const color = brandTone(subject.tone, theme);
        return (
          <Stack
            key={index}
            direction="row"
            spacing={1.5}
            sx={{
              p: 1.5,
              border: 1,
              borderColor: "divider",
              borderLeft: 3,
              borderLeftColor: color,
              borderRadius: 1,
              bgcolor:
                theme.palette.mode === "dark"
                  ? `${color}0d`
                  : `${color}12`,
            }}
          >
            <Stack
              alignItems="center"
              spacing={0.5}
              sx={{ minWidth: 62, flexShrink: 0 }}
            >
              <Box
                sx={{
                  display: "flex",
                  color,
                  "& svg": { fontSize: 20, display: "block" },
                }}
              >
                {subject.icon}
              </Box>
              <Typography
                variant="caption"
                sx={{
                  color,
                  fontWeight: 700,
                  lineHeight: 1.2,
                  textAlign: "center",
                }}
              >
                {subject.label}
              </Typography>
            </Stack>

            <Box sx={{ minWidth: 0 }}>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: "block", fontWeight: 700 }}
              >
                Finding {index + 1}
              </Typography>
              <Typography variant="body2" component="div">
                <Highlighted text={line} color={color} />
              </Typography>
            </Box>
          </Stack>
        );
      })}
    </Stack>
  );
}
