from __future__ import annotations
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Set

from config import active_games, guild
from utils.word_loader import word_lists_polish, POLISH_ALPHABET
from utils.hint_utils import display_hint, get_possible_matches

class MemorizeAllPlCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="memorize_pl",
        description="Cycle through all Polish hints of a given length, one at a time"
    )
    @app_commands.describe(length="Length of the Polish words", start_hint="Optional starting hint (e.g., __k_____)")
    async def memorize_pl(self, interaction: discord.Interaction, length: int, start_hint: str | None = None):
        await interaction.response.defer()
        channel = interaction.channel
        active_games[channel.id] = True

        entries = [e for e in word_lists_polish if len(e["polish"]) == length]
        if not entries:
            await channel.send(f"❌ No Polish words of length {length} found.")
            active_games.pop(channel.id, None)
            return

        # starting position / letter
        start_pos, start_letter_idx = 0, 0
        if start_hint and len(start_hint) == length:
            for i, ch in enumerate(start_hint):
                if ch not in {'_', ' '}:
                    start_pos = i
                    if ch.lower() in POLISH_ALPHABET:
                        start_letter_idx = POLISH_ALPHABET.index(ch.lower())
                    break

        try:
            pos = start_pos
            while pos < length and active_games.get(channel.id):
                li = start_letter_idx
                while li < len(POLISH_ALPHABET) and active_games.get(channel.id):
                    letter = POLISH_ALPHABET[li]
                    raw_hint = '_' * pos + letter + '_' * (length - pos - 1)

                    pl_matches = get_possible_matches(raw_hint, [w["polish"] for w in entries])
                    pl_matches = list(dict.fromkeys(pl_matches))  # unique, preserve order
                    if not pl_matches:
                        li += 1
                        continue

                    # Build answer map for this hint
                    answer_to_pl_eng: Dict[str, Set[str]] = {}
                    all_needed: Set[str] = set()
                    for w in entries:
                        if w["polish"] not in pl_matches:
                            continue
                        tag = f"{w['polish']}({w.get('english','')})"
                        all_needed.add(tag)

                        for key in {w["polish"], *w.get("answers", set())}:
                            k = key.strip().lower()
                            if not k:
                                continue
                            answer_to_pl_eng.setdefault(k, set()).add(tag)

                    hint_completed = False
                    while not hint_completed and active_games.get(channel.id):
                        guessed: Set[str] = set()
                        timeout = 10 + 3 * len(pl_matches)
                        start_time = asyncio.get_event_loop().time()

                        await channel.send(
                            f"🧠 Memorize — position {pos+1}/{length}, letter `{letter.upper()}`\n"
                            f"Hint:\n```{display_hint(raw_hint)}```\n"
                            f"Guess all {len(pl_matches)} word(s) in **{timeout} seconds**. Type `endmemorize` to stop."
                        )

                        while (asyncio.get_event_loop().time() - start_time) < timeout:
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

                            new = [t for t in answer_to_pl_eng[content] if t not in guessed]
                            if not new:
                                continue

                            guessed.update(new)
                            await channel.send(
                                f"✅ {', '.join(sorted(new))} guessed! Progress: {len(guessed)}/{len(all_needed)}"
                            )

                            if guessed >= all_needed:
                                hint_completed = True
                                await channel.send("🎉 All words for this hint guessed! Moving on…")
                                break

                        if not hint_completed:
                            msg = await channel.send(
                                "❌ Time's up or some words were missed!\n"
                                "Here are all correct words:\n" +
                                ", ".join(sorted(all_needed))
                            )
                            await asyncio.sleep(10)
                            await msg.delete()
                            await channel.send(f"🔁 Let's retry the same hint:\n```{display_hint(raw_hint)}```")

                    li += 1

                start_letter_idx = 0
                pos += 1

            await channel.send("✅ Finished all hints or session ended.")
        finally:
            active_games.pop(channel.id, None)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemorizeAllPlCog(bot), guild=guild)

