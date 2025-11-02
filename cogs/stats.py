import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from utils.stats_store import get_stats
from utils.word_loader import POLISH_ALPHABET
from config import guild

def en_letter(li: int) -> str:
    return chr(ord('a') + li) if 0 <= li < 26 else '?'

def pl_letter(li: int) -> str:
    return POLISH_ALPHABET[li] if 0 <= li < len(POLISH_ALPHABET) else '?'

def human_record(entry: dict, lang: str) -> str:
    rec = entry.get("record", {})
    val = int(rec.get("value", 0) or 0)
    if val <= 0:
        return "(no record yet)"
    when = rec.get("updated_at", "")
    last_pos = rec.get("last_pos")
    last_li  = rec.get("last_li")
    if last_pos is not None and last_li is not None:
        L = en_letter(last_li) if lang == "en" else pl_letter(last_li)
        # last_pos is 0-based; show 1-based for humans
        return f"through pos {last_pos+1}, letter '{L}' (streak {val}; updated {when})"
    return f"streak {val} (updated {when})"

def human_reps(entry: dict, lang: str, max_items: int = 6) -> str:
    reps = entry.get("reps", {})
    if not reps:
        return "–"
    items = []
    for key, count in reps.items():
        try:
            p_str, li_str = key.split("-", 1)
            p = int(p_str) + 1  # human 1-indexed position
            li = int(li_str)
        except Exception:
            continue
        L = en_letter(li) if lang == "en" else pl_letter(li)
        items.append((count, p, L))
    # sort by count desc, then pos asc, then letter asc
    items.sort(key=lambda t: (-t[0], t[1], t[2]))
    shown = [f"pos {p}, '{L}' → {c}x" for c, p, L in items[:max_items]]
    extra = len(items) - max_items
    return "; ".join(shown) + (f"; +{extra} more" if extra > 0 else "")

class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="stats",
        description="Show memorize progress: best record endpoint and per-letter repetitions."
    )
    @app_commands.describe(user="Optional user to query (defaults to you)")
    async def stats(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user
        data = await get_stats(target.id)

        if not data:
            await interaction.followup.send(f"📊 No stats yet for {target.mention}.")
            return

        def render_lang(lang_key: str, title: str):
            lang_map = data.get(lang_key, {})
            if not lang_map:
                return f"**{title}**: *(no progress yet)*"
            lines = [f"**{title}**:"]
            for length_str, entry in sorted(lang_map.items(), key=lambda kv: int(kv[0])):
                rec = human_record(entry, lang_key)
                rep = human_reps(entry, lang_key)
                lines.append(
                    f"- {length_str} letters\n"
                    f"  • record: {rec}\n"
                    f"  • repetitions: {rep}"
                )
            return "\n".join(lines)

        msg = "\n\n".join([
            render_lang("en", "English"),
            render_lang("pl", "Polish"),
        ])
        await interaction.followup.send(f"📊 Progress for {target.mention}:\n{msg}")

async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot), guild=guild)
