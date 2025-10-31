from __future__ import annotations
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from config import active_games, guild
from utils.word_loader import word_lists
from utils.hint_utils import get_hint, display_hint, get_possible_matches

class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="gtb", description="Play Guess the Build continuously")
    @app_commands.describe(difficulty="easy | medium | hard | normal")
    async def gtb(self, interaction: discord.Interaction, difficulty: str = "normal"):
        difficulty = difficulty.lower()
        if difficulty not in word_lists:
            await interaction.response.send_message(
                "❌ Invalid difficulty! Choose easy, medium, hard, or normal.",
                ephemeral=True
            )
            return

        if interaction.channel_id in active_games:
            await interaction.response.send_message(
                "⚠️ A game is already running in this channel!",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        channel = interaction.channel
        active_games[interaction.channel_id] = True

        await channel.send(f"🎮 Starting continuous Guess The Build! Difficulty: **{difficulty.title()}**")

        try:
            while True:
                entry = random.choice(word_lists[difficulty])
                word = entry["english"]
                answers = entry["answers"]

                # reveal one non-space letter to start
                revealed = {random.choice([i for i, c in enumerate(word) if c != ' '])}
                initial_hint = get_hint(word, revealed)
                await channel.send(
                    f"📝 New word! Length: **{len(word)}** Hint 1:\n```{display_hint(initial_hint)}```"
                )

                max_hints = 3
                hint_count = 1

                def check(m: discord.Message) -> bool:
                    return (
                        m.channel.id == channel.id
                        and not m.author.bot
                        and m.content.strip().lower() in answers
                    )

                while hint_count <= max_hints:
                    try:
                        msg = await self.bot.wait_for("message", timeout=10.0, check=check)
                        await channel.send(f"✅ {msg.author.mention} guessed the word **{word}** 🎉")

                        matches = get_possible_matches(
                            initial_hint, [w["english"] for w in word_lists[difficulty]]
                        )
                        await channel.send(
                            "📃 Words that matched the initial hint:\n" +
                            ", ".join(f"`{m}`" for m in matches)
                        )
                        break
                    except asyncio.TimeoutError:
                        hint_count += 1
                        if hint_count > max_hints:
                            matches = get_possible_matches(
                                initial_hint, [w["english"] for w in word_lists[difficulty]]
                            )
                            await channel.send(f"❌ No one guessed the word. It was **{word}**")
                            await channel.send(
                                "📃 Words that matched the initial hint:\n" +
                                ", ".join(f"`{m}`" for m in matches)
                            )
                            active_games.pop(interaction.channel_id, None)
                            return

                        # reveal another letter
                        unrev = [i for i in range(len(word)) if i not in revealed and word[i] != ' ']
                        if unrev:
                            revealed.add(random.choice(unrev))
                        hint = get_hint(word, revealed)
                        await channel.send(f"🔎 Hint {hint_count}: ```{display_hint(hint)}```")

        except Exception as e:
            print(f"❗ Error in continuous GTB: {e}")
            active_games.pop(interaction.channel_id, None)
            await channel.send("⚠️ Something went wrong. The game has ended.")

async def setup(bot: commands.Bot):
    await bot.add_cog(GameCog(bot), guild=guild)

