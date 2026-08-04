"""Statutory provisions of the Electronic Transactions Act, 2063 (2008), Nepal.

Transcribed from the Act as published (``samples/legal_corpus/`` holds the
source PDFs and a manifest recording which of them a machine can read).
Only the provisions this engine can reason about from stored findings are
listed - the Act contains many more, and their absence here means "not
automatically assessed", never "not applicable".

Each entry records the section number, its heading as enacted, the penalty as
written, and - separately - the *finding* that engages it. Keeping the law and
the trigger apart matters: the law is fixed text that must never be paraphrased
into something it does not say, while the trigger is this engine's editorial
judgement about when a finding is relevant, and is open to challenge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class StatutoryProvision:
    """One section of the Act, with the condition this engine maps to it."""

    #: Section number as enacted, e.g. ``"52"``.
    section: str
    #: Heading exactly as it appears in the Act.
    title: str
    #: Penalty as written. Quoted, never summarised into a different figure.
    penalty: str
    #: What the Act prohibits, in the Act's own terms, condensed for a reader.
    conduct: str
    #: Why this engine considers the finding relevant. Editorial, not statutory.
    trigger: str
    #: Which statute the section belongs to. Defaults to the Act most of these
    #: come from, so existing entries did not have to be rewritten.
    statute: str = "Electronic Transactions Act, 2063 (2008)"

    @property
    def citation(self) -> str:
        return f"Section {self.section}, {self.statute}"


ACT_SHORT_NAME = "Electronic Transactions Act, 2063 (2008)"

#: The Act's title in Nepali. Reproduced so a report filed with a Nepali court
#: or police unit names the instrument as it is named in law.
#:
#: Taken from the filename of the Nepali gazette copy in
#: ``samples/legal_corpus/``, which is proper Unicode - the *contents* of that
#: PDF are typeset in a legacy Preeti/PCSNEPALI font and extract as Latin
#: nonsense, so nothing else in this file can be sourced from the Nepali text.
#: Section headings therefore appear in English only; see the corpus manifest.
ACT_NEPALI_NAME = "विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३"

ACT_JURISDICTION = "Nepal"

#: Where the Nepali text sits relative to the English one, in law.
ACT_LANGUAGE_NOTE = (
    "Cited from the English text of the Act. The Nepali text is authoritative "
    "where the two differ; verify any provision against "
    f"{ACT_NEPALI_NAME} before relying on it in a filing."
)

#: Provisions assessed automatically. Ordered by how directly a typical
#: online-fraud case engages them.
PROVISIONS: Tuple[StatutoryProvision, ...] = (
    StatutoryProvision(
        section="52",
        title="To commit computer fraud",
        penalty=(
            "fine not exceeding one hundred thousand Rupees or imprisonment "
            "not exceeding two years or both"
        ),
        conduct=(
            "Acquiring a financial benefit by fraud through a computer, "
            "including from the payment of any bill, the balance of another "
            "person's account, or an ATM card. The amount obtained is "
            "recoverable."
        ),
        trigger=(
            "payment-rail identifiers (wallet, bank account, card or "
            "transaction id) appear in the evidence together with a money value"
        ),
    ),
    StatutoryProvision(
        section="47",
        title="Publication of illegal materials in electronic form",
        penalty=(
            "fine not exceeding one hundred thousand Rupees or imprisonment "
            "not exceeding five years or both"
        ),
        conduct=(
            "Publishing or displaying material in electronic media, including "
            "on the internet, which is prohibited by prevailing law or is "
            "contrary to public morality or decent behaviour."
        ),
        trigger=(
            "threat intelligence flags a URL or domain present in the evidence "
            "as malicious"
        ),
    ),
    StatutoryProvision(
        section="45",
        title="Unauthorized Access in Computer Materials",
        penalty=(
            "fine not exceeding two hundred thousand Rupees or imprisonment "
            "not exceeding three years or both"
        ),
        conduct=(
            "Accessing any programme, information or data of a computer "
            "without the authorisation of its owner, or beyond the scope of "
            "an authorisation held."
        ),
        trigger=(
            "credential material (OTP, password, PIN or login data) appears in "
            "the evidence, indicating access was sought or obtained"
        ),
    ),
    StatutoryProvision(
        section="53",
        title="Punishment to the person who abets to commit computer related offence",
        penalty=(
            "fine not exceeding fifty thousand Rupees or imprisonment not "
            "exceeding six months or both, depending on the degree of the offence"
        ),
        conduct=(
            "Abetting another to commit an offence under the Act, or attempting "
            "or being involved in a conspiracy to commit one."
        ),
        trigger=(
            "a campaign cluster groups two or more evidence items, indicating "
            "coordinated rather than isolated activity"
        ),
    ),
    StatutoryProvision(
        section="55",
        title="Punishment in an offence committed outside Nepal",
        penalty="as for the underlying offence",
        conduct=(
            "An offence under the Act involving a computer, computer system or "
            "network located in Nepal may be prosecuted even where the act was "
            "committed by a person residing outside Nepal."
        ),
        trigger=(
            "the case is linked to another case, or infrastructure indicators "
            "suggest the acts were not confined to a single locality"
        ),
    ),
    StatutoryProvision(
        section="46",
        title="Damage to any Computer and Information System",
        penalty=(
            "fine not exceeding two thousand Rupees and imprisonment not "
            "exceeding three years or both"
        ),
        conduct=(
            "Knowingly and with mala fide intention destroying, damaging, "
            "deleting, altering or disrupting information of any computer "
            "source, or diminishing its value and utility."
        ),
        trigger=(
            "the complainant's own account describes losing access to an "
            "account - being blocked, locked out or deleted"
        ),
    ),
    StatutoryProvision(
        section="54",
        title="Punishment to the Accomplice",
        penalty="one half of the punishment for which the principal is liable",
        conduct=(
            "Assisting another to commit an offence under the Act, or acting "
            "as an accomplice by any means."
        ),
        trigger=(
            "coordinated activity is evidenced, so liability may extend beyond "
            "the principal to anyone who assisted"
        ),
    ),
    StatutoryProvision(
        section="56",
        title="Confiscation",
        penalty=(
            "confiscation of the computer, computer system, disks, software or "
            "other accessory devices used"
        ),
        conduct=(
            "Any computer, computer system, disk, software or accessory device "
            "used to commit an offence relating to computer under the Act is "
            "liable to confiscation."
        ),
        trigger=(
            "at least one offence provision of the Act is engaged, so the "
            "devices used to commit it fall within the confiscation power"
        ),
    ),
)

# ---------------------------------------------------------------------------
# Intellectual property
#
# Brand impersonation is the defining feature of the payment-wallet scams this
# system was built for: a page that says eSewa, carrying eSewa's mark, that
# eSewa did not publish. That is an offence under the Electronic Transactions
# Act (s.47, publication) *and* under trade-mark law, and the two are
# prosecuted separately. Leaving the second out meant an officer holding a
# clear case of mark misuse was never told so.
# ---------------------------------------------------------------------------

TRADEMARK_ACT = "Patent, Design and Trade Mark Act, 2022 (1965)"
COPYRIGHT_ACT = "Copyright Act, 2059 (2002)"

IP_PROVISIONS: Tuple[StatutoryProvision, ...] = (
    StatutoryProvision(
        statute=TRADEMARK_ACT,
        section="19",
        title="Punishment for illegal use of trade-marks",
        penalty=(
            "fine not exceeding one hundred thousand Rupees, and confiscation "
            "of articles and goods connected with the offence, as per its gravity"
        ),
        conduct=(
            "Using a trade-mark that is not registered to the user, using one "
            "whose registration has been cancelled, or otherwise using a "
            "registered mark without authority (s.18B)."
        ),
        trigger=(
            "logo or brand detection identifies a registered brand's mark in "
            "evidence that the brand did not publish"
        ),
    ),
    StatutoryProvision(
        statute=COPYRIGHT_ACT,
        section="27",
        title="Punishment on infringement of protected right",
        penalty=(
            "fine of ten thousand to one hundred thousand Rupees or "
            "imprisonment not exceeding six months or both; higher on repeat. "
            "Materials reproduced or distributed, and devices used to reproduce "
            "them, shall be seized"
        ),
        conduct=(
            "Infringing a protected right under s.25 - reproducing a work, or "
            "advertising or publicising by copying a work, without the "
            "authorisation of the author or copyright owner."
        ),
        trigger=(
            "a brand's visual assets were matched against reference artwork, "
            "i.e. the work was copied rather than merely named. DORMANT BY "
            "DEFAULT: this needs template matching, which only runs once an "
            "investigator places reference logos in "
            "storage/forensics/logo_templates/<brand>/. Without them the "
            "detector reports keyword and colour matches only, which evidence "
            "use of the mark (trade-mark s.19) but not reproduction of the work."
        ),
    ),
)

#: Every provision the engine can assess, across all statutes.
ALL_PROVISIONS: Tuple[StatutoryProvision, ...] = PROVISIONS + IP_PROVISIONS

#: Offence sections of the Electronic Transactions Act that are deliberately
#: *not* assessed, and why. Recorded so their absence reads as a scoping
#: decision rather than an oversight - and so anyone extending this module can
#: see which gaps need a new signal rather than a new rule.
UNASSESSED_ETA_SECTIONS = {
    "44": "no signal - nothing in the evidence indicates source-code tampering",
    "48": ("requires a person holding authorised access who divulged it; the "
           "evidence does not establish authorisation"),
    "49": "concerns false statements to a Certifying Authority about digital signatures",
    "50": "concerns operating as an unlicensed Certifying Authority",
    "51": "concerns failure to submit statements to the Controller",
    "57": ("requires identifying a corporate body; no organisation entity is "
           "extracted from evidence"),
    "58": "residual penalty for violations with no specific punishment",
}

#: Wording that must accompany any automated statutory assessment. The engine
#: identifies which provisions the *findings* engage; whether an offence is
#: made out, and whether to charge, is for the investigating officer and the
#: prosecutor.
ASSESSMENT_CAVEAT = (
    "This is an automated mapping from technical findings to statutory "
    "provisions, provided to assist the investigating officer. It is not legal "
    "advice and not a charging decision. A provision is listed because the "
    "evidence contains the features described, not because an offence has been "
    "proved: intent, authorisation and identity are matters for investigation. "
    "Provisions of the Act not listed here were not assessed."
)
