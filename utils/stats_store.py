from collections import defaultdict
from datetime import datetime, timezone

# user -> lang -> length -> dict
_state = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
    "run_started": False,             # currently in an eligible contiguous run
    "run_len": 0,                     # current contiguous run length
    "record": 0,                      # best contiguous run length
    "record_updated_at": "",          # ISO timestamp when record last updated
    "record_last_pos": None,          # position index (0-based) where record run last succeeded
    "record_last_li": None,           # letter index (0-based) where record run last succeeded
    "repetitions": defaultdict(int),  # key "pos-li" -> count
    "count_record": False,            # this run is eligible to update record (no start_hint)
})))

def _bucket(user_id: int, lang: str, length: int):
    return _state[user_id][lang][length]

# --- session start ---
async def start_run_if_at_beginning(user_id: int, lang: str, length: int,
                                    start_pos: int, start_letter_idx: int,
                                    record_eligible: bool):
    """
    Record eligibility depends ONLY on 'record_eligible' (i.e., no start_hint).
    We ignore start_pos/start_letter_idx for eligibility per your requirement.
    """
    b = _bucket(user_id, lang, length)
    eligible = bool(record_eligible)
    b["run_started"] = eligible
    b["run_len"] = 0
    b["count_record"] = eligible

# --- called when a hint is fully completed ---
async def advance_run_on_success(user_id: int, lang: str, length: int,
                                 pos: int, li: int, iso: str,
                                 alphabet_len: int, word_len: int):
    b = _bucket(user_id, lang, length)
    # Always advance the in-session run length
    b["run_len"] += 1

    # Only touch record if this run is eligible
    if b["count_record"] and b["run_len"] > b["record"]:
        b["record"] = b["run_len"]
        b["record_updated_at"] = iso
        # store where the *record* run last succeeded (pos, letter)
        b["record_last_pos"] = pos
        b["record_last_li"] = li

# --- logging helpers ---
async def bump_repetition(user_id: int, lang: str, length: int,
                          pos: int, li: int, iso: str):
    b = _bucket(user_id, lang, length)
    key = f"{pos}-{li}"  # pos (0-based) and letter index (0-based)
    b["repetitions"][key] += 1

# Kept for compatibility with your cogs (no output in /stats)
async def mark_completed(user_id: int, lang: str, length: int,
                         pos: int, li: int, iso: str):
    return

async def end_run(user_id: int, lang: str, length: int):
    b = _bucket(user_id, lang, length)
    b["run_started"] = False
    b["count_record"] = False
    b["run_len"] = 0

# --- Getter for /stats command ---
async def get_stats(user_id: int) -> dict:
    """
    Returns:
    {
      "en": { "3": { "record": {...}, "reps": {...} }, ... },
      "pl": { "3": { "record": {...}, "reps": {...} }, ... },
    }
    record: {"value": int, "updated_at": str, "last_pos": int | None, "last_li": int | None}
    reps:   {"pos-li": int, ...}
    """
    user_data = _state.get(user_id, {})
    if not user_data:
        return {}

    out = {}
    for lang, lengths in user_data.items():
        out[lang] = {}
        for length, b in lengths.items():
            out[lang][str(length)] = {
                "record": {
                    "value": b.get("record", 0),
                    "updated_at": b.get("record_updated_at", ""),
                    "last_pos": b.get("record_last_pos", None),
                    "last_li":  b.get("record_last_li", None),
                },
                "reps": dict(b.get("repetitions", {})),
            }
    return out
