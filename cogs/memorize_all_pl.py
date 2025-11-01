import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from utils.hint_utils import get_possible_matches, display_hint
from utils.word_loader import word_lists_polish, POLISH_ALPHABET
from config import guild, active_games
from datetime import datetime, timezone
from utils.stats_store import (
    bump_repetition, mark_completed,
    start_run_if_at_beginning, advance_run_on_success, end_run
)


class MemorizeAllPl(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="memorize_pl",
        description="Cycle through all Polish hints of a given length, one at a time (A→Ż per position)."
    )
    @app_commands.describe(
        length="Length of the Polish words to memorize",
        start_hint="Optional starting hint (e.g., __k______)"
    )
    async def memorize_pl(self, interaction: discord.Interaction, length: int, start_hint: str | None = None):
        await interaction.response.defer()
        channel = interaction.channel

        # Filter to words of the requested length
        entries = [e for e in word_lists_polish if len(e["polish"]) == length]
        if not entries:
            await channel.send(f"❌ No Polish words of length {length} found.")
            return

        # Only one session per channel
        if active_games.get(channel.id):
            await channel.send("⚠️ A session is already active in this channel.")
            return
        active_games[channel.id] = True

        # --- Determine starting position and letter index from start_hint (if any)
        start_pos, start_letter_idx = 0, 0
        if start_hint and len(start_hint) == length:
            for i, ch in enumerate(start_hint):
                if ch not in {'_', ' '}:
                    start_pos = i
                    if ch.lower() in POLISH_ALPHABET:
                        start_letter_idx = POLISH_ALPHABET.index(ch.lower())
                    break

        author_id = interaction.user.id

        # Always close any previous contiguous run for this user/length/lang bucket
        await end_run(author_id, "pl", length)

        # Record-eligible ONLY if user did not pass a start hint and we truly begin at index 0, letter 0
        record_eligible = (not start_hint) and (start_pos == 0) and (start_letter_idx == 0)

        # Start a new run; stats_store will remember if this run is allowed to affect 'record'
        # NOTE: start_run_if_at_beginning signature per my suggested stats_store:
        #   start_run_if_at_beginning(user_id, lang, start_index:int, record_eligible:bool)
        # If your implementation tracks per-length, keep your length dimension in the bucket and call as below.
        await start_run_if_at_beginning(author_id, "pl", length, start_pos, start_letter_idx, record_eligible)

        try:
            pos = start_pos
            while pos < length and active_games.get(channel.id):
                li = start_letter_idx
                while li < len(POLISH_ALPHABET) and active_games.get(channel.id):
                    letter = POLISH_ALPHABET[li]
                    raw_hint = '_' * pos + letter + '_' * (length - pos - 1)

                    # Compute matches for this letter-at-position hint
                    pl_matches = get_possible_matches(raw_hint, [w["polish"] for w in entries])
                    # dedupe, preserve order
                    pl_matches = list(dict.fromkeys(pl_matches))
                    if not pl_matches:
                        li += 1
                        continue

                    # Build accepted answers map -> tags
                    answer_to_pl_eng = {}
                    all_needed = set()
                    for w in entries:
                        if w["polish"] not in pl_matches:
                            continue
                        tag = f"{w['polish']}({w.get('english','')})"
                        all_needed.add(tag)
                        # Accept base and any configured alt-answers
                        all_keys = {w["polish"], *w.get("answers", set())}
                        for k in {k.strip().lower() for k in all_keys if k and k.strip()}:
                            answer_to_pl_eng.setdefault(k, set()).add(tag)

                    # Count progress by base Polish word (not per meaning)
                    def base_of(tag: str) -> str:
                        return tag.split('(', 1)[0]

                    base_needed = {base_of(t) for t in all_needed}
                    base_guessed = set()
                    guessed_tags = set()

                    # Timeout scales with number of matches
                    timeout = 10 + 3 * len(pl_matches)
                    start_time = asyncio.get_event_loop().time()

                    await channel.send(
                        f"🧠 Memorize — position {pos+1}/{length}, letter `{letter.upper()}`\n"
                        f"Hint:\n```{display_hint(raw_hint)}```\n"
                        f"Guess all {len(base_needed)} unique Polish word(s) in **{timeout} seconds**. "
                        f"Type `endmemorize` to stop."
                    )

                    while (asyncio.get_event_loop().time() - start_time) < timeout and active_games.get(channel.id):
                        try:
                            msg = await self.bot.wait_for(
                                "message",
                                timeout=timeout - (asyncio.get_event_loop().time() - start_time),
                                check=lambda m: m.channel.id == channel.id and not m.author.bot
                            )
                        except asyncio.TimeoutError:
                            break

                        content = msg.content.strip().lower()
                        if content == "endmemorize":
                            await channel.send("⏹️ Memorization session ended early.")
                            active_games.pop(channel.id, None)
                            return

                        if content not in answer_to_pl_eng:
                            continue

                        new_hits = [t for t in answer_to_pl_eng[content] if t not in guessed_tags]
                        if not new_hits:
                            continue

                        guessed_tags.update(new_hits)
                        await channel.send(f"✅ `{content}` guessed! ({', '.join(sorted(new_hits))})")

                        # Credit at most one new base per user message
                        for t in new_hits:
                            b = base_of(t)
                            if b not in base_guessed:
                                base_guessed.add(b)
                                break

                        await channel.send(f"Progress: {len(base_guessed)}/{len(base_needed)}")

                        if base_guessed >= base_needed:
                            await channel.send("🎉 All words for this hint guessed! Moving on…")

                            # log stats
                            iso = datetime.now(timezone.utc).isoformat()
                            await bump_repetition(interaction.user.id, "pl", length, pos, li, iso)
                            await mark_completed(interaction.user.id, "pl", length, pos, li, iso)

                            # advance the contiguous run (stats_store decides whether to touch 'record' based on run flag)
                            alphabet_len = len(POLISH_ALPHABET)
                            word_len = length
                            await advance_run_on_success(
                                interaction.user.id, "pl", length, pos, li, iso, alphabet_len, word_len
                            )
                            break

                    # If we didn’t finish this hint, end the run and retry same letter
                    if base_guessed < base_needed and active_games.get(channel.id):
                        missed = sorted(base_needed - base_guessed)
                        msg = await channel.send(
                            "❌ Time's up or some words were missed!\n"
                            "Missed base words:\n" + ", ".join(missed)
                        )

                        # End current run so partial progress doesn’t inappropriately affect record
                        await end_run(interaction.user.id, "pl", length)

                        await asyncio.sleep(10)
                        await msg.delete()
                        await channel.send(f"🔁 Let's retry the same hint:\n```{display_hint(raw_hint)}```")
                        # retry same letter (no li += 1)
                        continue

                    # Completed this letter — move to next letter
                    li += 1

                # Move to next position and reset letter index
                start_letter_idx = 0
                pos += 1

            await channel.send("✅ Finished all hints or session ended.")
        finally:
            active_games.pop(channel.id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(MemorizeAllPl(bot), guild=guild)
