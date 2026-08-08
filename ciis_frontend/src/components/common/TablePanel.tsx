import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import SearchIcon from "@mui/icons-material/Search";
import {
  Box,
  Chip,
  Collapse,
  IconButton,
  InputAdornment,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TablePagination,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { Fragment, useMemo, useState, type ReactNode } from "react";

export interface TableColumn<T> {
  id: string;
  label: ReactNode;
  /** Tooltip shown on the header cell — use for jargon. */
  hint?: string;
  align?: "left" | "right" | "center";
  width?: number | string;
  /** Return a sortable primitive. Omit to make the column unsortable. */
  sortValue?: (row: T) => number | string;
  render: (row: T) => ReactNode;
}

export interface FilterOption {
  label: string;
  value: string;
  count?: number;
  color?: string;
}

/**
 * A dense, scannable table for engine output.
 *
 * The investigation view previously stacked one MUI `Accordion` per result.
 * With 36 correlation pairs and 13 suspects that is ~50 collapsed cards on a
 * single page — the reader scrolls for a long time and still cannot compare
 * two rows, because each row is a full-width card rather than an aligned
 * column. On a large case it only gets worse.
 *
 * This replaces that with the structure the data actually wants:
 *
 * - **Aligned columns**, so confidences can be compared down the page.
 * - **Sorting**, defaulting to strongest-first — the top of the table is the
 *   part an investigator cares about.
 * - **Pagination**, so page height is constant no matter how large the case.
 * - **Filter chips** that actually filter. The strength counts were previously
 *   decorative; clicking one now narrows the table.
 * - **Search**, for jumping straight to a known identifier or evidence id.
 *
 * Detail is not lost — every row still expands to the full engine explanation.
 * It is one row open at a time, which keeps the page from growing unboundedly
 * and matches how the detail is actually read: one pair at a time.
 */
export function TablePanel<T>({
  rows,
  columns,
  getKey,
  renderDetail,
  filters,
  searchOf,
  searchPlaceholder = "Search…",
  initialSort,
  pageSize = 10,
  emptyMessage = "Nothing to show.",
}: {
  rows: T[];
  columns: TableColumn<T>[];
  getKey: (row: T) => string;
  renderDetail?: (row: T) => ReactNode;
  filters?: {
    options: FilterOption[];
    /** Which filter bucket a row belongs to. */
    bucketOf: (row: T) => string;
  };
  searchOf?: (row: T) => string;
  searchPlaceholder?: string;
  initialSort?: { id: string; dir: "asc" | "desc" };
  pageSize?: number;
  emptyMessage?: string;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(pageSize);
  const [sort, setSort] = useState<{ id: string; dir: "asc" | "desc" } | null>(
    initialSort ?? null,
  );

  const visible = useMemo(() => {
    let out = rows;
    if (active && filters) out = out.filter((r) => filters.bucketOf(r) === active);
    if (query.trim() && searchOf) {
      const q = query.trim().toLowerCase();
      out = out.filter((r) => searchOf(r).toLowerCase().includes(q));
    }
    if (sort) {
      const col = columns.find((c) => c.id === sort.id);
      if (col?.sortValue) {
        const dir = sort.dir === "asc" ? 1 : -1;
        out = [...out].sort((a, b) => {
          const av = col.sortValue!(a);
          const bv = col.sortValue!(b);
          if (av === bv) return 0;
          return (av < bv ? -1 : 1) * dir;
        });
      }
    }
    return out;
  }, [rows, active, filters, query, searchOf, sort, columns]);

  // Keep the viewport anchored when a filter shrinks the result set below the
  // current page, rather than showing a blank page.
  const maxPage = Math.max(0, Math.ceil(visible.length / rowsPerPage) - 1);
  const safePage = Math.min(page, maxPage);
  const pageRows = visible.slice(safePage * rowsPerPage, safePage * rowsPerPage + rowsPerPage);

  const reset = () => {
    setPage(0);
    setExpanded(null);
  };

  return (
    <Box>
      {(filters || searchOf) && (
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          alignItems={{ sm: "center" }}
          justifyContent="space-between"
          sx={{ mb: 1.75 }}
        >
          {filters && (
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
              <Chip
                size="small"
                label={`All ${rows.length}`}
                onClick={() => {
                  setActive(null);
                  reset();
                }}
                variant={active === null ? "filled" : "outlined"}
                sx={{ fontWeight: 700 }}
              />
              {filters.options.map((opt) => (
                <Chip
                  key={opt.value}
                  size="small"
                  label={opt.count === undefined ? opt.label : `${opt.label} ${opt.count}`}
                  onClick={() => {
                    setActive(active === opt.value ? null : opt.value);
                    reset();
                  }}
                  variant={active === opt.value ? "filled" : "outlined"}
                  sx={{
                    textTransform: "capitalize",
                    fontWeight: 700,
                    ...(opt.color
                      ? active === opt.value
                        ? { bgcolor: opt.color, color: "#0b1020" }
                        : { color: opt.color, borderColor: opt.color }
                      : {}),
                  }}
                />
              ))}
            </Stack>
          )}

          {searchOf && (
            <TextField
              size="small"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                reset();
              }}
              placeholder={searchPlaceholder}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                },
              }}
              sx={{ minWidth: { sm: 240 } }}
            />
          )}
        </Stack>
      )}

      {visible.length === 0 ? (
        <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
          {rows.length === 0 ? emptyMessage : "No rows match the current filter."}
        </Typography>
      ) : (
        <>
          <Table size="small" sx={{ tableLayout: "fixed" }}>
            <TableHead>
              <TableRow>
                {renderDetail && <TableCell sx={{ width: 44 }} />}
                {columns.map((col) => (
                  <TableCell
                    key={col.id}
                    align={col.align}
                    sx={{ width: col.width, whiteSpace: "nowrap" }}
                  >
                    {col.sortValue ? (
                      <TableSortLabel
                        active={sort?.id === col.id}
                        direction={sort?.id === col.id ? sort.dir : "desc"}
                        onClick={() =>
                          setSort({
                            id: col.id,
                            dir: sort?.id === col.id && sort.dir === "desc" ? "asc" : "desc",
                          })
                        }
                      >
                        {col.hint ? <Tooltip title={col.hint}><span>{col.label}</span></Tooltip> : col.label}
                      </TableSortLabel>
                    ) : col.hint ? (
                      <Tooltip title={col.hint}>
                        <span>{col.label}</span>
                      </Tooltip>
                    ) : (
                      col.label
                    )}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {pageRows.map((row) => {
                const key = getKey(row);
                const open = expanded === key;
                return (
                  <Fragment key={key}>
                    <TableRow
                      hover
                      onClick={renderDetail ? () => setExpanded(open ? null : key) : undefined}
                      sx={{
                        cursor: renderDetail ? "pointer" : "default",
                        "& > td": { borderBottom: open ? 0 : undefined },
                      }}
                    >
                      {renderDetail && (
                        <TableCell sx={{ width: 44 }}>
                          <IconButton size="small" aria-label={open ? "Collapse" : "Expand"}>
                            <ExpandMoreIcon
                              fontSize="small"
                              sx={{
                                transform: open ? "rotate(180deg)" : "none",
                                transition: "transform 200ms ease",
                              }}
                            />
                          </IconButton>
                        </TableCell>
                      )}
                      {columns.map((col) => (
                        <TableCell
                          key={col.id}
                          align={col.align}
                          sx={{ width: col.width, overflow: "hidden", textOverflow: "ellipsis" }}
                        >
                          {col.render(row)}
                        </TableCell>
                      ))}
                    </TableRow>
                    {renderDetail && (
                      <TableRow>
                        <TableCell
                          colSpan={columns.length + 1}
                          sx={{ py: 0, borderBottom: open ? undefined : 0 }}
                        >
                          <Collapse in={open} timeout={220} unmountOnExit>
                            <Box sx={{ py: 2, px: 1 }}>{renderDetail(row)}</Box>
                          </Collapse>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>

          {visible.length > rowsPerPage && (
            <TablePagination
              component="div"
              count={visible.length}
              page={safePage}
              onPageChange={(_, p) => {
                setPage(p);
                setExpanded(null);
              }}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={(e) => {
                setRowsPerPage(parseInt(e.target.value, 10));
                reset();
              }}
              rowsPerPageOptions={[10, 25, 50]}
              sx={{ borderTop: 1, borderColor: "divider" }}
            />
          )}
        </>
      )}
    </Box>
  );
}
