import os
import discord

# --- Configure these via environment or hardcode if you prefer ---
DISCORD_TOKEN = "MTQwNjEyNDI3NDAxNTY2NjIzNw.GhI_sy.3f2OYRmt1Ak1ySuArxnBa8svzdvy8Mn61PLePI"
GUILD_ID = int(os.getenv("GUILD_ID", "1406114268696281121"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # optional

# Path to your data/words.json (you can switch it via env if needed)
WORDS_JSON = os.getenv("WORDS_JSON", os.path.join("data", "words.json"))

# --- Discord / shared state ---
intents = discord.Intents.default()
intents.message_content = True

guild = discord.Object(id=GUILD_ID)

# Per-channel guards to prevent overlapping sessions
active_games: dict[int, bool] = {}

if not DISCORD_TOKEN:
    # Don't crash hard—just warn in console. You'll get a clear error when bot runs.
    print("[WARN] DISCORD_TOKEN is empty. Set env var DISCORD_TOKEN before running the bot.")

