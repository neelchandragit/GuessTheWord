from __future__ import annotations
import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import asyncio
from typing import Dict, Any

# ---------- persistence ----------
# default location: ./stats.json (override with env STATS_FILE)
STATS_PATH = Path(os.getenv("STATS_FILE", "stats.json")).resolve()
_LOCK = asyncio.Lock()

def _default_leaf():
    return {
        "run_started": False,            # currently in an eligible contiguous run
        "run_len": 0,                    # current contiguous run length
        "record": 0,                     # best contiguous run length
        "record_updated_at": "",         # ISO timestamp when record last updated
        "record_last_pos": None,         # 0-based position where record run last succeeded
        "record_last_li": None,          # 0-based letter index where record run last succeeded
        "repetitions": defaultdict(int), # key "pos-li" -> count
        "count_record": False,           # this run is eligible to update record (no start_hint)
    }

# user -> lang -> length -> leaf
_state: Dict[int, Dict[str, Dict[int, Dict[str, Any]]]] = defaultdict(
    lambda: defaultdict(lambda: defaultdict(_default_leaf))
)

def _to_plain(obj):
    """Convert nested defaultdicts & inner defaultdict(int) to plain dicts for JSON."""
    if isinstance(obj, defaultdict):
        obj = dict(obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[k] = _to_plain(v)
        return out
    return obj

def _from_plain(d):
    """Hydrate plain dict back into our nested defaultdict structure."""
    global _state
    _state = defaultdict(lambda: defaultdict(lambda: defaultdict(_default_leaf)))
    for user_id_str, langs in d.items():
        try:
            user_id = int(user_id_str)
        except ValueError:
            # keys might already be int if we saved that way
            user_id = user_id_str
        for lang, lengths in langs.items():
            for length_str, leaf in lengths.items():
                try:
                    length = int(length_str)
                except ValueError:
                    length = length_str
                b = _state[user_id][lang][length]
                # copy simple fields
                b["run_started"] = bool(leaf.get("run_started", False))
                b["run_len"] = int(leaf.get("run_len", 0))
                b["record"] = int(leaf.get("record", 0))
                b["record_updated_at"] = leaf.get("record_updated_at", "")
                b["record_last_pos"] = leaf.get("record_last_pos", None)
                b["record_last_li"]  = leaf.get("record_last_li", None)
                b["count_record"] = bool(leaf.get("count_record", False))
                # repetitions
                reps = leaf.get("repetitions", {}) or {}
                dd = defaultdict(int)
                for rk, rv in reps.items():
                    try:
                        dd[rk] = int(rv)
                    except Exception:
                        pass
                b["repetitions"] = dd

def _load_from_disk():
    if not STATS_PATH.exists():
        return
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _from_plain(data)
    except Exception:
        # if file is corrupted, ignore and start fresh (could log)
        pass

def _ensure_parent():
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)

def _atomic_write_text(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)

async def _save_to_disk():
    _ensure_parent()
    payload = _to_plain(_state)
    # JSON keys must be strings; convert the top user_id and length keys to str for safety
    def stringify_keys(obj):
        if isinstance(obj, dict):
            return {str(k): stringify_keys(v) for k, v in obj.items()}
        return obj
    payload = stringify_keys(payload)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    _atomic_write_text(STATS_PATH, text)

# Load once on import
_load_from_disk()

# ---------- internal helpers ----------
def _bucket(user_id: int, lang: str, length: int):
    return _state[user_id][lang][length]

# ---------- API (called by cogs) ----------
async def start_run_if_at_beginning(user_id: int, lang: str, length: int,
                                    start_pos: int, start_letter_idx: int,
                                    record_eligible: bool):
    """
    Record eligibility depends ONLY on 'record_eligible' (i.e., no start_hint).
    """
    async with _LOCK:
        b = _bucket(user_id, lang, length)
        eligible = bool(record_eligible)
        b["run_started"] = eligible
        b["run_len"] = 0
        b["count_record"] = eligible
        await _save_to_disk()

async def advance_run_on_success(user_id: int, lang: str, length: int,
                                 pos: int, li: int, iso: str,
                                 alphabet_len: int, word_len: int):
    async with _LOCK:
        b = _bucket(user_id, lang, length)
        b["run_len"] += 1
        if b["count_record"] and b["run_len"] > b["record"]:
            b["record"] = b["run_len"]
            b["record_updated_at"] = iso
            b["record_last_pos"] = pos
            b["record_last_li"]  = li
        await _save_to_disk()

async def bump_repetition(user_id: int, lang: str, length: int,
                          pos: int, li: int, iso: str):
    async with _LOCK:
        b = _bucket(user_id, lang, length)
        key = f"{pos}-{li}"  # 0-based pos and letter index
        b["repetitions"][key] += 1
        await _save_to_disk()

# kept as a no-op (your UI doesn’t show completed counts anymore)
async def mark_completed(user_id: int, lang: str, length: int,
                         pos: int, li: int, iso: str):
    return

async def end_run(user_id: int, lang: str, length: int):
    async with _LOCK:
        b = _bucket(user_id, lang, length)
        b["run_started"] = False
        b["count_record"] = False
        b["run_len"] = 0
        await _save_to_disk()

async def get_stats(user_id: int) -> dict:
    """
    Returns:
    {
      "en": {
        "3": {
          "record": {"value": int, "updated_at": str, "last_pos": int|None, "last_li": int|None},
          "reps":   {"pos-li": int, ...}
        },
        ...
      },
      "pl": { ... }
    }
    """
    # Reading doesn't need the lock strictly, but take it to avoid tearing while serializing.
    async with _LOCK:
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
