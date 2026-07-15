import { Card, CardContent, Skeleton, Stack } from "@mui/material";

/** Generic loading skeletons: table rows, stat cards, detail blocks. */
export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <Stack spacing={1} sx={{ p: 2 }}>
      <Skeleton variant="rounded" height={36} />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} variant="rounded" height={44} />
      ))}
    </Stack>
  );
}

export function CardGridSkeleton({ cards = 4 }: { cards?: number }) {
  return (
    <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
      {Array.from({ length: cards }).map((_, i) => (
        <Card key={i} sx={{ flex: "1 1 220px" }}>
          <CardContent>
            <Skeleton width="55%" />
            <Skeleton variant="text" height={44} width="35%" />
          </CardContent>
        </Card>
      ))}
    </Stack>
  );
}

export function DetailSkeleton() {
  return (
    <Stack spacing={2} sx={{ p: 2 }}>
      <Skeleton variant="rounded" height={56} />
      <Skeleton variant="rounded" height={160} />
      <Skeleton variant="rounded" height={240} />
    </Stack>
  );
}
