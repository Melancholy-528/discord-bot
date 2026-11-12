"""Profiles bot features."""

from bot_state import (
    asyncio, bot, discord, get_guild_stats, get_member_stats,
    intents, io, member_activity_text, render_info_card,
)


@bot.hybrid_command(name="fetch", description="Show a user's avatar and, when available, banner")
async def fetch(ctx, user: discord.User = None):
    if ctx.interaction:
        await ctx.defer(thinking=True)
    user = user or ctx.author
    try:
        user = await bot.fetch_user(user.id)
    except discord.HTTPException:
        pass
    embed = discord.Embed(title=f"{user}'s profile", color=discord.Color.blurple())
    embed.set_image(url=user.display_avatar.url)
    if user.banner:
        embed.set_thumbnail(url=user.banner.url)
        embed.add_field(name="Banner", value=f"[Open banner]({user.banner.url})")
    else:
        embed.add_field(name="Banner", value="This user has no profile banner visible to the bot.")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="ping", description="Check the bot's response latency")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Gateway latency: **{bot.latency * 1000:.0f} ms**.")

@bot.hybrid_command(name="serverinfo", description="Show details about this server")
async def serverinfo(ctx):
    if not ctx.guild:
        await ctx.send("This command works in a server.")
        return
    if ctx.interaction:
        await ctx.defer(thinking=True)
    guild = ctx.guild
    members = guild.members
    humans = sum(not member.bot for member in members)
    bots = sum(member.bot for member in members)
    online = sum(member.status in {discord.Status.online, discord.Status.idle, discord.Status.dnd} for member in members)
    tracked_messages, reactions_given, reactions_received = get_guild_stats(guild.id)
    facts = [
        ("Owner", str(guild.owner) if guild.owner else "Unavailable"),
        ("Members", f"{guild.member_count or len(members)} · {humans} people · {bots} bots"),
        ("Currently online", f"{online} cached members" if intents.presences else "Presence Intent disabled"),
        ("Created", guild.created_at.strftime("%d %b %Y")),
        ("Channels", f"{len(guild.text_channels)} text · {len(guild.voice_channels)} voice · {len(guild.categories)} categories"),
        ("Community", f"{len(guild.roles) - 1} roles · {len(guild.emojis)} emojis · {len(guild.stickers)} stickers"),
        ("Boosts", f"Tier {guild.premium_tier} · {guild.premium_subscription_count or 0} boosts"),
        ("Tracked activity", f"{tracked_messages} messages · {reactions_given} reacts given · {reactions_received} received"),
    ]
    icon = None
    if guild.icon:
        try:
            icon = await guild.icon.read()
        except discord.HTTPException:
            pass
    card_bytes = await asyncio.to_thread(render_info_card, guild.name, f"Server ID {guild.id}", facts, icon, (104, 142, 255), "SERVER PROFILE")
    file = discord.File(io.BytesIO(card_bytes), filename="server-info.png")
    embed = discord.Embed(title=f"{guild.name} · server details", color=discord.Color.blurple())
    embed.description = f"**{guild.member_count or len(members)} members** · {online} online · **{tracked_messages}** tracked messages and **{reactions_given}** tracked reactions given."
    embed.set_image(url="attachment://server-info.png")
    embed.set_footer(text="Activity and counts are tracked from when this bot's stats database was created.")
    await ctx.send(embed=embed, file=file)

@bot.hybrid_command(name="userinfo", description="Show details about a server member")
async def userinfo(ctx, member: discord.Member = None):
    if not ctx.guild:
        await ctx.send("This command works in a server.")
        return
    if ctx.interaction:
        await ctx.defer(thinking=True)
    member = member or ctx.author
    messages, reactions_given, reactions_removed, reactions_received = get_member_stats(ctx.guild.id, member.id)
    roles = [role.name for role in reversed(member.roles) if role != ctx.guild.default_role]
    voice = member.voice.channel.name if member.voice and member.voice.channel else "Not in voice"
    boost = member.premium_since.strftime("%d %b %Y") if member.premium_since else "Not boosting"
    activity = member_activity_text(member) if intents.presences else "Enable Presence Intent in bot settings"
    facts = [
        ("Account ID", str(member.id)),
        ("Current activity", activity),
        ("Account created", member.created_at.strftime("%d %b %Y")),
        ("Joined this server", member.joined_at.strftime("%d %b %Y") if member.joined_at else "Unknown"),
        ("Messages tracked", f"{messages:,} since tracking started"),
        ("Reactions", f"{reactions_given:,} given · {reactions_received:,} received · {reactions_removed:,} removed"),
        ("Roles", ", ".join(roles[-5:]) or "No roles"),
        ("Voice / boost", f"{voice} · {boost}"),
    ]
    avatar = None
    try:
        avatar = await member.display_avatar.read()
    except discord.HTTPException:
        pass
    accent = (member.color.r, member.color.g, member.color.b) if member.color.value else (117, 94, 245)
    card_bytes = await asyncio.to_thread(render_info_card, str(member), f"Member in {ctx.guild.name}", facts, avatar, accent, "MEMBER PROFILE")
    file = discord.File(io.BytesIO(card_bytes), filename="user-info.png")
    embed = discord.Embed(title=f"{member} · member profile", color=member.color if member.color.value else discord.Color.blurple())
    embed.description = f"**{activity}**\n{messages:,} messages · {reactions_given:,} reacts given · {reactions_received:,} received"
    embed.set_image(url="attachment://user-info.png")
    embed.set_footer(text="Message and reaction counts are tracked from when the bot started recording them.")
    await ctx.send(embed=embed, file=file)
