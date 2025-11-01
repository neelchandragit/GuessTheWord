import discord
from discord.ext import commands
from config import intents, guild, DISCORD_TOKEN, GUILD_ID, OWNER_ID

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self):
        # Load your cogs
        await self.load_extension("cogs.gtb")
        await self.load_extension("cogs.memorize_all_en")
        await self.load_extension("cogs.memorize_all_pl")
        await self.load_extension("cogs.memorize_random_en")
        await self.load_extension("cogs.memorize_random_pl")
        await self.load_extension("cogs.stats")
        # Fast guild-only sync
        await self.tree.sync(guild=guild)
        print(f"✅ Slash commands synced to guild {GUILD_ID}")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message):
        # Let command framework process normal commands if you add any later
        await self.process_commands(message)
        if message.author.bot:
            return

        # Simple shutdown control (optional)
        if message.content.strip().lower() == "shutdownbot":
            if OWNER_ID and message.author.id != OWNER_ID:
                await message.channel.send("❌ You are not authorized to shut down the bot.")
                return
            await message.channel.send("⏹️ Shutting down the bot…")
            await self.close()

def main():
    bot = MyBot()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()

