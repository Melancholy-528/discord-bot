"""Community bot features."""

from bot_state import (
    active_reminders, app_commands, asyncio, bot, datetime,
    deliver_reminder, discord, next_reminder_id, parse_duration, send_private,
    timedelta, timezone,
)


@bot.hybrid_command(name="poll", description="Create a reaction poll with two to four choices")
@app_commands.describe(question="Poll question", option1="First option", option2="Second option", option3="Optional third option", option4="Optional fourth option")
async def poll(ctx, question: str, option1: str, option2: str, option3: str = "", option4: str = ""):
    options = [option[:100] for option in (option1, option2, option3, option4) if option.strip()]
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    embed = discord.Embed(title="📊 Poll", description=question[:250], color=discord.Color.blurple())
    embed.add_field(name="Choices", value="\n".join(f"{emojis[index]} {discord.utils.escape_mentions(option)}" for index, option in enumerate(options)))
    embed.set_footer(text=f"Poll by {ctx.author.display_name} · React to vote")
    message = await ctx.send(embed=embed)
    for emoji in emojis[:len(options)]:
        await message.add_reaction(emoji)

@bot.hybrid_command(name="suggest", description="Post a suggestion for the server")
async def suggest(ctx, *, suggestion: str):
    suggestion = suggestion.strip()
    if not suggestion:
        await ctx.send("Write a suggestion first.")
        return
    embed = discord.Embed(title="💡 Server suggestion", description=discord.utils.escape_mentions(suggestion[:1800]), color=discord.Color.gold())
    embed.set_footer(text=f"Suggested by {ctx.author.display_name}")
    message = await ctx.send(embed=embed)
    await message.add_reaction("👍")
    await message.add_reaction("👎")

@bot.hybrid_command(name="remindme", description="Send yourself a reminder later")
@app_commands.describe(duration="Examples: 30s, 10m, 2h, 1d", text="What should I remind you about?")
async def remindme(ctx, duration: str, *, text: str):
    global next_reminder_id
    try:
        seconds = parse_duration(duration)
    except ValueError as error:
        await send_private(ctx, str(error))
        return
    reminder_id = next_reminder_id
    next_reminder_id += 1
    active_reminders[reminder_id] = {
        "user_id": ctx.author.id,
        "channel_id": ctx.channel.id,
        "seconds": seconds,
        "text": text[:500],
        "due": datetime.now(timezone.utc) + timedelta(seconds=seconds),
        "task": None,
    }
    active_reminders[reminder_id]["task"] = asyncio.create_task(deliver_reminder(reminder_id))
    due = int(active_reminders[reminder_id]["due"].timestamp())
    await send_private(ctx, f"Reminder **#{reminder_id}** set for <t:{due}:R>. I'll DM you when it's due.")

@bot.hybrid_command(name="reminders", description="List your active reminders")
async def reminders(ctx):
    mine = [(reminder_id, item) for reminder_id, item in active_reminders.items() if item["user_id"] == ctx.author.id]
    if not mine:
        await send_private(ctx, "You don't have any active reminders.")
        return
    lines = [f"**#{reminder_id}** · <t:{int(item['due'].timestamp())}:R> · {discord.utils.escape_mentions(item['text'])}" for reminder_id, item in mine[:20]]
    await send_private(ctx, "\n".join(lines))

@bot.hybrid_command(name="cancelreminder", description="Cancel one of your reminders")
@app_commands.describe(reminder_id="The reminder number shown by /reminders")
async def cancelreminder(ctx, reminder_id: int):
    reminder = active_reminders.get(reminder_id)
    if not reminder or reminder["user_id"] != ctx.author.id:
        await send_private(ctx, "I couldn't find one of your active reminders with that number.")
        return
    reminder["task"].cancel()
    active_reminders.pop(reminder_id, None)
    await send_private(ctx, f"Cancelled reminder **#{reminder_id}**.")
