"""
Dataset quality audit + curation (ML Improvement, step 1).

Audits data/processed/train.csv for duplicates, conflicting labels,
host-level label conflicts (noise), mislabeled well-known domains, class
balance and diversity. Writes results/dataset_quality_report.json and
produces data/processed/train_curated.csv:

  * exact duplicate URLs dropped
  * well-known official domains force-labelled legitimate
  * curated diversity URLs added (government, banking, cloud, universities,
    tech, social media, shopping, news) with www / path variants

Usage:  python dataset_quality_report.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

import pandas as pd

from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Curated legitimate domains by sector (diversity injection)
DIVERSITY_DOMAINS: dict[str, list[str]] = {
    "government": [
        "usa.gov", "irs.gov", "ssa.gov", "nasa.gov", "nih.gov", "cdc.gov",
        "gov.uk", "canada.ca", "europa.eu", "india.gov.in", "australia.gov.au",
        "bund.de", "service-public.fr", "gob.mx", "japan.go.jp",
    ],
    "banking": [
        "chase.com", "bankofamerica.com", "wellsfargo.com", "citibank.com",
        "capitalone.com", "usbank.com", "americanexpress.com", "discover.com",
        "hsbc.com", "barclays.co.uk", "santander.com", "ing.com", "bnpparibas.com",
        "deutsche-bank.de", "ubs.com", "goldmansachs.com", "morganstanley.com",
    ],
    "cloud": [
        "aws.amazon.com", "azure.microsoft.com", "cloud.google.com",
        "cloudflare.com", "digitalocean.com", "heroku.com", "oracle.com",
        "ibm.com", "salesforce.com", "vmware.com", "akamai.com", "fastly.com",
    ],
    "universities": [
        "mit.edu", "stanford.edu", "harvard.edu", "berkeley.edu", "cmu.edu",
        "ox.ac.uk", "cam.ac.uk", "ethz.ch", "u-tokyo.ac.jp", "tsinghua.edu.cn",
        "iitb.ac.in", "nus.edu.sg", "utoronto.ca", "unimelb.edu.au",
    ],
    "technology": [
        "google.com", "microsoft.com", "apple.com", "facebook.com", "github.com",
        "gitlab.com", "stackoverflow.com", "python.org", "mozilla.org",
        "adobe.com", "intel.com", "nvidia.com", "amd.com", "dell.com", "hp.com",
        "cisco.com", "redhat.com", "docker.com", "kubernetes.io", "openai.com",
    ],
    "social_media": [
        "twitter.com", "x.com", "instagram.com", "linkedin.com", "reddit.com",
        "youtube.com", "tiktok.com", "pinterest.com", "whatsapp.com",
        "telegram.org", "discord.com", "snapchat.com", "twitch.tv",
    ],
    "shopping": [
        "amazon.com", "ebay.com", "walmart.com", "target.com", "bestbuy.com",
        "costco.com", "etsy.com", "aliexpress.com", "shopify.com", "ikea.com",
        "homedepot.com", "wayfair.com", "zalando.de", "flipkart.com",
    ],
    "news": [
        "bbc.com", "cnn.com", "nytimes.com", "theguardian.com", "reuters.com",
        "apnews.com", "bloomberg.com", "wsj.com", "washingtonpost.com",
        "aljazeera.com", "lemonde.fr", "spiegel.de", "timesofindia.com",
    ],
}

# Common legitimate path patterns for URL variants
PATH_VARIANTS = ["", "/", "/about", "/contact", "/login", "/help", "/news",
                 "/products", "/search?q=info", "/index.html"]


def _host_series(urls: pd.Series) -> pd.Series:
    """Extract normalised hostnames from a URL series."""
    host = urls.astype(str).str.extract(r"://([^/]+)", expand=False)
    host = host.fillna(urls.astype(str).str.split("/").str[0])
    return host.str.replace(r"^www\.", "", regex=True).str.lower()


def build_diversity_urls() -> pd.DataFrame:
    """Generate curated legitimate URL variants across all sectors."""
    rows: list[dict] = []
    for sector, domains in DIVERSITY_DOMAINS.items():
        for domain in domains:
            for prefix in ("https://", "https://www."):
                # Skip double-www for subdomained entries like aws.amazon.com
                if prefix.endswith("www.") and domain.count(".") > 1:
                    continue
                for path in PATH_VARIANTS:
                    rows.append({
                        "url": f"{prefix}{domain}{path}",
                        "label": 0,
                        "sector": sector,
                    })
    df = pd.DataFrame(rows).drop_duplicates(subset="url")
    return df


def main() -> int:
    settings = get_settings()
    processed = settings.paths.processed_data_dir
    results_dir = settings.paths.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)

    train = pd.read_csv(processed / "train.csv")[["url", "label"]].dropna()
    n_original = len(train)

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(processed / "train.csv"),
        "original_rows": n_original,
    }

    # --- 1. Exact duplicates & conflicting labels -------------------------
    dup_mask = train.duplicated(subset="url", keep="first")
    conflicts = train.groupby("url")["label"].nunique()
    report["duplicate_urls"] = int(dup_mask.sum())
    report["conflicting_label_urls"] = int((conflicts > 1).sum())
    train = train[~dup_mask]

    # --- 2. Host-level label conflicts (noise indicator) ------------------
    hosts = _host_series(train["url"])
    host_labels = train.assign(host=hosts).groupby("host")["label"].nunique()
    noisy_hosts = host_labels[host_labels > 1]
    report["hosts_total"] = int(host_labels.size)
    report["hosts_with_both_labels"] = int(len(noisy_hosts))
    report["noisy_host_examples"] = noisy_hosts.head(15).index.tolist()

    # --- 3. Mislabeled well-known domains ----------------------------------
    official: set[str] = set()
    for domains in settings.threat.official_domains.values():
        official.update(d.lower() for d in domains)
    for domains in DIVERSITY_DOMAINS.values():
        official.update(d.lower() for d in domains)

    on_official = hosts.isin(official)
    mislabeled = train[on_official & (train["label"] == 1)]
    report["official_domain_rows"] = int(on_official.sum())
    report["official_domains_labeled_phishing"] = int(len(mislabeled))
    report["mislabeled_examples"] = mislabeled["url"].head(15).tolist()
    # Fix: official domains are legitimate by definition
    train.loc[on_official, "label"] = 0

    # --- 4. Class balance ---------------------------------------------------
    counts = train["label"].value_counts()
    report["class_balance"] = {
        "legitimate": int(counts.get(0, 0)),
        "phishing": int(counts.get(1, 0)),
        "ratio": round(float(counts.get(0, 0)) / max(1, int(counts.get(1, 0))), 3),
        "strategy": "scale_pos_weight during training (no rows discarded)",
    }

    # --- 5. Diversity injection ----------------------------------------------
    diversity = build_diversity_urls()
    new_rows = diversity[~diversity["url"].isin(set(train["url"]))]
    train = pd.concat(
        [train, new_rows[["url", "label"]]], ignore_index=True
    ).drop_duplicates(subset="url")
    report["diversity_urls_added"] = int(len(new_rows))
    report["diversity_sectors"] = {
        sector: len(domains) for sector, domains in DIVERSITY_DOMAINS.items()
    }

    # --- 6. Structural sanity metrics ---------------------------------------
    for label in (0, 1):
        sample = train[train["label"] == label]["url"].astype(str)
        if len(sample) > 30000:
            sample = sample.sample(30000, random_state=42)
        report[f"label{label}_https_share"] = round(
            float(sample.str.startswith("https").mean()), 4
        )
        report[f"label{label}_with_path_share"] = round(
            float((sample.str.count("/") > 2).mean()), 4
        )

    # --- Save ------------------------------------------------------------------
    curated_path = processed / "train_curated.csv"
    train.to_csv(curated_path, index=False)
    report["curated_rows"] = int(len(train))
    report["curated_file"] = str(curated_path)

    report_path = results_dir / "dataset_quality_report.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(json.dumps({k: v for k, v in report.items()
                      if not isinstance(v, list)}, indent=2))
    print(f"\nReport: {report_path}\nCurated dataset: {curated_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
