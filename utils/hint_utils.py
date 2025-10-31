from typing import Iterable, List

def get_hint(word: str, revealed_indexes: Iterable[int]) -> str:
    """
    Produce a raw hint with underscores for hidden letters and real spaces preserved.
    BUGFIX: keep spaces as spaces (previously compared to empty string).
    """
    ri = set(revealed_indexes)
    return ''.join(
        (letter if (letter == ' ' or idx in ri) else '_')
        for idx, letter in enumerate(word)
    )

def display_hint(raw_hint: str) -> str:
    """
    Pretty hint for Discord monospace:
    - '_' -> '_ '
    - ' ' -> extra spaces to visually separate words
    """
    out = []
    for c in raw_hint:
        if c == '_':
            out.append('_ ')
        elif c == ' ':
            out.append('    ')
        else:
            out.append(f"{c} ")
    return ''.join(out)

def get_possible_matches(raw_hint: str, word_pool: List[str]) -> List[str]:
    """
    Returns words that match the hint exactly (length, letters, spaces).
    """
    L = len(raw_hint)
    matches: List[str] = []
    for w in word_pool:
        if len(w) != L:
            continue
        ok = True
        for i, hc in enumerate(raw_hint):
            wc = w[i]
            if hc == '_':
                if wc == ' ':  # hidden char can't be a space
                    ok = False
                    break
            elif hc == ' ':
                if wc != ' ':
                    ok = False
                    break
            else:
                if hc.lower() != wc.lower():
                    ok = False
                    break
        if ok:
            matches.append(w)
    return matches

