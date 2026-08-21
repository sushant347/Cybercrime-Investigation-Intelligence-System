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
 * and every pair opens to the factor-by-factor arithmetic behind its score,
 * closing on the total the confidence is derived from. The engine's own
 * explanation paragraph is kept verbatim behind a disclosure inside that
 * panel. Nothing is summarised away; it is only folded until asked for.
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

/**
 * The matched values re-counted by how rare each one is.
 *
 * This is the number the contribution is actually built from: contribution =
 * weight x effective matches, for entity factors *and* for the non-entity ones
 * (a matching hash or a proximity window has no corpus rarity, so its
 * effective count is simply the counted matches). Showing the mean specificity
 * in its place made the row look like bad arithmetic — two domains at mean
 * specificity 0.65 and weight 0.60 read as 0.39 but contribute 0.77, because
 * the specificities are summed, not averaged.
 *
 * `effective_matches` is optional on artifacts stored before it existed, so it
 * falls back to the value implied by the contribution.
 */
function effectiveMatches(factor: CorrelationFactor): number {
  if (typeof factor.effective_matches === "number") return factor.effective_matches;
  return factor.weight > 0 ? factor.contribution / factor.weight : factor.matches;
}

/**
 * What a factor actually matched, without the lead-in naming the factor.
 *
 * The engine writes each reason as a standalone sentence — "Both items
 * reference the same phones: +977…" — because it is also concatenated into the
 * one-paragraph explanation. Beside a column that already says "Phones" that
 * opening repeats on every row and pushes the values themselves off to the
 * right, so the two known templates are trimmed and anything else is shown
 * exactly as the engine wrote it.
 */
function factorDetail(factor: CorrelationFactor): string {
  const label = factor.factor.replace(/_/g, " ");
  const leadIns = [
    `Both items reference the same ${label}: `,
    "Threat intelligence flags the same malicious indicators in both items: ",
  ];
  const lead = leadIns.find((candidate) => factor.reason.startsWith(candidate));
  return lead ? factor.reason.slice(lead.length) : factor.reason;
}

/**
 * The factor breakdown: what matched, and what each match was worth.
 *
 * Ordered by contribution so the factor that actually carried the pair is the
 * first thing read, and closed by the total the confidence is derived from —
 * without it the columns are six numbers that never visibly add up to
 * anything.
 */
function FactorTable({
  factors,
  totalWeight,
}: {
  factors: CorrelationFactor[];
  totalWeight: number;
}) {
  const theme = useTheme();
  const ordered = [...factors].sort((a, b) => b.contribution - a.contribution);

  return (
    <TableContainer sx={{ overflowX: "auto" }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Factor</TableCell>
            <TableCell sx={{ minWidth: 240 }}>What matched</TableCell>
            <TableCell align="right">Matches</TableCell>
            <Tooltip title="How identifying this kind of match is, before rarity is considered. Configured per entity type — a wallet address counts for more than a round sum of money.">
              <TableCell align="right">Weight</TableCell>
            </Tooltip>
            <Tooltip title="The matches re-counted by how rare each value is across every item held: a value seen almost nowhere else counts close to 1, a corpus-wide one close to 0. Hover a figure for the per-value reasoning.">
              <TableCell align="right">Effective</TableCell>
            </Tooltip>
            <Tooltip title="Weight × effective matches — this factor's share of the total below.">
              <TableCell align="right">Contribution</TableCell>
            </Tooltip>
          </TableRow>
        </TableHead>
        <TableBody>
          {ordered.map((factor) => {
            const specificity = factorSpecificity(factor);
            return (
              <TableRow key={factor.factor}>
                <TableCell
                  sx={{
                    textTransform: "capitalize",
                    whiteSpace: "nowrap",
                    fontWeight: 700,
                    verticalAlign: "top",
                  }}
                >
                  {factor.factor.replace(/_/g, " ")}
                </TableCell>
                <TableCell sx={{ verticalAlign: "top", wordBreak: "break-word" }}>
                  {factorDetail(factor)}
                </TableCell>
                <TableCell align="right" sx={{ verticalAlign: "top" }}>
                  {factor.matches}
                </TableCell>
                <TableCell align="right" sx={{ verticalAlign: "top" }}>
                  {factor.weight.toFixed(2)}
                </TableCell>
                <TableCell align="right" sx={{ verticalAlign: "top" }}>
                  <Tooltip
                    title={
                      specificity === null ? (
                        "Not a value-based factor, so there is no corpus rarity to weigh — the effective count is simply the matches."
                      ) : (
                        <Stack spacing={0.5}>
                          <Typography variant="caption" sx={{ fontWeight: 700 }}>
                            Mean specificity {specificity.toFixed(2)}
                          </Typography>
                          {(factor.value_details ?? []).map((d) => (
                            <Typography key={d.value} variant="caption">
                              {d.reason}
                            </Typography>
                          ))}
                        </Stack>
                      )
                    }
                  >
                    <Box
                      component="span"
                      sx={
                        specificity === null
                          ? undefined
                          : {
                              fontWeight: 700,
                              color: brandTone(specificityTone(specificity), theme),
                            }
                      }
                    >
                      {effectiveMatches(factor).toFixed(2)}
                    </Box>
                  </Tooltip>
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    verticalAlign: "top",
                    fontWeight: 700,
                    fontFamily: '"JetBrains Mono", monospace',
                  }}
                >
                  {factor.contribution.toFixed(2)}
                </TableCell>
              </TableRow>
            );
          })}
          <TableRow>
            <TableCell
              colSpan={5}
              align="right"
              sx={{ fontWeight: 700, borderBottom: 0 }}
            >
              Total weight
            </TableCell>
            <TableCell
              align="right"
              sx={{
                fontWeight: 700,
                borderBottom: 0,
                fontFamily: '"JetBrains Mono", monospace',
              }}
            >
              {totalWeight.toFixed(2)}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </TableContainer>
  );
}

/** A pair row plus its collapsible detail row. */
function PairRow({ pair }: { pair: EvidencePairCorrelation }) {
  const [open, setOpen] = useState(false);
  const [showSentence, setShowSentence] = useState(false);
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
            {/* This panel held the same content three times over: the engine's
                explanation paragraph, then `correlation_reasons` as bullets —
                which is literally the list of factor reasons the paragraph is
                built from — and then those same reasons again in the table's
                Reason column. The bullets are gone, the reasons live in the
                table where their numbers are, and the paragraph is kept
                verbatim behind a disclosure so nothing the engine wrote is
                lost. */}
            <Stack spacing={2} sx={{ py: 2, px: { xs: 0, sm: 2 } }}>
              <Box>
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="baseline"
                  flexWrap="wrap"
                  useFlexGap
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    {pair.factors.length} independent factor
                    {pair.factors.length === 1 ? "" : "s"}
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ fontFamily: '"JetBrains Mono", monospace' }}
                  >
                    total weight {pair.correlation_weight.toFixed(2)} → confidence{" "}
                    {pair.correlation_confidence.toFixed(2)}
                  </Typography>
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  Each factor contributes its <strong>weight</strong> — how
                  identifying that kind of match is — times its{" "}
                  <strong>effective</strong> matches, the match count re-counted
                  by how rare each value is across every item held. Those
                  contributions sum to the total weight, and confidence rises
                  with that total on a saturating curve: several independent
                  factors push it up, no single one reaches certainty alone.
                </Typography>
              </Box>

              {pair.factors.length > 0 && (
                <FactorTable
                  factors={pair.factors}
                  totalWeight={pair.correlation_weight}
                />
              )}

              <Box>
                <Typography
                  component="button"
                  type="button"
                  variant="caption"
                  onClick={() => setShowSentence((v) => !v)}
                  sx={{
                    background: "none",
                    border: 0,
                    p: 0,
                    cursor: "pointer",
                    color: "text.secondary",
                    textDecoration: "underline",
                    font: "inherit",
                  }}
                >
                  {showSentence ? "Hide" : "Show"} the engine&rsquo;s full
                  sentence
                </Typography>
                <Collapse in={showSentence} timeout="auto" unmountOnExit>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 1 }}
                  >
                    {pair.explanation}
                  </Typography>
                </Collapse>
              </Box>
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
