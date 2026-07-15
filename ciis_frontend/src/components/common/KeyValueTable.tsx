import { Table, TableBody, TableCell, TableRow, Typography } from "@mui/material";
import type { ReactNode } from "react";

import { titleCase } from "@/lib/format";

/** Two-column key/value table used for metadata, stats, and config views. */
export function KeyValueTable({
  data,
  render,
}: {
  data: Record<string, unknown>;
  render?: (key: string, value: unknown) => ReactNode;
}) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
        No data available.
      </Typography>
    );
  }
  return (
    <Table size="small">
      <TableBody>
        {entries.map(([key, value]) => (
          <TableRow key={key} hover>
            <TableCell sx={{ width: "40%", color: "text.secondary", fontWeight: 600 }}>
              {titleCase(key)}
            </TableCell>
            <TableCell sx={{ wordBreak: "break-word" }}>
              {render ? (
                render(key, value)
              ) : (
                <Typography variant="body2" component="span">
                  {typeof value === "object" && value !== null
                    ? JSON.stringify(value)
                    : String(value ?? "—")}
                </Typography>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
