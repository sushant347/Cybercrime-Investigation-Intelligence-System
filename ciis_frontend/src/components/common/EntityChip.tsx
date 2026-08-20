import AccountBalanceIcon from "@mui/icons-material/AccountBalance";
import AlternateEmailIcon from "@mui/icons-material/AlternateEmail";
import ChatIcon from "@mui/icons-material/Chat";
import CreditCardIcon from "@mui/icons-material/CreditCard";
import CurrencyBitcoinIcon from "@mui/icons-material/CurrencyBitcoin";
import FingerprintIcon from "@mui/icons-material/Fingerprint";
import LanguageIcon from "@mui/icons-material/Language";
import PhoneIphoneIcon from "@mui/icons-material/PhoneIphone";
import WalletIcon from "@mui/icons-material/Wallet";
import { Box, Stack, Tooltip, Typography, useTheme } from "@mui/material";
import type { ReactElement } from "react";

import { brandTone, type BRAND } from "@/theme/theme";

/**
 * One captured identifier, rendered so it reads as a *thing* rather than as
 * body text.
 *
 * Suspect anchors used to appear as plain monospace strings in an accordion
 * header, which made a wallet id, a phone number and a Telegram handle look
 * identical at a glance. Each identifier family now carries its own icon and
 * colour, so the kinds of identity a case is built on are legible before
 * anything is expanded.
 *
 * Types come from `InvestigationConfig.suspect_identity_types`, which mixes
 * plural entity names with a legacy vocabulary; both are mapped here, and an
 * unrecognised type degrades to a neutral fingerprint rather than breaking.
 */

type EntityFamily = {
  icon: ReactElement;
  /** Resolved against the active theme — see `brandTone`. */
  tone: keyof typeof BRAND;
  /** Human label for the identifier family, used when no value is shown. */
  label: string;
};

const FAMILIES: Record<string, EntityFamily> = {
  phones: { icon: <PhoneIphoneIcon />, tone: "accent", label: "Phone" },
  whatsapp_numbers: { icon: <ChatIcon />, tone: "accent", label: "WhatsApp" },
  emails: { icon: <AlternateEmailIcon />, tone: "primary", label: "Email" },
  esewa_ids: { icon: <WalletIcon />, tone: "critical", label: "eSewa" },
  khalti_ids: { icon: <WalletIcon />, tone: "critical", label: "Khalti" },
  imepay_ids: { icon: <WalletIcon />, tone: "critical", label: "IME Pay" },
  wallets: { icon: <WalletIcon />, tone: "critical", label: "Wallet" },
  bank_accounts: { icon: <AccountBalanceIcon />, tone: "critical", label: "Bank account" },
  card_numbers: { icon: <CreditCardIcon />, tone: "critical", label: "Card" },
  eth_wallets: { icon: <CurrencyBitcoinIcon />, tone: "high", label: "ETH wallet" },
  btc_wallets: { icon: <CurrencyBitcoinIcon />, tone: "high", label: "BTC wallet" },
  telegram_usernames: { icon: <ChatIcon />, tone: "medium", label: "Telegram" },
  facebook_usernames: { icon: <ChatIcon />, tone: "medium", label: "Facebook" },
  instagram_usernames: { icon: <ChatIcon />, tone: "medium", label: "Instagram" },
  social_accounts: { icon: <ChatIcon />, tone: "medium", label: "Social account" },
  urls: { icon: <LanguageIcon />, tone: "primary", label: "URL" },
  domains: { icon: <LanguageIcon />, tone: "primary", label: "Domain" },
};

const FALLBACK: EntityFamily = {
  icon: <FingerprintIcon />,
  tone: "primary",
  label: "Identifier",
};

export function entityFamily(entityType: string): EntityFamily {
  return FAMILIES[entityType] ?? FALLBACK;
}

/** Readable label for an identifier type ("esewa_ids" -> "eSewa"). */
export function entityTypeLabel(entityType: string): string {
  return (
    FAMILIES[entityType]?.label ??
    entityType.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())
  );
}

export function EntityChip({
  entityType,
  value,
  size = "medium",
  flagged = false,
  title,
}: {
  entityType: string;
  value: string;
  size?: "small" | "medium";
  /** Draws the threat-intelligence outline. */
  flagged?: boolean;
  title?: string;
}) {
  const theme = useTheme();
  const family = entityFamily(entityType);
  const color = brandTone(flagged ? "critical" : family.tone, theme);
  const compact = size === "small";

  const chip = (
    <Stack
      direction="row"
      alignItems="center"
      spacing={compact ? 0.75 : 1}
      sx={{
        px: compact ? 0.75 : 1.25,
        py: compact ? 0.25 : 0.6,
        borderRadius: 1.5,
        border: 1,
        borderColor: flagged ? color : `${color}66`,
        bgcolor: `${color}1a`,
        maxWidth: "100%",
        minWidth: 0,
        // A flagged anchor must survive being skimmed past.
        boxShadow: flagged ? `0 0 0 1px ${color}55` : "none",
      }}
    >
      <Box
        sx={{
          display: "flex",
          color,
          "& svg": { fontSize: compact ? 15 : 18, display: "block" },
        }}
      >
        {family.icon}
      </Box>
      <Stack sx={{ minWidth: 0 }}>
        <Typography
          variant={compact ? "caption" : "body2"}
          noWrap
          sx={{
            fontFamily: '"JetBrains Mono", monospace',
            fontWeight: 700,
            color: theme.palette.text.primary,
            lineHeight: 1.35,
            minWidth: 0,
          }}
        >
          {value}
        </Typography>
        {!compact && (
          <Typography
            variant="caption"
            sx={{ color, lineHeight: 1.2, fontWeight: 600 }}
          >
            {family.label}
          </Typography>
        )}
      </Stack>
    </Stack>
  );

  return <Tooltip title={title ?? `${family.label}: ${value}`}>{chip}</Tooltip>;
}
