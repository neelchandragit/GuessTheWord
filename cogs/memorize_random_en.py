import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from utils.hint_utils import get_possible_matches, display_hint
from utils.word_loader import word_lists
from config import guild, active_games

class MemorizeRandomEn(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="memorize_random_en",
        description="Random English hints (repeats allowed). Continues until a hint is failed."
    )
    @app_commands.describe(length="Length of English words to use")
    async def memorize_random_en(self, interaction: discord.Interaction, length: int):
        await interaction.response.defer()
        channel = interaction.channel

        all_entries = sum([word_lists[d] for d in ["easy", "medium", "hard"]], [])
        entries_of_length = [w for w in all_entries if len(w["english"]) == length]
        if not entries_of_length:
            await channel.send(f"❌ No English words of length {length} found.")
            return

        # Guard against concurrent sessions in the same channel
        if active_games.get(channel.id):
            await channel.send("⚠️ A session is already active in this channel.")
            return
        active_games[channel.id] = True

        await channel.send(f"🎲 Starting randomized EN memorization for **{length}**-letter words. Type `endmemorize` to stop.")

        try:
            while active_games.get(channel.id):
                # pick random word and random non-space position
                entry = random.choice(entries_of_length)
                eng_word = entry["english"]
                positions = [i for i, c in enumerate(eng_word) if c != ' ']
                if not positions:
                    continue
                pos = random.choice(positions)
                letter = eng_word[pos].lower()

                raw_hint = '_' * pos + letter + '_' * (len(eng_word) - pos - 1)

                possible_matches = get_possible_matches(raw_hint, [w["english"] for w in entries_of_length])
                if not possible_matches:
                    # rarely none match; just pick another
                    continue

                # Build answer map
                answer_to_eng = {}
                for w in entries_of_length:
                    if w["english"] in possible_matches:
                        for ans in w["answers"]:
                            answer_to_eng[ans.lower()] = w["english"]

                all_needed = set(possible_matches)
                guessed_set = set()
                timeout = 10 + 3 * len(possible_matches)

                await channel.send(
                    f"🧩 **Random EN hint**\n"
                    f"Hint:\n```{display_hint(raw_hint)}```\n"
                    f"Guess all {len(possible_matches)} matching word(s) in **{timeout} seconds**. Type `endmemorize` to stop."
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

                    if content not in answer_to_eng:
                        continue

                    hit = answer_to_eng[content]
                    if hit not in guessed_set:
                        guessed_set.add(hit)
                        await channel.send(f"✅ `{hit}` guessed! Progress: {len(guessed_set)}/{len(all_needed)}")

                    if guessed_set >= all_needed:
                        await channel.send("🎉 All words for this hint guessed! Next random hint…")
                        break

                # If we didn’t get them all, end the session
                if guessed_set < all_needed and active_games.get(channel.id):
                    missed = sorted(all_needed - guessed_set)
                    await channel.send("❌ Time's up or miss detected! Missed:\n" + ", ".join(f"`{m}`" for m in missed))
                    await channel.send("🏁 Session over.")
                    active_games.pop(channel.id, None)
                    return

            # If loop exits because active_games was cleared
            if not active_games.get(channel.id):
                await channel.send("⏹️ Session ended.")

        finally:
            active_games.pop(channel.id, None)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemorizeRandomEn(bot), guild=guild)
