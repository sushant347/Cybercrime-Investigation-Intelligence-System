import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);

export const formatDateTime = (value?: string | null): string =>
  value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "—";

export const formatDate = (value?: string | null): string =>
  value ? dayjs(value).format("YYYY-MM-DD") : "—";

export const timeAgo = (value?: string | null): string =>
  value ? dayjs(value).fromNow() : "—";

export const formatBytes = (bytes?: number | string | null): string => {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
};

export const formatPercent = (value?: number | null, fractionAlready = false): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(fractionAlready ? value * 100 : value).toFixed(1)}%`;
};

export const truncateHash = (hash?: string, length = 12): string =>
  hash ? `${hash.slice(0, length)}…` : "—";

export const titleCase = (value: string): string =>
  value.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
