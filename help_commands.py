"""Help Commands bot features."""

from bot_state import (
    bot, discord,
)

from events import snipe

@bot.hybrid_command(name="help", description="Show this bot's commands")
async def help_command(ctx):
    embed = discord.Embed(title="Bot commands", color=discord.Color.blurple())
    embed.description = "Use slash commands or prefix them with `!` (legacy `$` also works)."
    embed.add_field(name="Community", value="`poll` · `suggest` · `remindme` · `reminders` · `cancelreminder`", inline=False)
    embed.add_field(name="Server info", value="`ping` · `serverinfo` · `userinfo` · `fetch` · `games` · `duel`", inline=False)
    embed.add_field(name="Moderation", value="`purge` · `warn` · `warnings` · `clearwarnings` · `snipe`", inline=False)
    embed.add_field(name="Music", value="`play` · `add` · `queue` · `nowplaying` · `skip` · `previous` · `pause` · `resume` · `stop` · `seek` · `back` · `forward` · `volume` · `shuffle` · `remove` · `clearqueue` · `loop`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="catch")
async def catch(ctx):
    await snipe(ctx)
