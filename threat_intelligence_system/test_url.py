"""
Quick URL tester -- edit the list below (or pass URLs on the command line)
and run:

    python test_url.py                                   # uses URLS_TO_TEST below
    python test_url.py https://a.com https://b.xyz       # test specific URLs
    python test_url.py --file urls.txt                   # one URL per line
    python test_url.py --no-intel                        # fast offline mode
    python test_url.py --json                            # also dump full JSON per URL

Results are printed to the console and saved to results/test_url_results.json
so you never have to copy anything by hand.
"""

import sys
sys.path.insert(0, ".")

import argparse
import json
from pathlib import Path

from src.prediction.predictor import PhishingPredictor

# ============================================================================
# 1. PUT YOUR URLS HERE (used when no URLs are given on the command line)
# ============================================================================
URLS_TO_TEST = [
    "https://www.telegrammessage.com/",
]
# ============================================================================


def print_result(result, show_json: bool = False) -> None:
    """Pretty-print one PredictionResult."""
    print("=" * 70)
    print(f"URL        : {result.url}")
    print(f"Prediction : {result.prediction.upper()}   ({result.risk_level} risk)")
    print(f"Risk Score : {result.risk_score}/100   |   Trust Score: {result.trust_score}/100")
    # Confidence = how sure the engine is about the predicted class.
    # Risk signals = how much danger each detector reported (0% = clean).
    print(f"Confidence : overall={result.confidence:.2%}  ml={result.ml_confidence:.2%}"
          + (f"  transformer={result.transformer_confidence:.2%}"
             if result.transformer_confidence is not None else ""))
    print(f"Risk signal: rules={result.rule_confidence:.2%}  "
          f"threat-intel={result.threat_intelligence_score:.2%}  "
          f"(0% = no threat indicators)")
    print(f"Versions   : model={result.model_version}  features={result.feature_version}  "
          f"dataset={result.dataset_version}  calibration={result.calibration_version}")

    # Decision breakdown (ensemble/hybrid contributions)
    bd = result.decision_breakdown
    if bd:
        print("\nDecision breakdown (how many of the {0} risk points "
              "each detector added):".format(result.risk_score))
        for key in ("ml_contribution", "rule_engine_contribution",
                    "threat_intelligence_contribution", "trust_score_contribution"):
            if key in bd:
                print(f"  {key.replace('_', ' '):<35}: {bd[key]:+.1f}")
        ens = bd.get("ensemble")
        if ens:
            print(f"  ensemble weights used              : "
                  f"{ {k: round(v, 2) for k, v in ens.get('weights_used', {}).items()} }")

    # SHAP explainability
    if result.top_shap_features:
        print("\nTop SHAP features (+ pushes phishing, - pushes legitimate):")
        for item in result.top_shap_features[:5]:
            print(f"  {item['feature']:<30} value={item['value']:<10.3f} "
                  f"contribution={item['contribution']:+.4f}")

    # Indicators
    for title, items in (
        ("Negative indicators (threat signals)", result.negative_indicators),
        ("Positive indicators (trust signals)", result.positive_indicators),
        ("Neutral indicators", result.neutral_indicators),
    ):
        if items:
            print(f"\n{title}:")
            for item in items:
                print(f"  - {item}")

    if result.reasons:
        print("\nReasons flagged:")
        for reason in result.reasons:
            print(f"  - {reason}")

    # Threat intelligence details
    intel = result.threat_intelligence
    print("\nThreat Intelligence Details:")
    if intel:
        if intel.get("virustotal_success"):
            print(f"  * VirusTotal: {intel.get('virustotal_positives', 0)}/"
                  f"{intel.get('virustotal_total_scanners', 0)} positive detections")
        else:
            print(f"  * VirusTotal: skipped/failed ({intel.get('virustotal_error', 'no API key')})")
        if intel.get("whois_success"):
            print(f"  * WHOIS: age={intel.get('whois_domain_age_days', '?')} days | "
                  f"registrar={intel.get('whois_registrar', 'N/A')} | "
                  f"country={intel.get('whois_registrant_country', 'N/A')}")
        else:
            print(f"  * WHOIS: failed ({intel.get('whois_error', 'N/A')})")
        if intel.get("ssl_success"):
            print(f"  * SSL: status={intel.get('ssl_ssl_status', 'UNKNOWN')} | "
                  f"expired={intel.get('ssl_is_expired', 'N/A')} | "
                  f"days_left={intel.get('ssl_days_until_expiry', 'N/A')}")
        else:
            print(f"  * SSL: failed ({intel.get('ssl_error', 'N/A')})")
        if intel.get("dns_success"):
            print(f"  * DNS: records={intel.get('dns_record_count', 0)} | "
                  f"SPF={intel.get('dns_has_spf', False)} | DMARC={intel.get('dns_has_dmarc', False)}")
        else:
            print(f"  * DNS: failed ({intel.get('dns_error', 'N/A')})")
        if intel.get("geoip_success"):
            print(f"  * GeoIP: {intel.get('geoip_ip_address', '?')} | "
                  f"{intel.get('geoip_city', 'N/A')}, {intel.get('geoip_country', 'N/A')} | "
                  f"ASN={intel.get('geoip_asn_org', 'N/A')}")
        else:
            print(f"  * GeoIP: failed ({intel.get('geoip_error', 'N/A')})")
    else:
        print("  (intelligence disabled -- run without --no-intel to enable)")

    if show_json:
        print("\nFull JSON:")
        print(result.to_json(indent=2))
    print("=" * 70 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick phishing URL tester.")
    parser.add_argument("urls", nargs="*", help="URLs to test (overrides the list in this file).")
    parser.add_argument("--file", help="Text file with one URL per line.")
    parser.add_argument("--no-intel", action="store_true",
                        help="Skip WHOIS/DNS/SSL/GeoIP/VirusTotal (much faster).")
    parser.add_argument("--json", action="store_true", help="Also print full JSON per URL.")
    parser.add_argument("--model", default="xgboost", help="Model type (default: xgboost).")
    parser.add_argument("--verbose", action="store_true", help="Show engine logs.")
    args = parser.parse_args()

    if not args.verbose:
        import logging
        logging.getLogger("phishing_engine").setLevel(logging.WARNING)

    urls = list(args.urls) or list(URLS_TO_TEST)
    if args.file:
        urls += [line.strip() for line in open(args.file, encoding="utf-8")
                 if line.strip() and not line.startswith("#")]
    if not urls:
        print("No URLs to test. Edit URLS_TO_TEST in this file or pass URLs as arguments.")
        return 1

    predictor = PhishingPredictor(
        model_type=args.model,
        use_intelligence=not args.no_intel,
    )

    results = []
    for url in urls:
        result = predictor.predict(url)
        print_result(result, show_json=args.json)
        results.append(result.to_dict())

    # Auto-save everything so nothing needs copying by hand
    out = Path("results") / "test_url_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)

    print(f"Tested {len(urls)} URL(s). Full results saved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
