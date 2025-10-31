# Guess The Word – Discord Bot

## Setup
1. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
2. `pip install discord.py python-dotenv`  *(dotenv optional—see below)*
3. Put your words at `data/words.json` (or set `WORDS_JSON` env var).
4. Set environment variables:
   - `DISCORD_TOKEN=...`
   - `GUILD_ID=...`
   - (optional) `OWNER_ID=...`
5. Run: `python bot.py`

## Commands
- `/gtb [difficulty]` — continuous game (`easy|medium|hard|normal`)
- `/memorize_all length:<int> [start_hint]` — English cycle mode
- `/memorize_pl length:<int> [start_hint]` — Polish cycle mode

### Admin
Type `shutdownbot` in a channel to stop the bot (if `OWNER_ID` is set, only that user can stop it).

