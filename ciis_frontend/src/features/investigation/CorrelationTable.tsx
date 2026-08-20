import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
import {
  Box,
  Chip,
  Collapse,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import { useMemo, useState } from "react";

import { ConfidenceBar } from "@/components/common/ConfidenceBar";
import { StatusChip } from "@/components/common/StatusChip";
import { brandTone } from "@/theme/theme";
import type { CorrelationFactor, EvidencePairCorrelation } from "@/types";

/**
 * Evidence correlations as a scannable table.
 *
 * One accordion per pair does not survive a real case: pairs grow with the
 * square of the evidence count, so thirty items produced a page of headers
 * hundreds of rows long with no way to find the strong links among the weak
 * ones. The same pairs are now a sorted, filterable table — strongest first —
 * and every pair still opens to exactly the detail the accordion held: the
 * engine's explanation, its reasons, and the per-factor contribution table.
 * Nothing is summarised away; it is only folded until asked for.
 */

type SortKey = "confidence" | "pair";

/** The strength the engine assigns to a pair it examined and rejected. */
const UNRELATED = "NO_RELATIONSHIP";

const specificityTone = (specificity: number) =>
  specificity >= 0.7 ? "low" : specificity >= 0.4 ? "high" : ("critical" as const);

/** Mean specificity of the values behind a factor; null for non-entity factors. */
function factorSpecificity(factor: CorrelationFactor): number | null {
  const details = factor.value_details ?? [];
  if (!details.length) return null;
  return details.reduce((sum, d) => sum + d.specificity, 0) / details.length;
}

/** The factor breakdown, unchanged from the previous accordion body. */
function FactorTable({ factors }: { factors: CorrelationFactor[] }) {
  const theme = useTheme();
  return (
    <TableContainer sx={{ overflowX: "auto" }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Factor</TableCell>
            <TableCell align="right">Matches</TableCell>
            <TableCell align="right">Weight</TableCell>
            <Tooltip title="How identifying the matched values are. 1.00 means the value appears almost nowhere else in the corpus; a low figure means it is common, so it barely supports a link.">
              <TableCell align="right">Specificity</TableCell>
            </Tooltip>
            <TableCell align="right">Contribution</TableCell>
            <TableCell>Reason</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {factors.map((factor) => {
            const specificity = factorSpecificity(factor);
            return (
              <TableRow key={factor.factor}>
                <TableCell sx={{ textTransform: "capitalize", whiteSpace: "nowrap" }}>
                  {factor.factor.replace(/_/g, " ")}
                </TableCell>
                <TableCell align="right">{factor.matches}</TableCell>
                <TableCell align="right">{factor.weight}</TableCell>
                <TableCell align="right">
                  {specificity === null ? (
                    "—"
                  ) : (
                    <Tooltip
                      title={
                        <Stack spacing={0.5}>
                          {(factor.value_details ?? []).map((d) => (
                            <Typography key={d.value} variant="caption">
                              {d.reason}
                            </Typography>
                          ))}
                        </Stack>
                      }
                    >
                      <Box
                        component="span"
                        sx={{ fontWeight: 700, color: brandTone(specificityTone(specificity), theme) }}
                      >
                        {specificity.toFixed(2)}
                      </Box>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell align="right">{factor.contribution.toFixed(2)}</TableCell>
                <TableCell sx={{ minWidth: 220 }}>{factor.reason}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

/** A pair row plus its collapsible detail row. */
function PairRow({ pair }: { pair: EvidencePairCorrelation }) {
  const [open, setOpen] = useState(false);
  // The strongest couple of factors, so the row says *why* without expanding.
  const topFactors = [...pair.factors]
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, 3);

  return (
    <>
      <TableRow
        hover
        onClick={() => setOpen((v) => !v)}
        sx={{ cursor: "pointer", "& > td": { borderBottom: open ? 0 : undefined } }}
      >
        <TableCell sx={{ width: 44, pr: 0 }}>
          <IconButton size="small" aria-label={open ? "Hide detail" : "Show detail"}>
            {open ? (
              <KeyboardArrowDownIcon fontSize="small" />
            ) : (
              <KeyboardArrowRightIcon fontSize="small" />
            )}
          </IconButton>
        </TableCell>
        <TableCell sx={{ whiteSpace: "nowrap" }}>
          <Typography
            variant="body2"
            sx={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 700 }}
          >
            {pair.evidence_a} ↔ {pair.evidence_b}
          </Typography>
        </TableCell>
        <TableCell>
          <StatusChip value={pair.relationship_strength} />
        </TableCell>
        <TableCell sx={{ minWidth: 160 }}>
          <ConfidenceBar
            value={pair.correlation_confidence}
            scale="fraction"
            label="Correlation confidence"
          />
        </TableCell>
        <TableCell>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {topFactors.map((factor) => (
              <Chip
                key={factor.factor}
                size="small"
                variant="outlined"
                label={factor.factor.replace(/_/g, " ")}
                sx={{ textTransform: "capitalize", height: 20, fontSize: 11 }}
              />
            ))}
            {pair.factors.length > topFactors.length && (
              <Chip
                size="small"
                variant="outlined"
                label={`+${pair.factors.length - topFactors.length}`}
                sx={{ height: 20, fontSize: 11 }}
              />
            )}
          </Stack>
        </TableCell>
      </TableRow>

      <TableRow>
        <TableCell colSpan={5} sx={{ py: 0, borderBottom: open ? undefined : 0 }}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Stack spacing={1.5} sx={{ py: 2, px: { xs: 0, sm: 2 } }}>
              <Typography variant="body2">{pair.explanation}</Typography>
              {pair.correlation_reasons.length > 0 && (
                <Stack spacing={0.5}>
                  {pair.correlation_reasons.map((reason, i) => (
                    <Typography key={i} variant="body2" color="text.secondary">
                      • {reason}
                    </Typography>
                  ))}
                </Stack>
              )}
              {pair.factors.length > 0 && <FactorTable factors={pair.factors} />}
            </Stack>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

export function CorrelationTable({
  pairs,
  strengthDistribution,
}: {
  pairs: EvidencePairCorrelation[];
  strengthDistribution: Record<string, number>;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("confidence");
  const [descending, setDescending] = useState(true);
  const [strengthFilter, setStrengthFilter] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = pairs.filter((pair) => {
      const unrelated = pair.relationship_strength === UNRELATED;
      // The engine examines every possible pair and keeps the rejections, so
      // `pairs` is n(n-1)/2 entries of which most are usually
      // NO_RELATIONSHIP. Showing all of them by default contradicted the
      // header ("10 related pair(s) of 55 examined") and buried the ten links
      // that matter under forty-five that do not. The rejections stay one
      // click away rather than being dropped.
      if (strengthFilter === null && unrelated) return false;
      if (strengthFilter && pair.relationship_strength !== strengthFilter) return false;
      if (!needle) return true;
      return (
        pair.evidence_a.toLowerCase().includes(needle) ||
        pair.evidence_b.toLowerCase().includes(needle) ||
        pair.factors.some((f) => f.factor.toLowerCase().includes(needle))
      );
    });
    const direction = descending ? -1 : 1;
    return [...filtered].sort((a, b) => {
      if (sortKey === "pair") {
        return (
          direction *
          `${a.evidence_a}${a.evidence_b}`.localeCompare(`${b.evidence_a}${b.evidence_b}`)
        );
      }
      return direction * (a.correlation_confidence - b.correlation_confidence);
    });
  }, [pairs, query, strengthFilter, sortKey, descending]);

  const relatedCount = pairs.filter((p) => p.relationship_strength !== UNRELATED).length;
  const unrelatedCount = pairs.length - relatedCount;

  // What the count is measured against depends on the active filter, so the
  // denominator has to move with it — "45 of 10 related pair(s)" is not a
  // sentence.
  const scope =
    strengthFilter === null
      ? { total: relatedCount, label: "related pair(s)" }
      : strengthFilter === UNRELATED
        ? { total: unrelatedCount, label: "pair(s) examined and found unrelated" }
        : {
            total: pairs.filter(
              (p) => p.relationship_strength === strengthFilter,
            ).length,
            label: `${strengthFilter.replace(/_/g, " ").toLowerCase()} pair(s)`,
          };

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setDescending((v) => !v);
    else {
      setSortKey(key);
      setDescending(key === "confidence");
    }
  };

  return (
    <Stack spacing={1.5}>
      {/* ------------------------------------------------------- the controls */}
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", md: "center" }}
        justifyContent="space-between"
      >
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {Object.entries(strengthDistribution).map(([strength, count]) => {
            const active = strengthFilter === strength;
            return (
              <Chip
                key={strength}
                size="small"
                label={`${strength}: ${count}`}
                variant={active ? "filled" : "outlined"}
                color={active ? "primary" : "default"}
                onClick={() => setStrengthFilter(active ? null : strength)}
                sx={{ textTransform: "capitalize" }}
              />
            );
          })}
          {strengthFilter && (
            <Chip
              size="small"
              label="clear filter"
              variant="outlined"
              onDelete={() => setStrengthFilter(null)}
            />
          )}
        </Stack>
        <TextField
          size="small"
          placeholder="Filter by evidence id or factor…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          sx={{ minWidth: { md: 280 } }}
        />
      </Stack>

      <Typography variant="caption" color="text.secondary">
        Showing {visible.length} of {scope.total} {scope.label}
        {unrelatedCount > 0 && strengthFilter === null && (
          <>
            {" "}
            — {unrelatedCount} further pair(s) were examined and found
            unrelated; select <strong>{UNRELATED}</strong> above to include them
          </>
        )}
        . Select a row to see the engine&apos;s reasoning and the
        factor-by-factor contribution.
      </Typography>

      {/* ---------------------------------------------------------- the table */}
      <TableContainer
        sx={{
          // Bounded so a large case cannot stretch the page indefinitely; the
          // header stays put while the pairs scroll underneath it.
          maxHeight: 560,
          border: 1,
          borderColor: "divider",
          borderRadius: 1,
        }}
      >
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 44 }} />
              <TableCell>
                <TableSortLabel
                  active={sortKey === "pair"}
                  direction={descending ? "desc" : "asc"}
                  onClick={() => toggleSort("pair")}
                >
                  Evidence pair
                </TableSortLabel>
              </TableCell>
              <TableCell>Strength</TableCell>
              <TableCell>
                <TableSortLabel
                  active={sortKey === "confidence"}
                  direction={descending ? "desc" : "asc"}
                  onClick={() => toggleSort("confidence")}
                >
                  Confidence
                </TableSortLabel>
              </TableCell>
              <TableCell>Why they link</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visible.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                    No pair matches the current filter.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              visible.map((pair) => (
                <PairRow key={`${pair.evidence_a}-${pair.evidence_b}`} pair={pair} />
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
