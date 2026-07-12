"""Chat-screenshot reconstruction from OCR bounding boxes (spatial, not regex).

When evidence looks like a messaging-app screenshot, this reconstructs the
conversation using the *geometry* of each detected text block rather than
fragile text patterns:

* messages are ordered top-to-bottom by their vertical position,
* left/right horizontal position infers sender side (incoming vs. "me"),
* short lines that are only a clock (``09:41``) are attached as timestamps,
* the original OCR text of every block is preserved verbatim.

The result is structured conversation metadata; it never alters OCR output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Mapping, Sequence

from .schemas import ChatMessage, ChatReconstruction

_TIME_ONLY = re.compile(r"^\s*\d{1,2}[:.]\d{2}(?:\s?[APap][Mm])?\s*$")
_APP_HINTS = {
    "whatsapp": ("whatsapp", "wa.me"),
    "messenger": ("messenger", "facebook"),
    "telegram": ("telegram", "t.me"),
}


@dataclass
class _Block:
    text: str
    x_left: float
    x_right: float
    y_top: float
    bbox: list


class ChatReconstructor:
    """Reconstructs conversation structure from spatial OCR layout."""

    def __init__(self, right_side_ratio: float = 0.55,
                 min_blocks_for_chat: int = 3) -> None:
        self._right_ratio = right_side_ratio
        self._min_blocks = min_blocks_for_chat

    def reconstruct(
        self,
        ocr_pages: Sequence[Mapping[str, Any]],
        image_width: int | None = None,
    ) -> ChatReconstruction:
        """Return structured conversation metadata (empty if not a chat)."""
        blocks = self._collect_blocks(ocr_pages)
        if len(blocks) < self._min_blocks:
            return ChatReconstruction()

        width = float(image_width) if image_width else max(
            (b.x_right for b in blocks), default=1.0) or 1.0
        blocks.sort(key=lambda b: b.y_top)  # message order = top -> bottom

        app_hint = self._app_hint(blocks)
        # Chat heuristic: some blocks lean right and some left (two-sided
        # bubbles), or an app hint is present.
        sides = [self._side(b, width) for b in blocks]
        two_sided = "left" in sides and "right" in sides
        is_chat = bool(app_hint) or two_sided
        if not is_chat:
            return ChatReconstruction()

        messages: List[ChatMessage] = []
        order = 0
        pending_ts = ""
        for block, side in zip(blocks, sides):
            if _TIME_ONLY.match(block.text):
                pending_ts = block.text.strip()
                # attach to the previous message if one exists
                if messages:
                    messages[-1].timestamp = pending_ts
                    pending_ts = ""
                continue
            order += 1
            messages.append(ChatMessage(
                order=order,
                sender="me" if side == "right" else "unknown",
                side=side,
                timestamp=pending_ts,
                text=block.text,
                bbox=block.bbox,
            ))
            pending_ts = ""
        return ChatReconstruction(
            is_chat_screenshot=True, app_hint=app_hint, messages=messages)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _collect_blocks(ocr_pages: Sequence[Mapping[str, Any]]) -> List[_Block]:
        blocks: List[_Block] = []
        for page in ocr_pages or []:
            for line in page.get("lines", []):
                bbox = line.get("bbox") or []
                text = str(line.get("text", "")).strip()
                if not text or not bbox:
                    continue
                xs = [float(p[0]) for p in bbox]
                ys = [float(p[1]) for p in bbox]
                blocks.append(_Block(text, min(xs), max(xs), min(ys), bbox))
        return blocks

    def _side(self, block: _Block, width: float) -> str:
        centre = (block.x_left + block.x_right) / 2.0
        if centre > width * self._right_ratio:
            return "right"
        if centre < width * (1 - self._right_ratio):
            return "left"
        return "unknown"

    @staticmethod
    def _app_hint(blocks: List[_Block]) -> str:
        joined = " ".join(b.text.lower() for b in blocks)
        for app, needles in _APP_HINTS.items():
            if any(n in joined for n in needles):
                return app
        return ""
