"""Events bot features."""

from bot_state import (
    afk_users, bot, datetime, discord, generate_sarcastic_reply,
    profanity, sniped_messages, stats_db, timezone,
)


@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    content = (message.content or "").strip()
    if not content:
        return

    if not profanity.contains_profanity(content):
        return

    sniped_messages[message.channel.id] = {
        "author_name": str(message.author),
        "author_avatar": message.author.display_avatar.url,
        "content": content,
        "channel_id": message.channel.id,
        "created_at": message.created_at,
        "deleted_at": datetime.now(timezone.utc)
    }

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.guild:
        stats_db.execute(
            "INSERT INTO member_stats(guild_id,user_id,messages) VALUES(?,?,1) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET messages=messages+1",
            (message.guild.id, message.author.id),
        )
        stats_db.execute(
            "INSERT OR REPLACE INTO tracked_messages(message_id,guild_id,author_id) VALUES(?,?,?)",
            (message.id, message.guild.id, message.author.id),
        )
        stats_db.commit()

    # Clear AFK when the user speaks, and let people know when they mention
    # someone who is away.
    if message.guild:
        author_key = (message.guild.id, message.author.id)
        if author_key in afk_users:
            afk_users.pop(author_key, None)
            await message.reply("welcome back! your AFK status is cleared ✨", mention_author=False, delete_after=10)
        for mentioned in message.mentions:
            afk = afk_users.get((message.guild.id, mentioned.id))
            if afk:
                await message.channel.send(
                    f"{mentioned.mention} is AFK: {discord.utils.escape_mentions(afk)}",
                    allowed_mentions=discord.AllowedMentions(users=[message.author]),
                    delete_after=10,
                )

    if bot.user.mentioned_in(message):
        cleaned = message.content.replace(f"<@{bot.user.id}>", "")
        cleaned = cleaned.replace(f"<@!{bot.user.id}>", "")
        cleaned = cleaned.strip()

        if not cleaned:
            await message.reply(
                "you pinged me for absolutely nothing",
                mention_author=False
            )
        else:
            reply = await generate_sarcastic_reply(cleaned)
            await message.reply(reply, mention_author=False)

    await bot.process_commands(message)

async def track_reaction(payload, stat_column):
    if payload.guild_id is None or payload.user_id == bot.user.id:
        return
    member = getattr(payload, "member", None) or bot.get_user(payload.user_id)
    if member and member.bot:
        return
    if stat_column not in {"reactions_added", "reactions_removed"}:
        return
    stats_db.execute(
        f"INSERT INTO member_stats(guild_id,user_id,{stat_column}) VALUES(?,?,1) "
        f"ON CONFLICT(guild_id,user_id) DO UPDATE SET {stat_column}={stat_column}+1",
        (payload.guild_id, payload.user_id),
    )
    row = stats_db.execute("SELECT author_id FROM tracked_messages WHERE message_id=?", (payload.message_id,)).fetchone()
    if stat_column == "reactions_added" and row and row[0] != payload.user_id:
        stats_db.execute(
            "INSERT INTO member_stats(guild_id,user_id,reactions_received) VALUES(?,?,1) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET reactions_received=reactions_received+1",
            (payload.guild_id, row[0]),
        )
    stats_db.commit()

@bot.event
async def on_raw_reaction_add(payload):
    await track_reaction(payload, "reactions_added")

@bot.event
async def on_raw_reaction_remove(payload):
    await track_reaction(payload, "reactions_removed")

@bot.hybrid_command(name="snipe", description="Snipe the latest deleted message that tripped the profanity filter")
async def snipe(ctx):
    data = sniped_messages.get(ctx.channel.id)

    if not data:
        await ctx.send("useless ping, no messages to snipe")
        return

    embed = discord.Embed(
        title="Caught in 4K 💀",
        description=data["content"],
        color=discord.Color.red(),
        timestamp=data["deleted_at"]
    )

    embed.set_author(
        name=data["author_name"],
        icon_url=data["author_avatar"]
    )

    embed.add_field(
        name="Channel",
        value=ctx.channel.mention,
        inline=True
    )

    embed.add_field(
        name="Deleted at",
        value=f"<t:{int(data['deleted_at'].timestamp())}:R>",
        inline=True
    )

    await ctx.send(embed=embed)

@bot.hybrid_command(name="afk", description="Set or clear your AFK status")
async def afk(ctx, *, reason: str = "AFK"):
    if not ctx.guild:
        await ctx.send("AFK status works in servers.", delete_after=10)
        return
    if reason.strip().lower() in {"off", "clear", "back"}:
        afk_users.pop((ctx.guild.id, ctx.author.id), None)
        await ctx.send("welcome back! your AFK status is cleared ✨", delete_after=10)
        return
    afk_users[(ctx.guild.id, ctx.author.id)] = reason[:200]
    await ctx.send(f"{ctx.author.mention} is now AFK: {discord.utils.escape_mentions(reason[:200])}", delete_after=10)
    if ctx.interaction is None:
        await ctx.message.add_reaction("💤")
