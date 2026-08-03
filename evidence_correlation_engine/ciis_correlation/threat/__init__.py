"""Threat-intelligence providers feeding the correlation engine.

Two implementations behind one duck-typed interface
(``available`` / ``lookup`` / ``is_malicious``):

* :mod:`.heuristics`  - offline, explainable URL/domain heuristics; always available
* :mod:`.ml_provider` - adapter over the standalone ``threat_intelligence_system``
  phishing classifier, imported lazily so its heavy ML stack (which needs its
  own virtualenv) never loads unless a lookup actually needs it

Both are optional: the pipeline degrades to the static indicator file, and then
to no threat factor at all, without failing an analysis.
"""

from .heuristics import ChainedThreatIntelProvider, HeuristicThreatIntelProvider

__all__ = ["ChainedThreatIntelProvider", "HeuristicThreatIntelProvider"]
