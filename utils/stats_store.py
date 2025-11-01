import json, os, asyncio
from typing import Dict, Any, Optional
from config import STATS_JSON

# JSON schema per user/lang/length:
# {
#   "<user_id>": {
#     "en": {
#       "<length>": {
#         "reps": { "pos-li": int },              # repetitions of each hint
#         "completed": { "pos-li": true, ... },    # set of completed hints
#         "record": { "pos": int, "letter_idx": int, "updated_at": str },  # farthest contiguous from (0,0)
#         "run": { "active": bool, "expected_pos": int, "expected_li": int }  # in-progress contiguous run
#       }
#     },
#     "pl": { ...same... }
#   }
# }

_lock = asyncio.Lock()

def _ensure_parent_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

async def _load() -> Dict[str, Any]:
    _ensure_parent_dir(STATS_JSON)
    if not os.path.exists(STATS_JSON):
        return {}
    try:
        with open(STATS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

async def _save(data: Dict[str, Any]):
    _ensure_parent_dir(STATS_JSON)
    tmp = STATS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATS_JSON)

def _bucket_for(data: Dict[str, Any], user_id: int, lang: str, length: int) -> Dict[str, Any]:
    u = data.setdefault(str(user_id), {})
    L = u.setdefault(lang, {})
    bucket = L.setdefault(str(length), {})
    bucket.setdefault("reps", {})
    bucket.setdefault("completed", {})
    bucket.setdefault("record", {"pos": -1, "letter_idx": -1, "updated_at": ""})
    bucket.setdefault("run", {"active": False, "expected_pos": 0, "expected_li": 0})
    return bucket

def _key(pos: int, li: int) -> str:
    return f"{pos}-{li}"

def _advance_pointer(pos: int, li: int, alphabet_len: int, word_len: int):
    """Given current pos/li, compute next (pos, li) in A→Z then next position traversal."""
    li += 1
    if li >= alphabet_len:
        li = 0
        pos += 1
    # note: caller must ensure pos < word_len when used
    return pos, li

async def bump_repetition(user_id: int, lang: str, length: int, pos: int, li: int, updated_at_iso: str):
    """Increment repetition count for this exact hint (pos, li)."""
    async with _lock:
        data = await _load()
        bucket = _bucket_for(data, user_id, lang, length)
        reps = bucket["reps"]
        k = _key(pos, li)
        reps[k] = int(reps.get(k, 0)) + 1
        bucket["updated_at"] = updated_at_iso
        await _save(data)

async def mark_completed(user_id: int, lang: str, length: int, pos: int, li: int, updated_at_iso: str):
    """Mark this exact hint (pos, li) as completed."""
    async with _lock:
        data = await _load()
        bucket = _bucket_for(data, user_id, lang, length)
        bucket["completed"][_key(pos, li)] = True
        bucket["updated_at"] = updated_at_iso
        await _save(data)

async def start_run_if_at_beginning(user_id: int, lang: str, length: int, start_pos: int, start_li: int):
    """Begin a contiguous-run tracker only if starting exactly at (0,0)."""
    async with _lock:
        if start_pos != 0 or start_li != 0:
            return
        data = await _load()
        bucket = _bucket_for(data, user_id, lang, length)
        bucket["run"] = {"active": True, "expected_pos": 0, "expected_li": 0}
        await _save(data)

async def advance_run_on_success(
    user_id: int, lang: str, length: int,
    pos: int, li: int, updated_at_iso: str,
    alphabet_len: int, word_len: int
):
    """If a contiguous run is active and this success matches the expected pointer,
       advance pointer and update 'record' if this is farther."""
    async with _lock:
        data = await _load()
        bucket = _bucket_for(data, user_id, lang, length)
        run = bucket["run"]
        if not run.get("active"):
            return
        if run["expected_pos"] != pos or run["expected_li"] != li:
            return  # success out of order: do not advance record
        # update record if farther (lexicographic by pos then li)
        rec = bucket["record"]
        if pos > rec.get("pos", -1) or (pos == rec.get("pos", -1) and li > rec.get("letter_idx", -1)):
            rec["pos"] = pos
            rec["letter_idx"] = li
            rec["updated_at"] = updated_at_iso
        # advance expected pointer
        npos, nli = _advance_pointer(pos, li, alphabet_len, word_len)
        run["expected_pos"] = npos
        run["expected_li"] = nli
        bucket["updated_at"] = updated_at_iso
        await _save(data)

async def end_run(user_id: int, lang: str, length: int):
    """Stop any active contiguous run (e.g., on failure)."""
    async with _lock:
        data = await _load()
        bucket = _bucket_for(data, user_id, lang, length)
        bucket["run"]["active"] = False
        await _save(data)

async def get_user_stats(user_id: int) -> Dict[str, Any]:
    async with _lock:
        data = await _load()
        return data.get(str(user_id), {})

async def reset_user_stats(user_id: int, lang: Optional[str] = None, length: Optional[int] = None):
    async with _lock:
        data = await _load()
        uid = str(user_id)
        if uid not in data:
            return
        if lang is None:
            data.pop(uid, None)
        else:
            if length is None:
                data[uid][lang] = {}
            else:
                data[uid][lang].pop(str(length), None)
        await _save(data)
