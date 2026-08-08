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

/**
 * Semantic tones that stay legible in *both* modes.
 *
 * The report view previously hardcoded a single set of print-oriented inks
 * (`#14532d`, `#4a5568`, …). Those are chosen for dark-on-white paper, so on
 * the dark canvas they sat at roughly 1.5:1 against the background and were
 * effectively unreadable. Each tone therefore carries a per-mode value, and
 * every one of these pairs clears WCAG AA (4.5:1) on its own surface.
 */
export const TONE = {
  good: { dark: "#4ade80", light: "#1a7f5a" },
  warn: { dark: "#fbbf24", light: "#a86612" },
  bad: { dark: "#ff6b6d", light: "#b3261e" },
  neutral: { dark: "#94a3b8", light: "#4a5568" },
  accent: { dark: "#5eead4", light: "#14532d" },
} as const;

export type ToneName = keyof typeof TONE;

/** Pick the readable ink for a semantic tone in the active mode. */
export function toneColor(tone: ToneName, mode: "dark" | "light"): string {
  return TONE[tone][mode];
}

/**
 * Whether a *higher* number is good or bad for a given metric.
 *
 * Priority components are not directionally uniform: a high
 * `evidence_confidence` is reassuring, while an equally high `forgery_risk`
 * is alarming. Rendering both in the same accent colour told the reader they
 * meant the same thing, so scores are coloured by direction instead.
 */
export function metricDirection(name: string): "higher_is_good" | "higher_is_bad" | "neutral" {
  switch (name) {
    case "evidence_confidence":
    case "correlation_strength":
      return "higher_is_good";
    case "forgery_risk":
    case "threat_intelligence":
    case "campaign_size":
    case "timeline_criticality":
      return "higher_is_bad";
    default:
      return "neutral";
  }
}

/**
 * Severity inks that stay readable on the active surface.
 *
 * `BRAND.*` is tuned for the dark canvas. Used unchanged in light mode the
 * warmer bands fail badly as *text*: `medium` (#ffd666) on white is about
 * 1.5:1 and `low` (#52c41a) about 2.2:1, well under AA — and `StatusChip`
 * paints the label in exactly this colour over a 10%-alpha wash of itself.
 * That made "MEDIUM" and "WEAK" chips nearly unreadable in light mode
 * everywhere they appear. Light mode therefore gets darkened equivalents of
 * the same hues; dark mode is unchanged.
 */
const LIGHT_SEVERITY = {
  critical: "#c2261f",
  high: "#a85a08",
  medium: "#8a6100",
  low: "#2b7a12",
} as const;

export function severityColor(value: string | undefined, theme: Theme): string {
  const light = theme.palette.mode === "light";
  switch ((value ?? "").toLowerCase()) {
    case "critical":
    case "urgent":
    case "failed":
    case "error":
      return light ? LIGHT_SEVERITY.critical : BRAND.critical;
    case "high":
    case "strong":
    case "warning":
      return light ? LIGHT_SEVERITY.high : BRAND.high;
    case "medium":
    case "moderate":
    case "running":
    case "queued":
      return light ? LIGHT_SEVERITY.medium : BRAND.medium;
    case "low":
    case "weak":
    case "completed":
    case "processed":
    case "info":
      return light ? LIGHT_SEVERITY.low : BRAND.low;
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
