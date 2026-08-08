"""Deterministic vector charts for the PDF investigation report.

Drawn with primitive ReportLab shapes rather than the ``graphics.charts``
classes. That is deliberate: this is an evidentiary document, so the same
input must produce the same marks on the page every time, and the chart
classes make their own decisions about axis ranges and tick placement that
shift as data changes. Every coordinate here is computed from the data.

Charts summarise; they never introduce a number. Each one is paired with the
table it summarises, so a reader who distrusts the picture can check the
figures immediately below it — and a greyscale print stays usable, because no
chart relies on colour alone to carry its meaning.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

try:  # reportlab is optional; the caller degrades to no charts.
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    _REPORTLAB = True
except ImportError:  # pragma: no cover - environment-dependent
    _REPORTLAB = False

#: Severity inks, matched to the on-screen palette so a printed report and the
#: web view agree about what "strong" looks like. Chosen for white paper.
BAND_COLORS = {
    "very_strong": "#b3261e",
    "strong": "#c2410c",
    "medium": "#a16207",
    "weak": "#4a5568",
    "critical": "#b3261e",
    "high": "#c2410c",
    "low": "#2b7a12",
    "good": "#1a7f5a",
    "bad": "#b3261e",
    "neutral": "#4a5568",
}

ACCENT = "#14532d"
MUTED = "#4a5568"
RULE = "#cbd5e0"
TRACK = "#edf2f7"

#: Full content width between the page margins (A4 less 18mm each side).
CONTENT_W = 174


def available() -> bool:
    return _REPORTLAB


def band_color(name: str) -> str:
    return BAND_COLORS.get(str(name).strip().lower().replace(" ", "_"), MUTED)


def _hex(value: str):
    return colors.HexColor(value)


def hbar_chart(
    rows: Sequence[Tuple[str, float, Optional[str]]],
    *,
    max_value: float = 100.0,
    width_mm: float = CONTENT_W,
    label_w_mm: float = 46.0,
    value_suffix: str = "",
    row_h: float = 12.0,
) -> Optional["Drawing"]:
    """Horizontal bars: ``(label, value, colour)`` per row, largest first.

    Used wherever the report ranks things — suspect confidence, correlation
    strength, OCR quality. The value is printed at the end of every bar, so
    the chart is never the only place a number appears.
    """
    if not _REPORTLAB or not rows:
        return None

    width = width_mm * mm
    label_w = label_w_mm * mm
    value_w = 20 * mm
    track_w = width - label_w - value_w
    height = len(rows) * row_h + 6

    d = Drawing(width, height)
    for i, (label, value, color) in enumerate(rows):
        y = height - (i + 1) * row_h
        safe = 0.0 if value is None else max(0.0, min(float(value), max_value))
        frac = safe / max_value if max_value else 0.0

        d.add(String(0, y + 3, _clip(str(label), 34), fontName="Helvetica",
                     fontSize=7, fillColor=_hex("#1f2937")))
        d.add(Rect(label_w, y, track_w, 7.5, fillColor=_hex(TRACK),
                   strokeColor=None))
        if frac > 0:
            d.add(Rect(label_w, y, max(1.2, track_w * frac), 7.5,
                       fillColor=_hex(color or ACCENT), strokeColor=None))
        d.add(String(label_w + track_w + 4, y + 3,
                     f"{_num(safe)}{value_suffix}", fontName="Helvetica-Bold",
                     fontSize=7, fillColor=_hex("#1f2937")))
    return d


def vbar_chart(
    rows: Sequence[Tuple[str, float, Optional[str]]],
    *,
    width_mm: float = CONTENT_W,
    height: float = 96.0,
) -> Optional["Drawing"]:
    """Vertical bars for a small distribution (counts per band).

    Counts are labelled above each bar rather than left to an axis, because a
    distribution in a report is read as "how many of each", not as a trend.
    """
    if not _REPORTLAB or not rows:
        return None

    width = width_mm * mm
    top_pad = 12.0
    base = 16.0
    peak = max((float(v or 0) for _, v, _ in rows), default=0.0)
    if peak <= 0:
        return None

    slot = width / len(rows)
    bar_w = min(slot * 0.5, 26.0)
    d = Drawing(width, height)
    d.add(Line(0, base, width, base, strokeColor=_hex(RULE), strokeWidth=0.5))

    for i, (label, value, color) in enumerate(rows):
        v = float(value or 0)
        h = (v / peak) * (height - base - top_pad)
        cx = i * slot + slot / 2
        if h > 0:
            d.add(Rect(cx - bar_w / 2, base, bar_w, h,
                       fillColor=_hex(color or ACCENT), strokeColor=None))
        d.add(String(cx, base + h + 3.5, _num(v), fontName="Helvetica-Bold",
                     fontSize=7.5, fillColor=_hex("#1f2937"),
                     textAnchor="middle"))
        d.add(String(cx, 6, _clip(str(label), 16), fontName="Helvetica",
                     fontSize=6.5, fillColor=_hex(MUTED), textAnchor="middle"))
    return d


def stacked_share_bar(
    segments: Sequence[Tuple[str, float, Optional[str]]],
    *,
    width_mm: float = CONTENT_W,
) -> Optional["Drawing"]:
    """One bar split into labelled proportions, with an inline legend.

    Preferred over a pie for a printed report: proportions along a common
    baseline are easier to compare than angles, and it survives being
    photocopied.
    """
    if not _REPORTLAB:
        return None
    total = sum(float(v or 0) for _, v, _ in segments)
    if total <= 0:
        return None

    width = width_mm * mm
    bar_h = 14.0
    d = Drawing(width, 40)
    x = 0.0
    for label, value, color in segments:
        v = float(value or 0)
        if v <= 0:
            continue
        seg_w = (v / total) * width
        d.add(Rect(x, 22, seg_w, bar_h, fillColor=_hex(color or ACCENT),
                   strokeColor=colors.white, strokeWidth=0.6))
        if seg_w > 22:
            d.add(String(x + seg_w / 2, 26.5, _num(v), fontName="Helvetica-Bold",
                         fontSize=7, fillColor=colors.white,
                         textAnchor="middle"))
        x += seg_w

    lx = 0.0
    for label, value, color in segments:
        if float(value or 0) <= 0:
            continue
        d.add(Rect(lx, 6, 6, 6, fillColor=_hex(color or ACCENT), strokeColor=None))
        text = f"{label} ({_num(float(value))})"
        d.add(String(lx + 9, 6.5, text, fontName="Helvetica", fontSize=6.5,
                     fillColor=_hex(MUTED)))
        lx += 9 + len(text) * 3.4 + 10
    return d


def timeline_strip(
    stages: Sequence[Tuple[str, Optional[int]]],
    *,
    width_mm: float = CONTENT_W,
) -> Optional["Drawing"]:
    """The attack's stage progression as a left-to-right ribbon.

    The order *is* the finding here, so the stages are drawn in sequence with
    arrow joins rather than listed. A stage's count is drawn only when the
    caller actually has one — passing ``None`` prints no caption rather than a
    misleading "0 events".
    """
    if not _REPORTLAB or not stages:
        return None

    width = width_mm * mm
    has_counts = any(c is not None for _, c in stages)
    height = 34.0 if has_counts else 28.0
    d = Drawing(width, height)
    gap = 10.0
    box_w = (width - gap * (len(stages) - 1)) / len(stages)
    box_h = 20.0 if has_counts else 15.0

    for i, (name, count) in enumerate(stages):
        x = i * (box_w + gap)
        # Deepening tint carries escalation without needing a second legend.
        shade = 0.10 + (i / max(1, len(stages) - 1)) * 0.30
        d.add(Rect(x, 8, box_w, box_h, fillColor=_hex(_tint(ACCENT, shade)),
                   strokeColor=_hex(ACCENT), strokeWidth=0.5))
        label_y = 19.0 if has_counts else 12.5
        d.add(String(x + box_w / 2, label_y, f"{i + 1}. {_clip(str(name), 22)}",
                     fontName="Helvetica-Bold", fontSize=6.8,
                     fillColor=_hex("#1f2937"), textAnchor="middle"))
        if count is not None:
            d.add(String(x + box_w / 2, 11.5,
                         f"{count} event{'' if count == 1 else 's'}",
                         fontName="Helvetica", fontSize=6.2,
                         fillColor=_hex(MUTED), textAnchor="middle"))
        if i < len(stages) - 1:
            ax = x + box_w + gap / 2
            d.add(Line(ax - 3, 18, ax + 3, 18, strokeColor=_hex(MUTED),
                       strokeWidth=0.8))
            d.add(Line(ax + 1, 20, ax + 3, 18, strokeColor=_hex(MUTED),
                       strokeWidth=0.8))
            d.add(Line(ax + 1, 16, ax + 3, 18, strokeColor=_hex(MUTED),
                       strokeWidth=0.8))
    return d


# ------------------------------------------------------------------ helpers
def _tint(hex_color: str, alpha: float) -> str:
    """Blend a colour toward white — a stand-in for alpha, which PDF fills lack."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * (1 - alpha))
    g = int(g + (255 - g) * (1 - alpha))
    b = int(b + (255 - b) * (1 - alpha))
    return f"#{r:02x}{g:02x}{b:02x}"


def _num(value: float) -> str:
    """Integers without a decimal tail; everything else to one place."""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.1f}"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
