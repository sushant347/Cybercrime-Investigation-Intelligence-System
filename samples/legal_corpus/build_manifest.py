#!/usr/bin/env python3
"""Record what is in the legal corpus and how much of it a machine can read.

Run this after adding or replacing a source document:

    python samples/legal_corpus/build_manifest.py

It writes ``manifest.json`` next to the documents. The point is not the file
listing - it is the *extractability* verdict per document, because that decides
what the engine is allowed to cite.

Nepali government instruments from this period are frequently typeset in legacy
non-Unicode fonts (Preeti, PCSNEPALI, Fontasy Himali). Those render as
Devanagari on screen but extract as Latin nonsense: the Act's own title comes
out as ``ljB'tLo sf/f]af/ P]g``. A transliteration table exists for Preeti, but
applying one to statutory text nobody on this project can proof-read would
produce citations that look right and are wrong - the exact failure this system
is built to avoid everywhere else. So those documents are marked unreadable and
the engine transcribes from the English text instead.

Requires PyMuPDF (``pymupdf``), already a platform dependency.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
DEVANAGARI = re.compile(r"[ऀ-ॿ]")

#: Fonts that encode Devanagari as Latin byte values. Text set in these cannot
#: be recovered by extraction alone.
LEGACY_NEPALI_FONTS = {"Preeti", "PCSNEPALI", "FONTASY_ HIMALI_ TT", "Kantipur"}

#: What the project actually does with each document. Anything not listed is
#: reference material - held for provenance, not consumed by code.
USED_BY = {
    "2.1 The Electronic Transactions Act, 2063 (2008).pdf": (
        "ciis_timeline_report.legal.provisions - sections 45, 47, 52, 53, 55 "
        "transcribed by hand (number, heading, penalty)"
    ),
}


def inspect(path: Path) -> dict:
    doc = fitz.open(path)
    pages = doc.page_count
    sample_pages = range(min(6, pages))
    text = "\n".join(doc[i].get_text() for i in sample_pages)

    fonts: set[str] = set()
    for i in range(min(4, pages)):
        for entry in doc[i].get_fonts(full=True):
            fonts.add(entry[3].split("+")[-1])

    legacy = sorted(LEGACY_NEPALI_FONTS & fonts)
    letters = sum(1 for c in text if c.isalpha())
    devanagari = len(DEVANAGARI.findall(text))
    ratio = devanagari / letters if letters else 0.0

    if legacy:
        readable, script, note = False, "nepali (legacy font)", (
            f"typeset in {', '.join(legacy)}; extracts as Latin, not Devanagari"
        )
    elif ratio > 0.5:
        readable, script, note = True, "nepali (unicode)", (
            "extracts as Unicode Devanagari, though some conjuncts are lossy"
        )
    elif devanagari:
        readable, script, note = True, "mixed", "Devanagari and Latin"
    else:
        readable, script, note = True, "latin", "extracts cleanly"

    return {
        "file": path.name,
        "pages": pages,
        "size_bytes": path.stat().st_size,
        "script": script,
        "machine_readable": readable,
        "devanagari_ratio": round(ratio, 3),
        "fonts": sorted(fonts)[:8],
        "note": note,
        "used_by": USED_BY.get(path.name, "reference only - not consumed by code"),
    }


def main() -> int:
    documents = []
    for path in sorted(HERE.iterdir()):
        if path.suffix.lower() == ".pdf":
            documents.append(inspect(path))
        elif path.suffix.lower() == ".docx":
            documents.append({
                "file": path.name,
                "pages": None,
                "size_bytes": path.stat().st_size,
                "script": "unknown (docx)",
                "machine_readable": True,
                "note": "Word document; not inspected by this script",
                "used_by": USED_BY.get(path.name,
                                       "reference only - not consumed by code"),
            })

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": (
            "Primary legal sources for the statutory-basis module. The engine "
            "transcribes provisions from these; it does not train on them and "
            "no model of any kind is fitted to this corpus."
        ),
        "statute_in_use": {
            "english": "Electronic Transactions Act, 2063 (2008)",
            "nepali": "विद्युतीय (इलेक्ट्रोनिक) कारोबार ऐन, २०६३",
            "jurisdiction": "Nepal",
            "note": (
                "The Nepali text is authoritative where it differs from the "
                "English translation. The engine transcribes from the English "
                "because the Nepali PDF is in a legacy font and cannot be "
                "extracted reliably - see machine_readable below."
            ),
        },
        "counts": {
            "documents": len(documents),
            "machine_readable": sum(1 for d in documents if d["machine_readable"]),
            "legacy_font_nepali": sum(
                1 for d in documents if d["script"] == "nepali (legacy font)"),
            "consumed_by_code": sum(
                1 for d in documents if d["used_by"] != "reference only - not consumed by code"),
        },
        "documents": documents,
    }

    out = HERE / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    c = manifest["counts"]
    print(f"wrote {out.relative_to(HERE.parent.parent)}")
    print(f"  {c['documents']} documents, {c['machine_readable']} machine-readable, "
          f"{c['legacy_font_nepali']} Nepali in legacy fonts, "
          f"{c['consumed_by_code']} consumed by code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
