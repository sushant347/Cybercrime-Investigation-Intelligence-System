"""Primary sources and non-offence guidance used by the legal assessment.

The Electronic Transactions Act and the NRB Cyber Resilience Guidelines do
different jobs.  The Act supplies statutory provisions and evidentiary rules;
the NRB document supplies supervisory expectations for licensed institutions.
Keeping the two catalogs separate prevents a regulatory follow-up from being
rendered as a criminal finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .models import LegalSourceReference


ETA_SOURCE_ID = "eta_2063"
NRB_CRG_SOURCE_ID = "nrb_crg_2023"

ETA_SOURCE_URL = "https://lawcommission.gov.np/content/13397/"
NRB_CRG_SOURCE_URL = (
    "https://www.nrb.org.np/contents/uploads/2023/08/"
    "Cyber-Resilience-Guidelines-2023.pdf"
)

NRB_CRG_NAME = "Nepal Rastra Bank Cyber Resilience Guidelines 2023"
NRB_APPLICABILITY = (
    "Conditional: confirm that the affected organisation is an institution "
    "within the Guidelines' scope, including an A, B, C or D class BFI, "
    "Payment System Operator or Payment Service Provider licensed by NRB's "
    "Payment Systems Department."
)


@dataclass(frozen=True)
class RegulatoryControl:
    """One official NRB expectation selected for investigative usefulness."""

    control_ids: Tuple[str, ...]
    title: str
    expectation: str
    recommended_action: str
    source_name: str = NRB_CRG_NAME
    citation_prefix: str = "Controls"

    @property
    def citation(self) -> str:
        controls = ", ".join(self.control_ids)
        return f"{self.citation_prefix} {controls}, {self.source_name}"


ELECTRONIC_RECORD_PRESERVATION = RegulatoryControl(
    control_ids=("4", "6"),
    title="Legal recognition and preservation of electronic records",
    expectation=(
        "Where the law requires a record to be retained, an electronic record "
        "is recognised when it remains accessible, can be reproduced in its "
        "original format, and retains available origin, destination, date and "
        "time information."
    ),
    recommended_action=(
        "Retain the original files, acquisition metadata, SHA-256 values and "
        "chain-of-custody history. A file hash supports integrity checking but "
        "is not by itself a statutory digital signature under ETA sections 3 "
        "and 5."
    ),
    source_name="Electronic Transactions Act, 2063 (2008)",
    citation_prefix="Sections",
)

NRB_AUTHENTICATION_CONTROL = RegulatoryControl(
    control_ids=("71(d)",),
    title="Preserve authentication and MFA records",
    expectation=(
        "Critical systems, processes and roles should require multi-factor "
        "authentication wherever supported, with enforced password-complexity "
        "requirements."
    ),
    recommended_action=(
        "Request the relevant login, MFA challenge, OTP delivery, account-change "
        "and access-control records from the institution for the incident window."
    ),
)

NRB_FORENSIC_LOG_CONTROL = RegulatoryControl(
    control_ids=("83", "84", "85", "86"),
    title="Preserve and correlate forensic logs",
    expectation=(
        "Detected events should be recorded with information such as event type, "
        "time and user or address; audit data should be protected, logs securely "
        "backed up, timestamps synchronised, and events centralised and "
        "correlated across relevant systems."
    ),
    recommended_action=(
        "Send a preservation request for transaction, authentication, application, "
        "system and network logs, including timezone and clock-synchronisation "
        "details, before normal retention or rotation removes them."
    ),
)


def primary_sources(*, include_nrb: bool) -> list[LegalSourceReference]:
    """Return the exact source records that contributed to an assessment."""

    sources = [
        LegalSourceReference(
            source_id=ETA_SOURCE_ID,
            authority="Nepal Law Commission",
            title="Electronic Transactions Act, 2063 (2008)",
            url=ETA_SOURCE_URL,
            local_documents=[
                "2.1 The Electronic Transactions Act, 2063 (2008).pdf",
                "2.1 विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३ (नेपाली).pdf",
            ],
            sha256={
                "2.1 The Electronic Transactions Act, 2063 (2008).pdf": (
                    "7f68a8b66adf579b5ba595f9062abcd8c61f9fddfaadffe06c8e4b752d76b4b6"
                ),
                "2.1 विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३ (नेपाली).pdf": (
                    "5b5cd8d72da9da73d6932ea227ec79cb65e19d5ca1ef3aa6f02f3dcef76bc723"
                ),
            },
            usage=(
                "Statutory offence mapping and electronic-record preservation "
                "guidance."
            ),
            note=(
                "The Nepali text is authoritative where it differs from the "
                "English translation."
            ),
        )
    ]
    if include_nrb:
        sources.append(
            LegalSourceReference(
                source_id=NRB_CRG_SOURCE_ID,
                authority="Nepal Rastra Bank, Payment Systems Department",
                title=NRB_CRG_NAME,
                url=NRB_CRG_SOURCE_URL,
                local_documents=["4.5 NRB Cyber-Resilience-Guidelines-2023.pdf"],
                sha256={
                    "4.5 NRB Cyber-Resilience-Guidelines-2023.pdf": (
                        "191eaea1bdb20cf4c50374d6173d0c1ee4476ae4145e6e1309ea26e097c7a8ff"
                    )
                },
                usage=(
                    "Conditional investigative follow-up for authentication and "
                    "forensic logging; never used as an offence finding."
                ),
                note=(
                    "Repository copy verified byte-for-byte against the official "
                    "NRB download. Applicability to the affected institution must "
                    "be confirmed by the investigator."
                ),
            )
        )
    return sources
