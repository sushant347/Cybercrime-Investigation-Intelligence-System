"""
Rule engine package for the Phishing URL Detection Engine.

Provides a deterministic, config-driven rule-based pre-filter that
runs before or alongside the ML model to flag obviously malicious URLs.
"""

from src.rules.rule_engine import RuleEngine, RuleResult, RuleFinding

__all__ = ["RuleEngine", "RuleResult", "RuleFinding"]
