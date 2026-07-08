"""Script to evaluate and verify the upgraded engine on official and suspicious lookalike domains."""
import sys
import os

# Ensure UTF-8 output on Windows for printing checkmarks and crosses
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

sys.path.insert(0, ".")

import pandas as pd
import numpy as np
from pathlib import Path
from src.prediction.predictor import PhishingPredictor
from src.utils.logger import get_logger

logger = get_logger(__name__)

def main():
    print("=" * 70)
    print("HYBRID DETECTION ENGINE VERIFICATION")
    print("=" * 70)

    # Initialize predictor (no external intelligence for fast local parsing/rules test)
    # This evaluates: ML model + Rules + Trust Score
    predictor = PhishingPredictor(model_type="xgboost", use_intelligence=False)

    test_urls = [
        # Legitimate official domains
        "https://www.facebook.com",
        "https://m.facebook.com",
        "https://google.com",
        "https://accounts.google.com",
        "https://github.com",
        "https://developer.github.com",
        "https://paypal.com",
        "https://amazon.com",
        "https://apple.com",
        "https://microsoft.com",
        "https://cloudflare.com",

        # Brand impersonation & phishing lookalikes
        "https://facebook-login.xyz",
        "https://facebook.com.evil.example",
        "https://google.com.evil.example",
        "https://paypal-login.net",
        "https://paypaI.com",  # Homograph capital I
        "https://xn--paypl-3ve.com",  # Punycode paypl
        "https://google-security-update.xyz",
        "https://github-authentication.ru",
        
        # Edge cases
        "https://192.168.1.10/login",
    ]

    results = []
    print(f"{'URL':<40} | {'Prediction':<12} | {'Risk':<5} | {'Trust':<5} | {'SSL':<7}")
    print("-" * 80)
    
    for url in test_urls:
        try:
            res = predictor.predict(url)
            print(f"{url:<40} | {res.prediction:<12} | {res.risk_score:<5} | {res.trust_score:<5} | {res.ssl_status:<7}")
            results.append(res)
        except Exception as e:
            print(f"Error predicting {url}: {e}")

    print("=" * 70)
    print("\nDetailed breakdown for facebook.com:")
    fb_res = [r for r in results if "www.facebook.com" in r.url]
    if fb_res:
        fb = fb_res[0]
        print(f"  Verdict: {fb.prediction}")
        print(f"  Risk Score: {fb.risk_score}/100")
        print(f"  Trust Score: {fb.trust_score}/100")
        print(f"  Positive Indicators: {fb.positive_indicators}")
        print(f"  Negative Indicators: {fb.negative_indicators}")
        print(f"  Neutral Indicators: {fb.neutral_indicators}")

    print("\nDetailed breakdown for facebook-login.xyz:")
    phish_res = [r for r in results if "facebook-login.xyz" in r.url]
    if phish_res:
        ph = phish_res[0]
        print(f"  Verdict: {ph.prediction}")
        print(f"  Risk Score: {ph.risk_score}/100")
        print(f"  Trust Score: {ph.trust_score}/100")
        print(f"  Positive Indicators: {ph.positive_indicators}")
        print(f"  Negative Indicators: {ph.negative_indicators}")
        print(f"  Neutral Indicators: {ph.neutral_indicators}")

if __name__ == "__main__":
    main()
