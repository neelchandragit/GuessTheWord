import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Set
from datetime import datetime, timezone

from config import active_games, guild
from utils.word_loader import word_lists, EN_ALPHABET
from utils.hint_utils import display_hint, get_possible_matches
from utils.stats_store import (
    bump_repetition, mark_completed,
    start_run_if_at_beginning, advance_run_on_success, end_run
)

async def run_memorize_game(
    bot: commands.Bot,
    channel: discord.abc.Messageable,
    entries_of_length: List[dict],
    length: int,
    start_hint: str | None,
    alphabet: List[str],
    author_id: int,              # 👈 pass the user id in
):
    active_games[channel.id] = True

    # figure out where to start
        # figure out where to start
    start_pos, start_letter_idx = 0, 0
    if start_hint and len(start_hint) == length:
        for i, ch in enumerate(start_hint):
            if ch not in {'_', ' '}:
                start_pos = i
                if ch.lower() in alphabet:
                    start_letter_idx = alphabet.index(ch.lower())
                break

    # Reset any existing contiguous run for this user/length
    await end_run(author_id, "en", length)

    # Record-eligible ONLY if no start_hint and we're truly at (pos=0, letter=0)
    record_eligible = (not start_hint)

    # NEW signature: includes record_eligible
    await start_run_if_at_beginning(author_id, "en", length, start_pos, start_letter_idx, record_eligible)


    


    try:
        pos = start_pos
        while pos < length and active_games.get(channel.id):
            for li in range(start_letter_idx, len(alphabet)):
                if not active_games.get(channel.id):
                    break

                letter = alphabet[li]
                raw_hint = '_' * pos + letter + '_' * (length - pos - 1)
                possible_matches = get_possible_matches(raw_hint, [w["english"] for w in entries_of_length])
                if not possible_matches:
                    continue

                # map any accepted answer -> english word
                answer_to_eng: Dict[str, str] = {}
                for w in entries_of_length:
                    if w["english"] in possible_matches:
                        for a in w["answers"]:
                            answer_to_eng[a.lower()] = w["english"]

                while active_games.get(channel.id):
                    guessed: Set[str] = set()
                    timeout = 10 + 3 * len(possible_matches)
                    start_time = asyncio.get_event_loop().time()

                    await channel.send(
                        f"🧠 Memorize — position {pos+1}/{length}, letter `{letter.upper()}`\n"
                        f"Hint:\n```{display_hint(raw_hint)}```\n"
                        f"Guess all {len(possible_matches)} word(s) in **{timeout} seconds**. Type `endmemorize` to stop."
                    )

                    while (asyncio.get_event_loop().time() - start_time) < timeout:
                        try:
                            msg = await bot.wait_for(
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

                        if content in answer_to_eng:
                            eng = answer_to_eng[content]
                            if eng not in guessed:
                                guessed.add(eng)
                                await channel.send(
                                    f"✅ `{eng}` guessed! Progress: {len(guessed)}/{len(possible_matches)}"
                                )
                                if len(guessed) == len(possible_matches):
                                    # ✅ Completed this hint
                                    await channel.send("🎉 All words for this hint guessed! Moving on…")
                                    iso = datetime.now(timezone.utc).isoformat()
                                    await bump_repetition(author_id, "en", length, pos, li, iso)
                                    await mark_completed(author_id, "en", length, pos, li, iso)
                                    await advance_run_on_success(author_id, "en", length, pos, li, iso, len(alphabet), length)
                                    break

                    if len(guessed) == len(possible_matches):
                        break
                    else:
                        # ❌ Failed this hint → end contiguous run, retry same hint
                        msg = await channel.send(
                            "❌ Time's up or some words were missed!\n"
                            "Here are all correct words:\n" +
                            ", ".join(f"`{w}`" for w in possible_matches)
                        )
                        await end_run(author_id, "en", length)
                        await asyncio.sleep(10)
                        await msg.delete()
                        await channel.send(f"🔁 Let's retry the same hint:\n```{display_hint(raw_hint)}```")

            start_letter_idx = 0
            pos += 1

        await channel.send("✅ Finished all hints or session ended.")
    finally:
        active_games.pop(channel.id, None)

class MemorizeAllEnCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="memorize_all",
        description="Cycle through all English hints of a given length"
    )
    @app_commands.describe(length="Length of the words", start_hint="Optional starting hint (e.g., __m______)")
    async def memorize_all(self, interaction: discord.Interaction, length: int, start_hint: str | None = None):
        await interaction.response.defer()
        channel = interaction.channel
        author_id = interaction.user.id  # 👈 capture once

        all_entries = sum([word_lists[d] for d in ["easy", "medium", "hard"]], [])
        entries_of_len = [w for w in all_entries if len(w["english"]) == length]
        if not entries_of_len:
            await channel.send(f"❌ No English words of length {length} found.")
            return

        await run_memorize_game(
            self.bot, channel, entries_of_len, length, start_hint, EN_ALPHABET, author_id
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MemorizeAllEnCog(bot), guild=guild)
