# Brand Intelligence Engine

Production-quality brand-impersonation detection added to the existing Threat
Intelligence System **without any breaking changes**. The predictor, ML models,
training pipeline, feature extraction, SHAP explainability, threat-intelligence
connectors, risk scoring, CLI, JSON outputs, checkpoints and existing tests are
all untouched — the engine plugs in additively through the Rule Engine.

## Components

| File | Purpose |
|---|---|
| `config/brand_intelligence.yaml` | Maintainable official-domain database + scoring config (edit brands with no code changes) |
| `src/intelligence/brand_intelligence.py` | `BrandIntelligenceEngine` — offline, explainable analysis |
| `src/rules/rule_engine.py` | Six additive brand rules (existing rules unchanged) |
| `tests/test_brand_intelligence.py` | 69 tests covering every requirement |

## What it detects

1. **Registrable-domain comparison (PSL).** Hostnames are reduced to their
   registrable domain via the Public Suffix List before comparison, never
   compared raw: `login.microsoft.com → microsoft.com` (official),
   `secure-login-paypal.com` and `edge-origin-whatsapp.com.cn` stay themselves
   (not official).
2. **Brand token detection** in hostname, subdomain, path and query.
3. **Official-domain verification.** A referenced brand is trusted only when the
   registrable domain is in that brand's official list; otherwise an
   `official_domain_mismatch` finding is raised and brand risk increases.
4. **Typosquatting** — Damerau-Levenshtein distance, leetspeak (`paypa1`,
   `micros0ft`, `g00gle`), multi-char visual confusions (`arnazon` rn→m),
   keyboard-adjacent slips, repeated/missing/extra characters (`whatsaap`,
   `facbook`, `payypal`).
5. **Homoglyph / Unicode spoofing** — NFKC normalisation plus a Cyrillic/Greek
   confusables map (`раypal`, `gοοgle`, `microsоft`). Genuine IDNs are not flagged.
6. **Prefix / suffix abuse** — `secure-google`, `verify-paypal`, `apple-support`,
   `microsoft-security`, `nabil-bank-login`.
7. **Cloud-hosting impersonation** — GitHub Pages, Firebase, Netlify, Vercel,
   S3, Azure Blob, Cloudflare Pages, Render, Railway, etc. Cloud providers are
   **never** malicious by themselves; suspicion rises only when a brand
   mismatch is combined with credential-collection signals (login/password
   forms). Reuses the existing `CloudHostingDetector` via dependency injection.
8. **Configurable Brand Risk Score** — a weighted combination of official-domain
   mismatch, brand token, typosquatting, homoglyph, prefix/suffix and
   cloud-hosting signals, optionally amplified by external context (domain age,
   SSL validity, WHOIS privacy, suspicious-keyword count). All weights and
   thresholds live in the YAML.
9. **Explainability** — every finding carries a human-readable reason, e.g.
   *"Brand 'WhatsApp' referenced in hostname, but registrable domain
   'edge-origin-whatsapp.com.cn' does not belong to the official WhatsApp
   infrastructure."*

## Official domain database

Global brands (Microsoft, Google, Apple, Meta, Facebook, Instagram, WhatsApp,
Amazon, PayPal, Netflix, Telegram, Discord, GitHub, Dropbox, Adobe, LinkedIn,
X/Twitter, Cloudflare, OpenAI) plus Nepal-specific coverage: eSewa, Khalti,
IME Pay, ConnectIPS, Fonepay, Nagarik App, Government of Nepal (`gov.np` /
`mil.np` suffixes), and 20 major Nepali banks. 45 protected brands total.

Add or edit a brand by appending to `config/brand_intelligence.yaml`:

```yaml
brands:
  my_bank:
    display_name: My Bank
    tokens: [mybank]
    official_domains: [mybank.com.np]
```

## Rule Engine integration (additive)

`RuleEngine.__init__` accepts an optional injected `BrandIntelligenceEngine`
(default is created lazily; a failing engine degrades to no-ops). A new
`_rule_brand_intelligence` step runs alongside the existing rules and emits:

| Rule ID | Trigger |
|---|---|
| `bi_official_domain_mismatch` | Brand referenced, registrable domain not official |
| `bi_typosquatting` | Domain label within edit distance of a brand |
| `bi_unicode_spoofing` | Homoglyph substitution of a brand |
| `bi_brand_impersonation` | Misleading affix + brand combination |
| `bi_fake_login_infrastructure` | Brand mismatch + credential signals in the URL |
| `bi_cloud_hosted_impersonation` | Brand mismatch + credentials on cloud hosting |

These findings appear in the existing `rule_engine` block of the prediction
JSON (new rule IDs, same structure) and contribute to the existing rule score
and hybrid decision — no output schema change.

## SHAP / feature-version decision (deliberately no retraining)

Per the requirement to *not* retrain automatically and to preserve feature
compatibility, the numeric ML feature vector (71 features, feature version
2.0.0) is **left unchanged** — adding numeric features would invalidate the
existing checkpoints. The engine's rich signals are exposed additively as
Rule Engine findings and the brand-intelligence result object instead.

**If** these brand signals are later wanted as first-class ML features, that is
a deliberate, documented retraining step: add them to `BrandFeatureExtractor`,
bump `FEATURE_VERSION`, and run `train_from_datasets.py`. It is intentionally
not performed here.

## Backward compatibility

- Existing feature count unchanged (71); prediction JSON keys unchanged (33).
- No checkpoint, model, predictor, or feature-extraction file modified.
- Full test suite: **379 passed, 1 skipped (pre-existing), 0 failures**,
  including 69 new brand-intelligence tests.

## Brand Conflict Detection (additive enhancement)

A trusted registrable domain that references a **different** protected brand is
now flagged as a *Brand Conflict*, even though the domain itself is legitimate.
This closes a gap where fully-trusted domains (e.g. `github.io`) were returned
with zero risk regardless of their path/query.

**Trigger:** the registrable domain belongs to a trusted organisation — either
an official protected-brand domain (`github.io` → GitHub) or a recognised cloud
provider (`firebaseapp.com`, `netlify.app`, `vercel.app`) — **and** a different
protected brand token appears in the hostname, subdomain, path or query.

| URL | Domain owner | Referenced brand | Result |
|---|---|---|---|
| `github.io/microsoft-login` | GitHub (official) | Microsoft | Brand Conflict (medium) |
| `github.io/paypal-login` | GitHub (official) | PayPal | Brand Conflict (medium) |
| `microsoft-verify.github.io/account` | GitHub (official) | Microsoft | Brand Conflict (high, domain-level) |
| `firebaseapp.com/google-login` | Firebase (cloud) | Google | Brand Conflict (medium) |
| `netlify.app/facebook-auth` | Netlify (cloud) | Facebook | Brand Conflict (medium) |
| `vercel.app/appleid` | Vercel (cloud) | Apple | Brand Conflict (medium) |

**Not phishing by itself.** The conflict raises the Brand Risk Score and adds a
`bi_brand_conflict` finding (severity *high*, never *critical*) to the Rule
Engine, increasing the rule score. The **final verdict still depends on the
existing ML model, Threat Intelligence and Risk Fusion** — the conflict never
forces a definite-phishing classification.

**Explainable warnings**, e.g.:
> Protected brand 'Microsoft' detected inside the URL (path), but the
> registrable domain 'github.io' belongs to GitHub. The URL references a
> different trusted organisation than the domain owner — possible brand
> impersonation or deceptive content.

**False-positive protection.** A token belonging to the domain owner itself is
never a conflict: `github.com`, `web.whatsapp.com`, `support.apple.com`,
`accounts.google.com`, `login.microsoft.com` and `outlook.office365.com`
(Microsoft alias on a Microsoft domain) all stay fully trusted (risk `none`).

**Scoring.** Configurable via `config/brand_intelligence.yaml`
(`scoring.weights.brand_conflict`, default 0.35). Domain-level conflicts
(hostname/subdomain) carry additional weight over path/query references.

**Rule:** `bi_brand_conflict` — added to the existing Rule Engine mapping; all
other rules, the ML model, feature schema (71 features, v2.0.0), checkpoints and
JSON outputs are unchanged. No retraining performed.
