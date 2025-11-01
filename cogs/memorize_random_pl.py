import asyncio
import random
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone

from config import guild, active_games
from utils.hint_utils import get_possible_matches, display_hint
from utils.word_loader import word_lists_polish, POLISH_ALPHABET
from utils.stats_store import (
    bump_repetition, mark_completed, end_run
)

class MemorizeRandomPl(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="memorize_random_pl",
        description="Memorize Polish hints randomly until a failure occurs."
    )
    @app_commands.describe(length="Length of the Polish words to memorize randomly")
    async def memorize_random_pl(self, interaction: discord.Interaction, length: int):
        await interaction.response.defer()
        channel = interaction.channel
        author_id = interaction.user.id

        entries = [e for e in word_lists_polish if len(e["polish"]) == length]
        if not entries:
            await channel.send(f"❌ No Polish words of length {length} found.")
            return

        if active_games.get(channel.id):
            await channel.send("⚠️ A session is already active in this channel.")
            return
        active_games[channel.id] = True

        await channel.send(
            f"🎲 Random Polish memorize session started for **{length}-letter** words! "
            "Type `endmemorize` anytime to stop."
        )

        try:
            while active_games.get(channel.id):
                # Pick a random position and letter
                pos = random.randint(0, length - 1)
                li = random.randint(0, len(POLISH_ALPHABET) - 1)
                letter = POLISH_ALPHABET[li]
                raw_hint = "_" * pos + letter + "_" * (length - pos - 1)

                # Matches for this hint
                pl_matches = get_possible_matches(raw_hint, [w["polish"] for w in entries])
                pl_matches = list(dict.fromkeys(pl_matches))
                if not pl_matches:
                    continue

                # Build answer map and tag set
                answer_to_pl_eng = {}
                all_needed = set()
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

                # Progress by unique Polish base (not per meaning)
                def base_of(tag: str) -> str:
                    return tag.split('(', 1)[0]

                base_needed = {base_of(t) for t in all_needed}
                base_guessed = set()
                guessed_tags = set()
                timeout = 10 + 3 * len(pl_matches)
                start_time = asyncio.get_event_loop().time()

                await channel.send(
                    f"🧠 Random hint — position {pos+1}/{length}, letter `{letter.upper()}`\n"
                    f"Hint:\n```{display_hint(raw_hint)}```\n"
                    f"Guess all {len(base_needed)} unique Polish word(s) in **{timeout} seconds**!"
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

                    # Credit at most one new base per user guess
                    for t in new_hits:
                        b = base_of(t)
                        if b not in base_guessed:
                            base_guessed.add(b)
                            break

                    await channel.send(f"Progress: {len(base_guessed)}/{len(base_needed)}")

                    # Completed all guesses → random next hint
                    if base_guessed >= base_needed:
                        await channel.send("🎉 All words guessed! New random hint incoming…")
                        iso = datetime.now(timezone.utc).isoformat()
                        await bump_repetition(author_id, "pl", length, pos, li, iso)
                        await mark_completed(author_id, "pl", length, pos, li, iso)
                        break

                if base_guessed < base_needed and active_games.get(channel.id):
                    # ❌ Failed → end session
                    missed = sorted(base_needed - base_guessed)
                    await channel.send(
                        "❌ Time's up or some words were missed!\n"
                        "Missed base words:\n" + ", ".join(missed)
                    )
                    await end_run(author_id, "pl", length)
                    await channel.send("💀 Ending random session.")
                    active_games.pop(channel.id, None)
                    return

        finally:
            active_games.pop(channel.id, None)
            await channel.send("✅ Random session ended.")

async def setup(bot: commands.Bot):
    await bot.add_cog(MemorizeRandomPl(bot), guild=guild)
