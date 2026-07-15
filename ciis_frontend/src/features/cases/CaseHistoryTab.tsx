import HistoryIcon from "@mui/icons-material/History";
import {
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
} from "@mui/material";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { casesApi } from "@/api";
import { EmptyState, ErrorState } from "@/components/common/EmptyState";
import { TableSkeleton } from "@/components/common/LoadingSkeleton";
import { apiErrorMessage } from "@/lib/apiClient";
import { formatDateTime, titleCase } from "@/lib/format";

export function CaseHistoryTab({ caseId }: { caseId: string }) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["case-history", caseId, page, pageSize],
    queryFn: () => casesApi.history(caseId, { page: page + 1, page_size: pageSize }),
    placeholderData: keepPreviousData,
  });

  if (isPending) return <TableSkeleton />;
  if (isError) return <ErrorState message={apiErrorMessage(error)} onRetry={() => void refetch()} />;
  if (data.results.length === 0) {
    return (
      <EmptyState
        icon={<HistoryIcon />}
        title="No workflow history yet"
        description="Case creation, status changes, and assignments will appear here."
      />
    );
  }

  return (
    <Card>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Time</TableCell>
            <TableCell>User</TableCell>
            <TableCell>Action</TableCell>
            <TableCell>Detail</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.results.map((entry) => (
            <TableRow key={entry.id} hover>
              <TableCell sx={{ whiteSpace: "nowrap" }}>
                {formatDateTime(entry.created_at)}
              </TableCell>
              <TableCell>{entry.username || "system"}</TableCell>
              <TableCell>{titleCase(entry.action)}</TableCell>
              <TableCell>{entry.detail}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <TablePagination
        component="div"
        count={data.count}
        page={page}
        rowsPerPage={pageSize}
        onPageChange={(_, p) => setPage(p)}
        onRowsPerPageChange={(e) => {
          setPageSize(Number(e.target.value));
          setPage(0);
        }}
        rowsPerPageOptions={[10, 25, 50]}
      />
    </Card>
  );
}
