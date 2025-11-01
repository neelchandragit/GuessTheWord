import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from utils.hint_utils import get_possible_matches, display_hint
from utils.word_loader import word_lists_polish
from config import guild, active_games

class MemorizeRandomPl(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="memorize_random_pl",
        description="Random Polish hints (repeats allowed). Continues until a hint is failed."
    )
    @app_commands.describe(length="Length of Polish words to use")
    async def memorize_random_pl(self, interaction: discord.Interaction, length: int):
        await interaction.response.defer()
        channel = interaction.channel

        entries_of_length = [w for w in word_lists_polish if len(w["polish"]) == length]
        if not entries_of_length:
            await channel.send(f"❌ No Polish words of length {length} found.")
            return

        if active_games.get(channel.id):
            await channel.send("⚠️ A session is already active in this channel.")
            return
        active_games[channel.id] = True

        await channel.send(
            f"🎲 Starting randomized PL memorization for **{length}**-letter words. "
            f"Type `endmemorize` to stop."
        )

        try:
            while active_games.get(channel.id):
                # Pick a random word and a random non-space position
                entry = random.choice(entries_of_length)
                pl_word = entry["polish"]
                positions = [i for i, c in enumerate(pl_word) if c != ' ']
                if not positions:
                    continue
                pos = random.choice(positions)
                letter = pl_word[pos].lower()

                # Build a hint with the true letter at pos
                raw_hint = '_' * pos + letter + '_' * (len(pl_word) - pos - 1)

                # All Polish matches for this hint
                pl_matches = get_possible_matches(raw_hint, [w["polish"] for w in entries_of_length])
                if not pl_matches:
                    continue

                # Build map: any accepted answer -> set of "Polish(English)" tags for THIS hint
                answer_to_pl_eng = {}
                all_needed = set()
                for w in entries_of_length:
                    if w["polish"] not in pl_matches:
                        continue
                    tag = f"{w['polish']}({w.get('english', '')})"
                    all_needed.add(tag)

                    # Accept the polish itself + all accepted answers (translations/shortcut/multiwords)
                    for key in {w["polish"], *w.get("answers", set())}:
                        k = key.strip().lower()
                        if not k:
                            continue
                        answer_to_pl_eng.setdefault(k, set()).add(tag)

                # ✅ Progress by unique Polish base word only
                def base_of(tag: str) -> str:
                    # "Bar(Bar)" -> "Bar"
                    return tag.split('(', 1)[0]

                base_needed = {base_of(t) for t in all_needed}
                base_guessed = set()

                guessed_tags = set()
                timeout = 10 + 3 * len(pl_matches)

                await channel.send(
                    f"🧩 **Random PL hint**\n"
                    f"Hint:\n```{display_hint(raw_hint)}```\n"
                    f"Guess all {len(base_needed)} unique Polish word(s) in **{timeout} seconds**. "
                    f"Type `endmemorize` to stop."
                )

                start = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start) < timeout and active_games.get(channel.id):
                    try:
                        msg = await self.bot.wait_for(
                            "message",
                            timeout=timeout - (asyncio.get_event_loop().time() - start),
                            check=lambda m: m.channel.id == channel.id and not m.author.bot
                        )
                    except asyncio.TimeoutError:
                        break

                    content = msg.content.strip().lower()
                    if content == "endmemorize":
                        await channel.send("⏹️ Session ended early.")
                        active_games.pop(channel.id, None)
                        return

                    if content not in answer_to_pl_eng:
                        continue

                    # All tags matched by this guess; show them all, but credit only one base
                    new_hits = [t for t in answer_to_pl_eng[content] if t not in guessed_tags]
                    if not new_hits:
                        continue

                    guessed_tags.update(new_hits)
                    await channel.send(f"✅ `{content}` guessed! ({', '.join(sorted(new_hits))})")

                    # Credit at most ONE new base per guess
                    credited = False
                    for t in new_hits:
                        b = base_of(t)
                        if b not in base_guessed:
                            base_guessed.add(b)
                            credited = True
                            break

                    # Progress = #unique Polish bases guessed / total unique bases
                    await channel.send(f"Progress: {len(base_guessed)}/{len(base_needed)}")

                    if base_guessed >= base_needed:
                        await channel.send("🎉 All words for this hint guessed! Next random hint…")
                        break

                # If we didn’t complete all base words for the hint → end session
                if base_guessed < base_needed and active_games.get(channel.id):
                    missed_bases = sorted(base_needed - base_guessed)
                    await channel.send("❌ Time's up or miss detected! Missed base words:\n" + ", ".join(missed_bases))
                    await channel.send("🏁 Session over.")
                    active_games.pop(channel.id, None)
                    return

            if not active_games.get(channel.id):
                await channel.send("⏹️ Session ended.")

        finally:
            active_games.pop(channel.id, None)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemorizeRandomPl(bot), guild=guild)
