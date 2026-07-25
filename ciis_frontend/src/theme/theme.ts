/**
 * CIIS design system - professional law-enforcement forensics look.
 * Dark mode is the default operating environment; light mode is fully
 * supported. All colors flow from these tokens.
 */
import { createTheme, type Theme } from "@mui/material/styles";

export const BRAND = {
  primary: "#3d7eff",
  primaryDark: "#2a5cd4",
  accent: "#00c2a8",
  critical: "#ff4d4f",
  high: "#ff9f43",
  medium: "#ffd666",
  low: "#52c41a",
};

const typography = {
  fontFamily: '"Inter", "Segoe UI", "Roboto", sans-serif',
  h4: { fontWeight: 800, letterSpacing: "-0.02em" },
  h5: { fontWeight: 700, letterSpacing: "-0.01em" },
  h6: { fontWeight: 700 },
  subtitle1: { fontWeight: 600 },
  subtitle2: { fontWeight: 600 },
  overline: { fontWeight: 600, letterSpacing: "0.08em" },
  button: { textTransform: "none" as const, fontWeight: 600 },
  body2: { lineHeight: 1.6 },
} as const;

const shape = { borderRadius: 10 } as const;

export function buildTheme(mode: "dark" | "light"): Theme {
  const dark = mode === "dark";
  return createTheme({
    palette: {
      mode,
      primary: { main: BRAND.primary },
      secondary: { main: BRAND.accent },
      error: { main: BRAND.critical },
      warning: { main: BRAND.high },
      success: { main: BRAND.low },
      background: dark
        ? { default: "#0b1020", paper: "#121a2e" }
        : { default: "#f4f6fb", paper: "#ffffff" },
      divider: dark ? "rgba(148,163,204,0.16)" : "rgba(15,23,42,0.10)",
      text: dark
        ? { primary: "#e6ebf7", secondary: "#93a1c0" }
        : { primary: "#101828", secondary: "#5b6579" },
    },
    typography,
    shape,
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          code: { fontFamily: '"JetBrains Mono", monospace' },
          "::-webkit-scrollbar": { width: 8, height: 8 },
          "::-webkit-scrollbar-thumb": {
            backgroundColor: dark ? "#2b3856" : "#c3cad9",
            borderRadius: 8,
          },
          "::selection": {
            backgroundColor: dark
              ? "rgba(61,126,255,0.35)"
              : "rgba(61,126,255,0.20)",
          },
          ":focus-visible": {
            outline: `2px solid ${BRAND.primary}`,
            outlineOffset: 2,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
            border: `1px solid ${dark ? "rgba(148,163,204,0.12)" : "rgba(15,23,42,0.08)"}`,
          },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            transition: "border-color 160ms ease, box-shadow 160ms ease",
          },
        },
      },
      MuiCardHeader: {
        styleOverrides: {
          title: { fontSize: "1rem", fontWeight: 700 },
          subheader: { fontSize: "0.8rem" },
        },
      },
      MuiCardActionArea: {
        styleOverrides: {
          root: {
            transition: "transform 160ms ease",
            "&:hover": { transform: "translateY(-2px)" },
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 8, paddingInline: 14 },
          containedPrimary: {
            "&:hover": { backgroundColor: BRAND.primaryDark },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: BRAND.primary,
            },
          },
        },
      },
      MuiTabs: {
        styleOverrides: {
          indicator: { height: 3, borderRadius: 3 },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: { minHeight: 44, fontWeight: 600 },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            "&.MuiTableRow-hover:hover": {
              backgroundColor: dark
                ? "rgba(61,126,255,0.06)"
                : "rgba(61,126,255,0.04)",
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          head: {
            fontWeight: 700,
            fontSize: "0.75rem",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: dark ? "#93a1c0" : "#5b6579",
            whiteSpace: "nowrap",
            backgroundColor: dark ? "rgba(148,163,204,0.05)" : "rgba(15,23,42,0.02)",
          },
        },
      },
      MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
      MuiDialog: {
        styleOverrides: { paper: { borderRadius: 14 } },
      },
      MuiTooltip: {
        defaultProps: { arrow: true },
        styleOverrides: {
          tooltip: { fontSize: "0.75rem", fontWeight: 500 },
        },
      },
      MuiLinearProgress: {
        styleOverrides: { root: { borderRadius: 4 } },
      },
      MuiAlert: {
        styleOverrides: { root: { borderRadius: 10 } },
      },
    },
  });
}

/** Engine value -> UI color, shared everywhere (bands, strengths, statuses). */
export function severityColor(value: string | undefined, theme: Theme): string {
  switch ((value ?? "").toLowerCase()) {
    case "critical":
    case "urgent":
    case "failed":
    case "error":
      return BRAND.critical;
    case "high":
    case "strong":
    case "warning":
      return BRAND.high;
    case "medium":
    case "moderate":
    case "running":
    case "queued":
      return BRAND.medium;
    case "low":
    case "weak":
    case "completed":
    case "processed":
    case "info":
      return BRAND.low;
    default:
      return theme.palette.text.secondary;
  }
}

/** Node type -> color for the relationship graph (Module 6 legend).
 *  Structural roles (case/evidence/timeline event) and every entity type the
 *  engine can emit need a distinct colour; anything unmapped falls back to
 *  grey via `nodeColor`, which reads as "unclassified" in the legend. */
export const NODE_COLORS: Record<string, string> = {
  case: "#94a3b8",
  timeline_event: "#22d3ee",
  evidence: "#3d7eff",
  phone: "#00c2a8",
  phones: "#00c2a8",
  email: "#a970ff",
  emails: "#a970ff",
  url: "#ff9f43",
  urls: "#ff9f43",
  domain: "#f759ab",
  domains: "#f759ab",
  wallet: "#ffd666",
  wallets: "#ffd666",
  bank_account: "#36cfc9",
  bank_accounts: "#36cfc9",
  esewa_id: "#36cfc9",
  esewa_ids: "#36cfc9",
  device: "#597ef7",
  devices: "#597ef7",
  person: "#ff4d4f",
  persons: "#ff4d4f",
  brand: "#73d13d",
  brands: "#73d13d",
  social_account: "#9254de",
  social_accounts: "#9254de",
  // Temporal / monetary entities extracted from evidence text.
  money: "#52c41a",
  amount: "#52c41a",
  amounts: "#52c41a",
  date: "#f0a020",
  dates: "#f0a020",
  time: "#fbbf24",
  times: "#fbbf24",
  otp: "#ff7a45",
  otps: "#ff7a45",
  keyword: "#8c9bba",
  keywords: "#8c9bba",
};

export const nodeColor = (type: string): string =>
  NODE_COLORS[type.toLowerCase()] ?? "#8c9bba";
