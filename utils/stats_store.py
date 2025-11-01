from collections import defaultdict

# user -> lang -> dict
_state = defaultdict(lambda: defaultdict(lambda: {
    "run_started": False,
    "run_len": 0,
    "record": 0,
    "completed_hints": 0,
    "repetitions": defaultdict(int),
    "count_record": False,   # NEW: per-run flag
}))

def _bucket(user_id, lang):
    return _state[user_id][lang]

def start_run_if_at_beginning(user_id, lang, start_index: int, count_record: bool):
    b = _bucket(user_id, lang)
    # Only start a record-eligible run if caller said so AND we are truly at index 0
    b["run_started"] = bool(count_record and start_index == 0)
    b["run_len"] = 0
    b["count_record"] = b["run_started"]

def advance_run_on_success(user_id, lang):
    b = _bucket(user_id, lang)
    # Always track run length in-session; only promote to record if the flag is on
    b["run_len"] += 1
    if b["count_record"] and b["run_len"] > b["record"]:
        b["record"] = b["run_len"]

def bump_repetition(user_id, lang, position: int, letter: str):
    b = _bucket(user_id, lang)
    key = (position, letter)
    b["repetitions"][key] += 1

def mark_completed(user_id, lang):
    b = _bucket(user_id, lang)
    b["completed_hints"] += 1

def end_run(user_id, lang):
    b = _bucket(user_id, lang)
    # Cleanly close the run; never carry record-eligibility into the next session
    b["run_started"] = False
    b["count_record"] = False
    b["run_len"] = 0

def get_stats(user_id, lang):
    b = _bucket(user_id, lang)
    # Flatten repetitions to your display format if needed in /stats
    return {
        "record": b["record"],
        "completed_hints": b["completed_hints"],
        "repetitions": dict(b["repetitions"]),
    }
