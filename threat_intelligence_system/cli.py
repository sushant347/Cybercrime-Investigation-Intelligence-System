#!/usr/bin/env python3
"""
Phishing URL Detection Engine — Command-Line Interface (v2.0)

Analyze URLs for phishing risk using a hybrid detection engine that combines:
  • 15 deterministic rule checks
  • ML-based prediction (XGBoost, LightGBM, etc.)
  • Threat intelligence (WHOIS, DNS, SSL, VirusTotal, GeoIP)
  • Explainable AI reasons

Usage
-----
Single URL:
    python cli.py https://paypal-login-security.xyz/login

Batch (comma-separated):
    python cli.py https://a.com,https://b.com

From file (one URL per line):
    python cli.py --file urls.txt

Save JSON report:
    python cli.py https://phishing.xyz --save-report

Disable intelligence / rules for speed:
    python cli.py https://example.com --no-intel --no-rules

Change model:
    python cli.py https://example.com --model random_forest
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# ANSI colour helpers (degrade gracefully on Windows / when piped)
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()

# Ensure UTF-8 output on Windows
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass  # Python < 3.7 fallback


def _colour(text: str, code: str) -> str:
    if not _IS_TTY:
        return text
    return f"\033[{code}m{text}\033[0m"


def red(t: str) -> str:    return _colour(t, "31")
def green(t: str) -> str:  return _colour(t, "32")
def yellow(t: str) -> str: return _colour(t, "33")
def cyan(t: str) -> str:   return _colour(t, "36")
def bold(t: str) -> str:   return _colour(t, "1")
def dim(t: str) -> str:    return _colour(t, "2")


_RISK_COLOURS = {
    "Critical": red,
    "High": red,
    "Medium": yellow,
    "Low": cyan,
    "Safe": green,
    "Unknown": dim,
}


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phishing-detect",
        description=textwrap.dedent("""\
            Hybrid Phishing URL Detection Engine v2.0
            ------------------------------------------
            Analyze one or more URLs for phishing risk using rules, ML,
            threat intelligence, and explainable AI.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python cli.py https://paypal-login-security.xyz/login
              python cli.py --file urls.txt --model xgboost --save-report
              python cli.py https://bit.ly/suspicious --no-intel --json
        """),
    )

    # Positional: URL(s)
    parser.add_argument(
        "urls",
        nargs="*",
        metavar="URL",
        help="One or more URLs to analyze (comma-separated lists allowed).",
    )

    # Input alternatives
    parser.add_argument(
        "--file", "-f",
        metavar="PATH",
        help="Path to a text file containing one URL per line.",
    )

    # Model selection
    parser.add_argument(
        "--model", "-m",
        default="xgboost",
        choices=[
            "logistic_regression", "random_forest", "decision_tree",
            "extra_trees", "naive_bayes", "svm", "xgboost", "lightgbm",
            "distilbert", "bert", "roberta",
        ],
        help="ML model to use for prediction (default: xgboost).",
    )

    # Behaviour flags
    parser.add_argument(
        "--no-intel",
        action="store_true",
        help="Disable external threat intelligence (WHOIS, DNS, SSL, VT).",
    )
    parser.add_argument(
        "--no-rules",
        action="store_true",
        help="Disable the deterministic rule engine.",
    )
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="Disable URL shortener resolution.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Enable optional model diagnostics mode.",
    )

    # Output options
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full results as JSON (machine-readable).",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save a structured JSON report to the results directory.",
    )
    parser.add_argument(
        "--report-dir",
        metavar="DIR",
        help="Directory to save reports to (default: results/).",
    )
    parser.add_argument(
        "--no-features",
        action="store_true",
        help="Exclude feature data from JSON output / saved reports.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Print only the verdict line (minimal output).",
    )

    return parser


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

def _risk_colour(risk_level: str) -> str:
    return _RISK_COLOURS.get(risk_level, dim)(risk_level)


def _print_result(result, quiet: bool = False) -> None:
    """Print a human-readable analysis result."""
    from src.prediction.result import PredictionResult

    risk_fn = _RISK_COLOURS.get(result.risk_level, dim)
    
    if result.is_phishing:
        prediction_text = bold(red("PHISHING"))
    elif result.is_suspicious:
        prediction_text = bold(yellow("SUSPICIOUS"))
    else:
        prediction_text = bold(green("LEGITIMATE"))

    if quiet:
        print(
            f"{prediction_text}  [{risk_fn(result.risk_level)}]  "
            f"score={result.risk_score}/100  "
            f"trust={result.trust_score}/100  "
            f"confidence={result.confidence:.0%}  "
            f"{result.url}"
        )
        return

    width = 72
    sep = dim("─" * width)

    print()
    print(bold(f"{'─' * width}"))
    print(bold(f"  Phishing URL Analysis"))
    print(bold(f"{'─' * width}"))
    print(f"  URL        : {cyan(result.url)}")

    # Resolved URL (if different from original)
    resolved_info = result.metadata.get("url_resolution", {})
    if result.metadata.get("original_url") and result.metadata["original_url"] != result.url:
        print(f"  Original   : {dim(result.metadata['original_url'])}")
    resolved_url = resolved_info.get("resolved_url")
    if resolved_url and resolved_url != result.url:
        print(f"  Resolved   : {cyan(resolved_url)}")

    # Trust Score color formatting
    trust_val = result.trust_score
    if trust_val >= 70:
        trust_text = green(f"{trust_val}/100")
    elif trust_val <= 30:
        trust_text = red(f"{trust_val}/100")
    else:
        trust_text = yellow(f"{trust_val}/100")

    print(f"  Verdict    : {prediction_text}")
    print(f"  Risk Level : {risk_fn(result.risk_level)}")
    print(f"  Risk Score : {risk_fn(str(result.risk_score))}/100")
    print(f"  Trust Score: {trust_text}")
    print(f"  Confidence : {result.confidence:.1%}")
    print(f"  Model      : {dim(result.model_type)}")
    print(f"  Timestamp  : {dim(result.analysis_timestamp)}")

    # Rule engine summary
    rule_data = result.metadata.get("rule_engine", {})
    if rule_data:
        findings = rule_data.get("findings", [])
        if findings:
            print()
            print(f"  {bold('Rule Engine')} ({len(findings)} finding(s)):")
            for finding in findings[:5]:  # Show top 5
                sev_fn = red if finding["severity"] in ("critical", "high") else yellow
                print(
                    f"    • [{sev_fn(finding['severity'].upper())}] "
                    f"{finding['rule_id']}"
                )
            if len(findings) > 5:
                print(f"    … and {len(findings) - 5} more")

    # Reasons
    if result.reasons:
        print()
        print(f"  {bold('Why flagged:')}")
        for i, reason in enumerate(result.reasons[:8], 1):
            wrapped = textwrap.fill(reason, width=66, initial_indent="", subsequent_indent=" " * 6)
            print(f"    {i}. {wrapped}")
        if len(result.reasons) > 8:
            print(f"    … and {len(result.reasons) - 8} more reasons")

    # Security Indicators (v2.0)
    if result.positive_indicators or result.negative_indicators or result.neutral_indicators:
        print()
        print(f"  {bold('Security Indicators:')}")
        for pos in result.positive_indicators[:5]:
            print(f"    {green(pos)}")
        for neg in result.negative_indicators[:5]:
            print(f"    {red(neg)}")
        for neu in result.neutral_indicators[:5]:
            # Use dim output for neutral indicators
            print(f"    {dim(neu)}")

    # Decision Breakdown (v2.0)
    print()
    print(f"  {bold('Decision Breakdown:')}")
    # ML Probability (using raw ML prediction if available)
    ml_pred = result.metadata.get("raw_ml_prediction", "phishing")
    ml_prob = result.ml_confidence
    print(f"    ML Probability       : {ml_prob:.0%} ({ml_pred.upper()})")
    
    # Rule Engine
    rule_score = result.rule_confidence
    rule_status = "Low Risk" if rule_score < 0.3 else "Medium Risk" if rule_score < 0.6 else "High Risk"
    print(f"    Rule Engine          : {rule_status} (score={rule_score:.2f})")
    
    # Threat Intelligence
    intel_success = result.threat_intelligence.get("whois_success", False) or result.threat_intelligence.get("dns_success", False)
    if not intel_success:
        intel_status = "No Data"
    else:
        vt_pos = result.threat_intelligence.get("virustotal_positives", 0)
        if vt_pos > 0:
            intel_status = red(f"Threat Detected ({vt_pos} VT detections)")
        else:
            intel_status = green("Trusted / Clean")
    print(f"    Threat Intelligence  : {intel_status}")
    
    # Trust Score
    print(f"    Trust Score          : {trust_text}")
    print(f"    Final Decision       : {prediction_text}")
    if result.reasons:
        print(f"    Reason               : {result.reasons[0]}")

    # Intelligence summary (brief)
    intel = result.threat_intelligence
    if intel:
        intel_lines = []
        age = intel.get("whois_domain_age_days")
        if age is not None:
            intel_lines.append(f"Domain age: {age} days")
        vt_pos = intel.get("virustotal_positives")
        vt_tot = intel.get("virustotal_total_scanners")
        if vt_pos is not None and vt_tot:
            intel_lines.append(f"VirusTotal: {vt_pos}/{vt_tot}")
        has_ssl = intel.get("ssl_has_ssl")
        if has_ssl is not None:
            # Handle unknown / boolean status safely
            ssl_str = "Yes" if has_ssl is True else "No" if has_ssl is False else str(has_ssl)
            intel_lines.append(f"SSL: {ssl_str}")
        if intel_lines:
            print()
            print(f"  {bold('Intelligence:')} {dim(' | '.join(intel_lines))}")

    print(sep)


def _print_batch_summary(results) -> None:
    """Print a summary table for batch analysis."""
    if not results:
        return

    n = len(results)
    phishing = sum(1 for r in results if r.is_phishing)
    high_risk = sum(1 for r in results if r.is_high_risk)
    avg_score = sum(r.risk_score for r in results) / n

    print()
    print(bold("═" * 72))
    print(bold(f"  BATCH SUMMARY  ({n} URLs analyzed)"))
    print(bold("═" * 72))
    print(f"  Phishing detected   : {red(str(phishing))} / {n}")
    print(f"  High-risk URLs      : {yellow(str(high_risk))} / {n}")
    print(f"  Average risk score  : {avg_score:.1f}/100")

    # Distribution
    for level in ("Critical", "High", "Medium", "Low", "Safe"):
        count = sum(1 for r in results if r.risk_level == level)
        if count:
            fn = _RISK_COLOURS.get(level, dim)
            bar = "█" * count
            print(f"  {level:<10}          : {fn(f'{count:3d} {bar}')}")

    print(bold("═" * 72))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument list (defaults to sys.argv).

    Returns:
        Exit code (0 = success, 1 = error, 2 = bad arguments).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Collect URLs
    urls: list[str] = []

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(red(f"Error: File not found: {file_path}"), file=sys.stderr)
            return 2
        urls.extend(
            line.strip()
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    for raw in args.urls:
        # Support comma-separated lists
        urls.extend(u.strip() for u in raw.split(",") if u.strip())

    if not urls:
        parser.print_help()
        return 2

    # Remove duplicates while preserving order
    seen: set[str] = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]

    print(
        dim(f"\nPhishing URL Detection Engine v2.0 — analyzing {len(urls)} URL(s)…\n")
    )

    # Initialize predictor
    try:
        from src.prediction.predictor import PhishingPredictor
        predictor = PhishingPredictor(
            model_type=args.model,
            use_intelligence=not args.no_intel,
            use_rules=not args.no_rules,
            resolve_shorteners=not args.no_resolve,
        )
    except Exception as exc:
        print(red(f"Error initializing engine: {exc}"), file=sys.stderr)
        return 1

    # Run analysis
    results = []
    for url in urls:
        try:
            result = predictor.predict(url, diagnostics=args.diagnostics)
            results.append(result)
            if args.json:
                print(result.to_json(indent=2 if not args.no_features else None))
            else:
                _print_result(result, quiet=args.quiet)
        except Exception as exc:
            print(red(f"Error analyzing {url}: {exc}"), file=sys.stderr)

    if not results:
        return 1

    # Batch summary (only for multi-URL, non-JSON output)
    if len(results) > 1 and not args.json and not args.quiet:
        _print_batch_summary(results)

    # Save report
    if args.save_report:
        try:
            from src.reporting.report_generator import ReportGenerator
            report_dir = Path(args.report_dir) if args.report_dir else None
            generator = ReportGenerator(output_dir=report_dir)

            if len(results) == 1:
                report, path = generator.generate_and_save(
                    results[0],
                    include_features=not args.no_features,
                )
            else:
                report, path = generator.generate_batch_and_save(
                    results,
                    include_features=not args.no_features,
                )

            print(green(f"\n✓ Report saved: {path}"))
            print(dim(f"  Report ID: {report.report_id}"))

        except Exception as exc:
            print(red(f"Error saving report: {exc}"), file=sys.stderr)

    # Return non-zero exit code if any URL is high-risk
    if any(r.is_high_risk for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
