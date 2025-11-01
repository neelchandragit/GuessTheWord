from __future__ import annotations
import json
from typing import Dict, List, Set, TypedDict
from config import WORDS_JSON

class EnEntry(TypedDict):
    english: str
    answers: Set[str]

class PlEntry(TypedDict):
    polish: str
    english: str
    answers: Set[str]

EN_ALPHABET = [chr(ord('a') + i) for i in range(26)]
POLISH_ALPHABET = [
    "a", "ą", "b", "c", "ć", "d", "e", "ę", "f", "g", "h", "i", "j", "k",
    "l", "ł", "m", "n", "ń", "o", "ó", "p", "q", "r", "s", "ś", "t", "u",
    "v", "w", "x", "y", "z", "ź", "ż"
]

# ---------- NEW: ASCII folding for Polish diacritics ----------
PL_ASCII_MAP = str.maketrans({
    "ą": "a", "Ą": "a",
    "ć": "c", "Ć": "c",
    "ę": "e", "Ę": "e",
    "ł": "l", "Ł": "l",
    "ń": "n", "Ń": "n",
    "ó": "o", "Ó": "o",
    "ś": "s", "Ś": "s",
    "ź": "z", "Ź": "z",
    "ż": "z", "Ż": "z",
})

def ascii_fold(s: str) -> str:
    """Translate Polish diacritics to ASCII equivalents."""
    return s.translate(PL_ASCII_MAP)

def gen_variants(s: str) -> Set[str]:
    """
    Given a phrase, generate acceptable variants:
    - lowercase
    - lowercase with spaces removed
    - ASCII-folded
    - ASCII-folded with spaces removed
    """
    s_low = s.lower()
    s_low_nospace = s_low.replace(" ", "")
    s_fold = ascii_fold(s_low)
    s_fold_nospace = s_fold.replace(" ", "")
    return {s_low, s_low_nospace, s_fold, s_fold_nospace}
# -------------------------------------------------------------

def load_word_lists_from_json(file_path: str) -> Dict[str, List[EnEntry]]:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    easy: List[EnEntry] = []
    medium: List[EnEntry] = []
    hard: List[EnEntry] = []

    for entry in raw:
        bot_word: str = entry["theme"]

        valid: Set[str] = set()
        # English theme itself + variants (also covers any diacritics if present)
        valid |= gen_variants(bot_word)

        # translations (any language): accept their variants too
        for t in entry.get("translations", {}).values():
            tr = t.get("translation")
            if tr:
                valid |= gen_variants(tr)

        # shortcut
        sc = entry.get("shortcut")
        if sc:
            valid |= gen_variants(sc)

        # multiwords
        for mw in entry.get("multiwords", []):
            m = mw.get("multiword")
            if m:
                valid |= gen_variants(m)

        length = len(bot_word)
        obj: EnEntry = {"english": bot_word, "answers": valid}
        if 3 <= length <= 5:
            easy.append(obj)
        elif 6 <= length <= 8:
            medium.append(obj)
        else:
            hard.append(obj)

    return {"easy": easy, "medium": medium, "hard": hard, "normal": easy + medium + hard}

def load_word_lists_from_json_polish(file_path: str) -> List[PlEntry]:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    out: List[PlEntry] = []
    for entry in raw:
        pl = entry.get("translations", {}).get("pl", {}).get("translation")
        if not pl:
            continue
        pl = pl.strip()
        en = entry.get("theme", "")

        valid: Set[str] = set()
        # Polish word + variants (adds ascii-folded forms like 'zolc' for 'żółć')
        valid |= gen_variants(pl)

        # Allow English theme as a valid guess (and variants)
        if en:
            valid |= gen_variants(en)

        # shortcut
        sc = entry.get("shortcut")
        if sc:
            valid |= gen_variants(sc)

        # multiwords
        for mw in entry.get("multiwords", []):
            m = mw.get("multiword")
            if m:
                valid |= gen_variants(m)

        out.append({"polish": pl, "english": en, "answers": valid})
    return out

# Load on import so cogs can just import variables
word_lists = load_word_lists_from_json(WORDS_JSON)
word_lists_polish = load_word_lists_from_json_polish(WORDS_JSON)
