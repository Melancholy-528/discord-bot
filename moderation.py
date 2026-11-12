"""Moderation bot features."""

from bot_state import (
    app_commands, bot, datetime, discord, send_private,
    timezone, warnings_by_guild,
)


@bot.hybrid_command(name="purge", description="Delete recent messages from this channel")
@app_commands.describe(amount="How many recent messages to remove (1–100)")
async def purge(ctx, amount: int):
    if not ctx.guild or not ctx.author.guild_permissions.manage_messages:
        await send_private(ctx, "You need Manage Messages permission to use this command.")
        return
    if amount < 1 or amount > 100:
        await send_private(ctx, "Choose an amount from 1 to 100.")
        return
    if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
        await send_private(ctx, "I need Manage Messages permission in this channel.")
        return
    if ctx.interaction:
        await ctx.defer(ephemeral=True)
    try:
        extra = 0 if ctx.interaction else 1
        deleted = await ctx.channel.purge(limit=amount + extra)
        count = max(0, len(deleted) - extra)
        if ctx.interaction:
            await ctx.send(f"Deleted {count} message{'s' if count != 1 else ''}.", ephemeral=True)
        else:
            await ctx.send(f"Deleted {count} message{'s' if count != 1 else ''}.", delete_after=5)
    except discord.Forbidden:
        await send_private(ctx, "I don't have permission to delete messages here.")

@bot.hybrid_command(name="warn", description="Record a moderation warning for a member")
@app_commands.describe(member="Member to warn", reason="Why they are receiving a warning")
async def warn(ctx, member: discord.Member, *, reason: str):
    if not ctx.guild or not (ctx.author.guild_permissions.manage_messages or ctx.author.guild_permissions.moderate_members):
        await send_private(ctx, "You need Manage Messages or Moderate Members permission to warn members.")
        return
    if member.bot or member.id == ctx.author.id or member.id == ctx.guild.owner_id:
        await send_private(ctx, "That member can't be warned with this command.")
        return
    if ctx.author.id != ctx.guild.owner_id and member.top_role >= ctx.author.top_role:
        await send_private(ctx, "You can't warn a member with an equal or higher role.")
        return
    if ctx.guild.me and member.top_role >= ctx.guild.me.top_role:
        await send_private(ctx, "My role must be higher than the member's role to record this warning.")
        return
    key = (ctx.guild.id, member.id)
    entries = warnings_by_guild.setdefault(key, [])
    entries.append({"reason": reason[:500], "moderator": ctx.author.id, "at": datetime.now(timezone.utc)})
    try:
        await member.send(f"You received a warning in **{ctx.guild.name}**: {discord.utils.escape_mentions(reason[:500])}")
    except discord.Forbidden:
        pass
    await ctx.send(f"⚠️ Recorded warning **#{len(entries)}** for {member.mention}.")

@bot.hybrid_command(name="warnings", description="Show recorded warnings for a member")
async def warnings(ctx, member: discord.Member):
    if not ctx.guild:
        await ctx.send("Warnings are server-specific.")
        return
    entries = warnings_by_guild.get((ctx.guild.id, member.id), [])
    if not entries:
        await ctx.send(f"{member.mention} has no recorded warnings.")
        return
    lines = [f"**{index}.** {discord.utils.escape_mentions(item['reason'])} · <t:{int(item['at'].timestamp())}:d> · moderator <@{item['moderator']}>" for index, item in enumerate(entries[-10:], max(1, len(entries) - 9))]
    embed = discord.Embed(title=f"Warnings for {member}", description="\n".join(lines), color=discord.Color.orange())
    embed.set_footer(text=f"{len(entries)} total · in-memory (reset when bot restarts)")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="clearwarnings", description="Clear recorded warnings for a member")
async def clearwarnings(ctx, member: discord.Member):
    if not ctx.guild or not (ctx.author.guild_permissions.manage_messages or ctx.author.guild_permissions.moderate_members):
        await send_private(ctx, "You need Manage Messages or Moderate Members permission to clear warnings.")
        return
    count = len(warnings_by_guild.pop((ctx.guild.id, member.id), []))
    await ctx.send(f"Cleared {count} warning{'s' if count != 1 else ''} for {member.mention}.")
