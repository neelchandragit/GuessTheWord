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

def load_word_lists_from_json(file_path: str) -> Dict[str, List[EnEntry]]:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    easy: List[EnEntry] = []
    medium: List[EnEntry] = []
    hard: List[EnEntry] = []

    for entry in raw:
        bot_word: str = entry["theme"]
        valid: Set[str] = set()
        valid.add(bot_word.lower())
        valid.add(bot_word.lower().replace(" ", ""))

        for t in entry.get("translations", {}).values():
            tr = t.get("translation")
            if tr:
                valid.add(tr.lower())

        sc = entry.get("shortcut")
        if sc:
            valid.add(sc.lower())

        for mw in entry.get("multiwords", []):
            m = mw.get("multiword")
            if m:
                valid.add(m.lower())

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

        valid: Set[str] = set()
        valid.add(pl.lower())
        valid.add(pl.lower().replace(" ", ""))

        en = entry.get("theme", "")
        if en:
            valid.add(en.lower())

        sc = entry.get("shortcut")
        if sc:
            valid.add(sc.lower())

        for mw in entry.get("multiwords", []):
            m = mw.get("multiword")
            if m:
                valid.add(m.lower())

        out.append({"polish": pl, "english": en, "answers": valid})
    return out

# Load on import so cogs can just import variables
word_lists = load_word_lists_from_json(WORDS_JSON)
word_lists_polish = load_word_lists_from_json_polish(WORDS_JSON)

