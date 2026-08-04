"""Maps stored findings to the statutory provisions they engage.

A technical report tells an investigating officer what the evidence shows. It
does not tell them which law that engages, and in practice that translation is
done from memory by whoever writes the file - inconsistently, and invisibly.
This module makes it explicit and reviewable.

Design constraints, in order of importance:

1. **It never asserts an offence.** It reports that the evidence contains the
   features a provision describes. Intent, authorisation and identity are
   matters for investigation, and the caveat saying so travels with the output.
2. **Every entry names its basis.** A provision appears only with the concrete
   finding and the evidence ids behind it, so an officer - or a defence expert -
   can go and look.
3. **It is deterministic and rule-based.** Same input, same output, no model.
   Consistent with the rest of the scoring path.
4. **Silence is not "no offence".** Provisions outside the assessed set, and
   findings the engine cannot see, are stated as unassessed rather than absent.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

from backend.modules.evidence.logger import get_logger
from ciis_correlation.campaigns.models import CampaignAnalysis
from ciis_correlation.core.audit import InvestigationAuditTrail
from ciis_correlation.core.config import InvestigationConfig
from ciis_correlation.core.data_access import EvidenceContext
from ciis_correlation.correlation.models import CrossCaseCorrelation
from ciis_correlation.core.text import count_of, joined

from .models import EngagedProvision, LegalBasisAssessment
from .provisions import (
    ACT_JURISDICTION,
    ACT_LANGUAGE_NOTE,
    ACT_NEPALI_NAME,
    ACT_SHORT_NAME,
    ALL_PROVISIONS,
    ASSESSMENT_CAVEAT,
    COPYRIGHT_ACT,
    TRADEMARK_ACT,
    StatutoryProvision,
)

MODULE = "legal_basis"

#: Entity types that evidence a payment rail. A shared transaction id is the
#: same payment seen from both sides, so it counts alongside the account
#: identifiers themselves.
_PAYMENT_TYPES = frozenset({
    "wallets", "esewa_ids", "khalti_ids", "imepay_ids",
    "bank_accounts", "card_numbers", "transaction_ids",
    "eth_wallets", "btc_wallets",
})

#: Entity types that evidence credential handling.
_CREDENTIAL_TYPES = frozenset({"otp"})

#: Keywords that evidence credential handling in the text itself, for cases
#: where the extractor found no OTP entity but the message plainly asks for one.
#: Deliberately narrow: these are the words that name a secret, not words that
#: merely sound urgent.
_CREDENTIAL_WORDS = ("otp", "password", "pin", "cvv", "login", "security code")

#: Phrases in which a complainant describes losing access to their own account.
#: Drawn from the post-attack stage vocabulary the timeline already uses, so the
#: two modules read the same evidence the same way. Deliberately excludes
#: "scammed", "fraud" and "cheated" - those describe the loss of money, which is
#: s.52, not the loss of access, which is s.46.
_LOCKOUT_WORDS = (
    "blocked me", "locked out", "cannot login", "can't login",
    "cannot access", "account deleted", "deleted my", "lost access",
)


class LegalBasisService:
    """Statutory mapping over the findings of one case."""

    def __init__(
        self,
        config: InvestigationConfig,
        audit: Optional[InvestigationAuditTrail] = None,
    ) -> None:
        self._cfg = config
        self._audit = audit
        self._log = get_logger("investigation.legal")

    # ------------------------------------------------------------------ public

    def assess(
        self,
        case_id: str,
        items: Sequence[EvidenceContext],
        *,
        campaigns: Optional[CampaignAnalysis] = None,
        cross_case: Optional[CrossCaseCorrelation] = None,
        analytics: Any = None,
    ) -> LegalBasisAssessment:
        started = time.perf_counter()
        by_key = {(p.statute, p.section): p for p in ALL_PROVISIONS}
        eta = lambda section: by_key[(ACT_SHORT_NAME, section)]  # noqa: E731
        engaged: List[EngagedProvision] = []

        for build in (
            lambda: self._computer_fraud(eta("52"), items),
            lambda: self._illegal_publication(eta("47"), items, analytics),
            lambda: self._unauthorised_access(eta("45"), items),
            lambda: self._system_damage(eta("46"), items),
            lambda: self._abetment(eta("53"), campaigns),
            lambda: self._accomplice(eta("54"), campaigns),
            lambda: self._extraterritorial(eta("55"), cross_case),
            lambda: self._trademark(by_key[(TRADEMARK_ACT, "19")], items),
            lambda: self._copyright(by_key[(COPYRIGHT_ACT, "27")], items),
        ):
            try:
                found = build()
            except Exception as exc:  # noqa: BLE001 - one rule must not sink the section
                self._log.warning("legal rule failed for %s: %s", case_id, exc)
                continue
            if found is not None:
                engaged.append(found)

        # Confiscation is consequential: it applies because an offence is made
        # out, not because of anything separate in the evidence. So it is
        # evaluated last, against what the rules above actually found.
        if engaged:
            try:
                engaged.append(self._confiscation(eta("56"), engaged))
            except Exception as exc:  # noqa: BLE001
                self._log.warning("confiscation rule failed for %s: %s", case_id, exc)

        assessment = LegalBasisAssessment(
            case_id=case_id,
            statute=ACT_SHORT_NAME,
            statute_nepali=ACT_NEPALI_NAME,
            jurisdiction=ACT_JURISDICTION,
            language_note=ACT_LANGUAGE_NOTE,
            provisions=engaged,
            caveat=ASSESSMENT_CAVEAT,
            summary=self._summary(engaged),
            analysis_time_ms=round((time.perf_counter() - started) * 1000.0, 1),
        )
        if self._audit is not None:
            self._audit.record(
                case_id, MODULE, "assessed",
                f"{count_of(len(engaged), 'provision')} engaged",
                duration_ms=assessment.analysis_time_ms,
            )
        return assessment

    # ------------------------------------------------------------------- rules

    @staticmethod
    def _entities_of(items: Sequence[EvidenceContext], types) -> Dict[str, List[str]]:
        """``value -> evidence ids`` for the given entity types."""
        found: Dict[str, List[str]] = {}
        for context in items:
            for entity in context.entities:
                if entity.entity_type in types:
                    found.setdefault(entity.value, []).append(context.evidence_id)
        return found

    def _computer_fraud(
        self, provision: StatutoryProvision, items: Sequence[EvidenceContext]
    ) -> Optional[EngagedProvision]:
        """s.52 - a payment rail and a sum of money in the same case."""
        rails = self._entities_of(items, _PAYMENT_TYPES)
        money = self._entities_of(items, {"money"})
        if not rails or not money:
            return None
        rail_ids = sorted({eid for ids in rails.values() for eid in ids})
        basis = (
            f"{count_of(len(rails), 'payment identifier')} "
            f"({joined(sorted(rails)[:3])}) appear alongside "
            f"{count_of(len(money), 'money value')} "
            f"({joined(sorted(money)[:3])}) in the same case, evidencing a "
            "financial benefit moving through a payment rail."
        )
        return self._engaged(provision, basis, rail_ids)

    def _illegal_publication(
        self,
        provision: StatutoryProvision,
        items: Sequence[EvidenceContext],
        analytics: Any,
    ) -> Optional[EngagedProvision]:
        """s.47 - threat intelligence flagged published material as malicious."""
        stats = getattr(analytics, "threat_statistics", None) or {}
        if not stats.get("intel_available") or not stats.get("malicious_indicators"):
            return None
        web = self._entities_of(items, {"urls", "domains"})
        if not web:
            return None
        web_ids = sorted({eid for ids in web.values() for eid in ids})
        basis = (
            f"threat intelligence flagged "
            f"{count_of(int(stats['malicious_indicators']), 'indicator')} in this "
            f"case; the evidence carries {count_of(len(web), 'web address')} "
            f"({joined(sorted(web)[:2])}), i.e. material published in electronic form."
        )
        return self._engaged(provision, basis, web_ids)

    def _unauthorised_access(
        self, provision: StatutoryProvision, items: Sequence[EvidenceContext]
    ) -> Optional[EngagedProvision]:
        """s.45 - credential material present as an entity or in the text."""
        creds = self._entities_of(items, _CREDENTIAL_TYPES)
        ids = {eid for entity_ids in creds.values() for eid in entity_ids}
        words: List[str] = []
        for context in items:
            text = (context.raw_text or "").lower()
            hit = [w for w in _CREDENTIAL_WORDS if w in text]
            if hit:
                ids.add(context.evidence_id)
                words.extend(hit)
        if not ids:
            return None
        named = joined(sorted(set(list(creds) + words))[:4])
        basis = (
            f"credential material appears in {count_of(len(ids), 'evidence item')} "
            f"({named}), indicating access to an account was sought or obtained."
        )
        return self._engaged(provision, basis, sorted(ids))

    def _abetment(
        self, provision: StatutoryProvision, campaigns: Optional[CampaignAnalysis]
    ) -> Optional[EngagedProvision]:
        """s.53 - a campaign cluster implies coordination, not a lone act."""
        if campaigns is None or not campaigns.campaigns:
            return None
        largest = max(campaigns.campaigns, key=lambda c: len(c.members))
        if len(largest.members) < 2:
            return None
        basis = (
            f"campaign {largest.campaign_id} groups "
            f"{count_of(len(largest.members), 'evidence item')} by shared "
            "indicators, which evidences coordinated activity rather than a "
            "single isolated act."
        )
        return self._engaged(provision, basis, sorted(largest.members))

    def _extraterritorial(
        self, provision: StatutoryProvision, cross_case: Optional[CrossCaseCorrelation]
    ) -> Optional[EngagedProvision]:
        """s.55 - links beyond this case put locality in issue."""
        if cross_case is None or not getattr(cross_case, "link_count", 0):
            return None
        linked = [link.case_id for link in getattr(cross_case, "links", [])][:3]
        basis = (
            f"this case shares identifiers with "
            f"{count_of(cross_case.link_count, 'other case')}"
            + (f" ({joined(linked)})" if linked else "")
            + ". Where any part of the conduct occurred outside Nepal, the Act "
            "still applies to systems located in Nepal."
        )
        return self._engaged(provision, basis, [])

    def _system_damage(
        self, provision: StatutoryProvision, items: Sequence[EvidenceContext]
    ) -> Optional[EngagedProvision]:
        """s.46 - the complainant describes being locked out of an account.

        Inferential, and the basis says so. The signal is the victim's own
        words, not a technical observation, so the wording keeps that
        distinction visible rather than presenting it as established fact.
        """
        ids, phrases = set(), []
        for context in items:
            text = (context.raw_text or "").lower()
            hit = [w for w in _LOCKOUT_WORDS if w in text]
            if hit:
                ids.add(context.evidence_id)
                phrases.extend(hit)
        if not ids:
            return None
        basis = (
            f"the account given in {count_of(len(ids), 'evidence item')} "
            f"describes loss of access ({joined(sorted(set(phrases))[:3])}). "
            "This is the complainant's description, not a technical finding: "
            "whether information was in fact deleted, altered or made "
            "unusable is a matter for investigation."
        )
        return self._engaged(provision, basis, sorted(ids))

    def _accomplice(
        self, provision: StatutoryProvision, campaigns: Optional[CampaignAnalysis]
    ) -> Optional[EngagedProvision]:
        """s.54 - where activity is coordinated, liability may reach assistants.

        Distinct from s.53: abetment is procuring the offence, accomplice
        liability is assisting it, and the penalty is half the principal's.
        Both become live on the same finding, so both are reported.
        """
        if campaigns is None or not campaigns.campaigns:
            return None
        largest = max(campaigns.campaigns, key=lambda c: len(c.members))
        if len(largest.members) < 2:
            return None
        basis = (
            f"campaign {largest.campaign_id} evidences coordination across "
            f"{count_of(len(largest.members), 'evidence item')}. Where more "
            "than one person acted, anyone who assisted is liable to one half "
            "of the principal's punishment."
        )
        return self._engaged(provision, basis, sorted(largest.members))

    def _confiscation(
        self, provision: StatutoryProvision, engaged: Sequence[EngagedProvision]
    ) -> EngagedProvision:
        """s.56 - consequential on an offence under the Act being engaged.

        Practical value rather than legal novelty: it tells the officer that
        the devices used are within the confiscation power, which is a seizure
        decision they have to make early or not at all.
        """
        sections = sorted({p.section for p in engaged
                           if p.citation.endswith(f"{ACT_SHORT_NAME}")})
        basis = (
            "the findings engage "
            f"{count_of(len(sections), 'provision')} of the Act "
            f"({joined(['s.' + s for s in sections])}). Any computer, device "
            "or storage medium used to commit those acts falls within the "
            "confiscation power and should be identified for seizure."
        )
        return self._engaged(provision, basis, [])

    # ------------------------------------------------------------ intellectual

    @staticmethod
    def _detected_brands(items: Sequence[EvidenceContext]) -> Dict[str, List[str]]:
        """``brand -> evidence ids`` from the Phase-1 logo detector."""
        found: Dict[str, List[str]] = {}
        for context in items:
            report = context.forensics.get("logo_detections") or {}
            for detection in report.get("detections") or []:
                brand = str(detection.get("brand") or "").strip()
                if brand:
                    found.setdefault(brand, []).append(context.evidence_id)
        return found

    def _trademark(
        self, provision: StatutoryProvision, items: Sequence[EvidenceContext]
    ) -> Optional[EngagedProvision]:
        """Trade Mark Act s.19 - a registered mark used by someone who may not.

        This is the offence that the payment-wallet scams in scope actually
        commit twice over: the page carries eSewa's mark and eSewa did not
        publish it. Prosecuted separately from the Electronic Transactions Act,
        so an officer needs to be told about it separately.
        """
        brands = self._detected_brands(items)
        if not brands:
            return None
        ids = sorted({eid for eids in brands.values() for eid in eids})
        basis = (
            f"brand marks were detected in the evidence "
            f"({joined(sorted(brands))}) across "
            f"{count_of(len(ids), 'evidence item')}. Where the material was "
            "not published by the mark's owner, its use is unauthorised. "
            "Registration and authority are matters of record to be confirmed."
        )
        return self._engaged(provision, basis, ids)

    def _copyright(
        self, provision: StatutoryProvision, items: Sequence[EvidenceContext]
    ) -> Optional[EngagedProvision]:
        """Copyright Act s.27 - a brand's own assets reproduced, not just named.

        Narrower than the trade-mark rule on purpose. Naming a brand in text
        engages the mark; reproducing its logo engages copyright as well. The
        detector distinguishes the two, so this rule uses only the visual
        matches and stays silent when a brand was merely mentioned.
        """
        reproduced: Dict[str, List[str]] = {}
        for context in items:
            report = context.forensics.get("logo_detections") or {}
            for detection in report.get("detections") or []:
                method = str(detection.get("detection_method") or "")
                brand = str(detection.get("brand") or "").strip()
                if brand and "template" in method.lower():
                    reproduced.setdefault(brand, []).append(context.evidence_id)
        if not reproduced:
            return None
        ids = sorted({eid for eids in reproduced.values() for eid in eids})
        basis = (
            f"the visual assets of {joined(sorted(reproduced))} were matched "
            f"against reference artwork in {count_of(len(ids), 'evidence item')}, "
            "indicating the work was reproduced rather than merely named."
        )
        return self._engaged(provision, basis, ids)

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _engaged(
        provision: StatutoryProvision, basis: str, evidence_ids: List[str]
    ) -> EngagedProvision:
        return EngagedProvision(
            section=provision.section,
            title=provision.title,
            citation=provision.citation,
            conduct=provision.conduct,
            penalty=provision.penalty,
            basis=basis,
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def _summary(engaged: Sequence[EngagedProvision]) -> str:
        if not engaged:
            return (
                "No provision in the assessed set was engaged by the stored "
                "findings. This is not a conclusion that no offence occurred - "
                "it means the specific features this engine looks for are "
                "absent from the evidence held."
            )
        sections = ", ".join(f"s.{p.section}" for p in engaged)
        return (
            f"The findings engage {count_of(len(engaged), 'provision')} of the "
            f"{ACT_SHORT_NAME}: {sections}. Each is listed with the finding "
            "that engaged it and the evidence behind that finding."
        )
