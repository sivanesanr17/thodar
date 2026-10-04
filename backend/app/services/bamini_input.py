from __future__ import annotations

import re

from tamil.txt2unicode import bamini2unicode


_TAMIL_RANGE = range(0x0B80, 0x0C00)
_BAMINI_MARKERS = re.compile(r"[;{}\[\]\\$%&#*]")


def decode_bamini_if_present(text: str, font_name: str | None = None) -> str:
    """Convert detectable legacy Bamini PDF text to Unicode before translation."""
    if not text or any(ord(character) in _TAMIL_RANGE for character in text):
        return text

    decoded = bamini2unicode(text)
    tamil_letters = sum(ord(character) in _TAMIL_RANGE for character in decoded)
    if tamil_letters < 4:
        return text

    if font_name and "bamini" in font_name.casefold():
        return decoded

    source_letters = sum(character.isalpha() for character in text)
    decoded_letters = sum(character.isalpha() for character in decoded)
    tamil_ratio = tamil_letters / max(1, decoded_letters)
    marker_count = len(_BAMINI_MARKERS.findall(text))
    if source_letters >= 8 and tamil_ratio >= 0.65 and marker_count >= 2:
        return decoded

    return text
