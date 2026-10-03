from __future__ import annotations

import re
import unicodedata


# Unicode-to-Bamini character sequences follow the published mappings in the
# MIT-licensed converter at github.com/Pakeetharan/unicode-bamini-converter.
_VOWEL_SIGNS = ("ௌ", "ோ", "ொ", "ா", "ி", "ீ", "ு", "ூ", "ெ", "ே", "ை", "்", "")
_CONSONANTS: dict[str, tuple[str, ...]] = {
    "க": ("nfs", "Nfh", "nfh", "fh", "fp", "fP", "F", "$", "nf", "Nf", "if", "f;", "f"),
    "ங": ("nqs", "Nqh", "nqh", "qh", "qp", "qP", "*", "*", "nq", "Nq", "iq", "q;", "q"),
    "ச": ("nrs", "Nrh", "nrh", "rh", "rp", "rP", "R", "R+", "nr", "Nr", "ir", "r;", "r"),
    "ஞ": ("nQs", "NQh", "nQh", "Qh", "Qp", "QP", "*", "*", "nQ", "NQ", "iQ", "Q;", "Q"),
    "ட": ("nls", "Nlh", "nlh", "lh", "b", "B", "L", "^", "nl", "Nl", "il", "l;", "l"),
    "ண": ("nzs", "Nzh", "nzh", "zh", "zp", "zP", "Z", "Z}", "nz", "Nz", "iz", "z;", "z"),
    "த": ("njs", "Njh", "njh", "jh", "jp", "jP", "J", "J}", "nj", "Nj", "ij", "j;", "j"),
    "ந": ("nes", "Neh", "neh", "eh", "ep", "eP", "E", "E}", "ne", "Ne", "ie", "e;", "e"),
    "ன": ("nds", "Ndh", "ndh", "dh", "dp", "dP", "D", "D}", "nd", "Nd", "id", "d;", "d"),
    "ப": ("ngs", "Ngh", "ngh", "gh", "gp", "gP", "G", "G+", "ng", "Ng", "ig", "g;", "g"),
    "ம": ("nks", "Nkh", "nkh", "kh", "kp", "kP", "K", "%", "nk", "Nk", "ik", "k;", "k"),
    "ய": ("nas", "Nah", "nah", "ah", "ap", "aP", "A", "A+", "na", "Na", "ia", "a;", "a"),
    "ர": ("nus", "Nuh", "nuh", "uh", "up", "uP", "U", "\\&", "nu", "Nu", "iu", "u;", "u"),
    "ல": ("nys", "Nyh", "nyh", "yh", "yp", "yP", "Y", "Y}", "ny", "Ny", "iy", "y;", "y"),
    "ள": ("nss", "Nsh", "nsh", "sh", "sp", "sP", "S", "Sh", "ns", "Ns", "is", "s;", "s"),
    "வ": ("nts", "Nth", "nth", "th", "tp", "tP", "T", "T+", "nt", "Nt", "it", "t;", "t"),
    "ழ": ("nos", "Noh", "noh", "oh", "op", "oP", "O", "*", "no", "No", "io", "o;", "o"),
    "ற": ("nws", "Nwh", "nwh", "wh", "wp", "wP", "W", "W}", "nw", "Nw", "iw", "w;", "w"),
    "ஜ": ("n[s", "N[h", "n[h", "[h", "[p", "[P", "[{", "[_", "n[", "N[", "i[", "[;", "["),
    "ஹ": ("n`s", "N`h", "n`h", "`h", "`p", "`P", "{`", "`_", "n`", "N`", "i`", "`;", "`"),
    "ஷ": ("n\\s", "N\\h", "n\\h", "\\h", "\\p", "\\P", "{", "\\_", "n\\", "N\\", "i\\", "\\;", "\\"),
    "ஸ": ("n]s", "N]h", "n]h", "]h", "]p", "]P", "]{", "]_", "n]", "N]", "i]", "] ;".replace(" ", ""), "]"),
}
_INDEPENDENT_VOWELS = {
    "அ": "m", "ஆ": "M", "இ": ",", "ஈ": "<", "உ": "c", "ஊ": "C",
    "எ": "v", "ஏ": "V", "ஐ": "I", "ஒ": "x", "ஓ": "X", "ஔ": "xs",
    "ஃ": "/",
}
_BAMINI_MAP = {
    consonant + vowel: legacy
    for consonant, legacy_values in _CONSONANTS.items()
    for vowel, legacy in zip(_VOWEL_SIGNS, legacy_values)
}
_BAMINI_MAP.update(_INDEPENDENT_VOWELS)
_BAMINI_MAP["ஸ்ரீ"] = "="
_BAMINI_MAP[","] = ">"
_CONVERSION_PATTERN = re.compile(
    "|".join(re.escape(key) for key in sorted(_BAMINI_MAP, key=len, reverse=True))
)
_TAMIL_SEGMENT = re.compile(r"[\u0B80-\u0BFF]+(?:\s+[\u0B80-\u0BFF]+)*")


def unicode_to_bamini(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return _CONVERSION_PATTERN.sub(lambda match: _BAMINI_MAP[match.group(0)], normalized)


def split_bamini_segments(text: str) -> list[tuple[str, bool]]:
    """Return (text, is_bamini_encoded) pieces, leaving Latin text in Unicode."""
    pieces: list[tuple[str, bool]] = []
    position = 0
    for match in _TAMIL_SEGMENT.finditer(text):
        if match.start() > position:
            pieces.append((text[position:match.start()], False))
        pieces.append((unicode_to_bamini(match.group(0)), True))
        position = match.end()
    if position < len(text):
        pieces.append((text[position:], False))
    return pieces or [(text, False)]
