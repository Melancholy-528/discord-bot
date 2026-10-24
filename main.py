import discord
import atexit
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from better_profanity import profanity
import os
import random
import math
import asyncio
import tempfile
import shutil
import re
import io
import struct
import sqlite3
import yt_dlp
import imageio_ffmpeg
from collections import deque
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont, ImageOps

load_dotenv()

token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True
intents.presences = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!", "$"), intents=intents, help_command=None)
afk_users = {}

sniped_messages = {}
warnings_by_guild = {}
active_reminders = {}
next_reminder_id = 1
stats_db = sqlite3.connect("bot_stats.sqlite3", check_same_thread=False)
stats_db.execute("PRAGMA journal_mode=WAL")
stats_db.execute("""CREATE TABLE IF NOT EXISTS member_stats (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    messages INTEGER NOT NULL DEFAULT 0,
    reactions_added INTEGER NOT NULL DEFAULT 0,
    reactions_removed INTEGER NOT NULL DEFAULT 0,
    reactions_received INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)""")
stats_db.execute("""CREATE TABLE IF NOT EXISTS tracked_messages (
    message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, author_id INTEGER NOT NULL
)""")
stats_db.commit()

custom_words = [
    "simp", "incel", "virgin", "beta", "douchebag", "dickhead", "asshole",
    "bitch", "fuckboy", "slut", "whore", "cunt", "faggot", "chud", "fuck",
    "crack", "weirdo", "loser", "trash", "garbage", "stupid", "idiot", "dumb",
    "suck", "sucks", "sucked", "sucking", "suck my", "suck a", "suck the",
    "suck on", "suck it", "eat my", "eat a", "eat the", "eat your", "eat that",
    "eat this", "lick my", "lick a", "lick the", "lick your", "lick that",
    "lick this", "blow my", "blow a", "blow the", "blow your", "blow that",
    "blow this", "cum", "cummy", "cummies", "cumming", "cums", "cummed",
    "cumming on", "cumming a", "cumming the", "cumming your", "cumming that",
    "cumming this", "nut", "nuts", "nutted", "nutting", "nut on", "nut a",
    "nut the", "nut your", "nut that", "nut this", "pussy", "pussylicker",
    "pussylicking", "pussylicked", "pussylicks", "pussy eat", "pussy eating",
    "pussy eaten", "pussy eat that", "pussy eat this", "pussy eat a",
    "pussy eat the", "pussy eat your"
]

profanity.load_censor_words(custom_words)

SARCASM_BANK = [
    "yeah that’s not how reality works but go off",
    "i respect the confidence, not the idea",
    "that statement just lowered my iq a bit",
    "i know what you meant but i’m choosing to ignore it",
    "bro said that like it made sense",
    "interesting take, unfortunately it’s wrong",
    "i’ve seen better logic in a dream",
    "that’s a bold claim for someone so incorrect",
    "you really typed that and hit send huh",
    "i refuse to believe you thought that through",
    "that’s enough internet for today honestly",
    "you might wanna re-evaluate everything you just said",
    "i hear you but i’m pretending i don’t",
    "that sentence felt illegal to read",
    "somehow that made things worse",
    "i’m not mad, just disappointed in the universe",
    "that’s not it chief",
    "you’re speaking but nothing is loading upstairs",
    "i’d agree but then we’d both be wrong",
    "that’s a creative way to be incorrect",
    "you cooked… and burned the kitchen down",
    "this is why aliens don’t talk to us",
    "i lost braincells reading that",
    "you really chose violence against logic",
    "that’s a certified bruh moment",
    "i’m gonna pretend i didn’t see that",
    "that’s not how any of this works",
    "you said that with full confidence too 💀",
    "i can’t tell if you’re joking or just built different (in a bad way)",
    "that idea needs to stay in drafts",
    "i’ve heard better arguments from a toaster",
    "you just typed nonsense in HD",
    "that’s wild coming from you",
    "this is why we can’t have nice things",
    "you might be onto nothing",
    "that’s a skill issue in sentence form",
    "i’m legally required to ignore that",
    "you really thought you did something there",
    "that’s not a take, that’s a detour from reality",
    "i’d explain why that’s wrong but we’d be here all day",
    "your logic left the chat immediately",
    "that statement has no business existing",
    "i’m concerned for your thought process",
    "you just speedran being incorrect",
    "that’s the kind of message you delete after sending",
    "i feel dumber after reading that",
    "you typed that like it was a fact 😭",
    "that’s not a conclusion, that’s a cry for help",
    "i’m not equipped to handle this level of confusion",
    "that’s enough internet for you today",
    "you really woke up and chose confusion",
    "that message violated common sense",
    "i’m sending that back to sender",
    "that’s a creative disaster",
    "you should probably not say that again",
    "this is why aliens avoid Earth"
]

async def generate_sarcastic_reply(user_message: str):
    base = random.choice(SARCASM_BANK)
    extra_twist = random.choice([
        "",
        " anyway...",
        " bro.",
        " 😭",
        " i’m done here.",
        " please rethink that."
    ])
    return base + extra_twist

@bot.tree.error
async def on_app_command_error(interaction, error):
    original = getattr(error, "original", error)
    logging.error(
        "Slash command %s failed: %s",
        getattr(interaction.command, "name", "unknown"), original,
        exc_info=(type(original), original, original.__traceback__),
    )
    message = "That command ran into an error. Please try again; the bot logged the details."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        logging.exception("Could not send the slash-command error response")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        command_name = ctx.command.qualified_name if ctx.command else "command"
        if command_name == "purge":
            message = "Usage: `!purge <amount>` — choose how many messages to delete (1–100)."
        else:
            message = f"Missing a required argument. Use `!help` to see command examples."
        await ctx.send(message, delete_after=12)
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("I couldn't understand one of those arguments. Check the command options and try again.", delete_after=12)
        return
    logging.error("Prefix command failed", exc_info=(type(error), error, error.__traceback__))
    try:
        await ctx.send("That command ran into an error. Please try again.", delete_after=12)
    except discord.HTTPException:
        pass


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    try:
        dev_guild_id = os.getenv("DEV_GUILD_ID")
        if dev_guild_id:
            guild = discord.Object(id=int(dev_guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to development guild {dev_guild_id}")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} global slash commands")
    except Exception as error:
        print(f"Slash command sync failed: {error}")


def parse_duration(value: str) -> int:
    pattern = re.compile(r"(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)", re.IGNORECASE)
    parts = list(pattern.finditer(value))
    leftover = pattern.sub("", value).replace(",", "").strip()
    if not parts or leftover:
        raise ValueError("Use a duration such as 30s, 10m, 2h, or 1d.")
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    seconds = sum(int(part.group(1)) * multipliers[part.group(2).lower()[0]] for part in parts)
    if seconds < 5 or seconds > 30 * 86400:
        raise ValueError("Reminders must be at least 5 seconds and no more than 30 days away.")
    return seconds


async def send_private(ctx, message):
    if ctx.interaction:
        await ctx.send(message, ephemeral=True)
    else:
        await ctx.send(message)


def load_card_font(size, bold=False):
    paths = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
        if bold else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit_text(draw, text, font, max_width):
    """Trim a single line to fit a card column."""
    text = str(text)
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap_card_text(draw, text, font, max_width, max_lines=3):
    words = str(text).replace("\n", " ").split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit_text(draw, lines[-1] + "…", font, max_width)
    return lines


def render_info_card(title, subtitle, facts, avatar_bytes=None, accent=(117, 94, 245), eyebrow="PROFILE"):
    width, height = 1400, 900
    image = Image.new("RGB", (width, height), (250, 249, 245))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        blend = y / height
        color = (int(255 - 5 * blend), int(253 - 3 * blend), int(246 + 5 * blend))
        draw.line((0, y, width, y), fill=color)
    draw.ellipse((980, -320, 1510, 210), fill=tuple(255 - (255 - c) // 10 for c in accent))
    draw.ellipse((-310, 660, 250, 1220), fill=(239, 244, 255))
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=38, fill=(255, 255, 255), outline=(232, 231, 224), width=2)
    draw.rounded_rectangle((25, 25, width - 25, 205), radius=36, fill=(250, 250, 255))
    draw.rectangle((25, 155, width - 25, 205), fill=(250, 250, 255))
    title_font = load_card_font(45, bold=True)
    sub_font = load_card_font(22)
    label_font = load_card_font(16, bold=True)
    value_font = load_card_font(25, bold=True)
    draw.rounded_rectangle((68, 57, 238, 91), radius=17, fill=accent)
    draw.text((84, 65), fit_text(draw, eyebrow, label_font, 140), font=label_font, fill=(255, 255, 255))
    draw.text((68, 106), fit_text(draw, title, title_font, 980), font=title_font, fill=(39, 45, 65))
    draw.text((70, 163), fit_text(draw, subtitle, sub_font, 980), font=sub_font, fill=(104, 113, 134))
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = ImageOps.fit(avatar, (122, 122), centering=(0.5, 0.5))
            mask = Image.new("L", (122, 122), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 121, 121), fill=255)
            image.paste(avatar, (width - 184, 63), mask)
            ImageDraw.Draw(image).ellipse((width - 188, 59, width - 58, 189), outline=accent, width=4)
            draw = ImageDraw.Draw(image)
        except Exception:
            pass

    columns = [facts[::2], facts[1::2]]
    max_rows = max((len(column) for column in columns), default=0)
    gap, card_w, card_h, start_y = 24, 630, 132, 230
    for column_index, entries in enumerate(columns):
        x = 60 + column_index * (card_w + gap)
        for row, (label, value) in enumerate(entries):
            y = start_y + row * (card_h + 18)
            if y + card_h > height - 88:
                break
            draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=22, fill=(250, 251, 255), outline=(226, 230, 239), width=1)
            draw.rounded_rectangle((x + 20, y + 20, x + 26, y + card_h - 20), radius=3, fill=accent)
            draw.text((x + 45, y + 22), fit_text(draw, str(label).upper(), label_font, card_w - 76), font=label_font, fill=(104, 113, 134))
            lines = wrap_card_text(draw, str(value).replace("\n", " · "), value_font, card_w - 76, max_lines=2)
            for line_index, line in enumerate(lines):
                draw.text((x + 45, y + 55 + line_index * 32), line, font=value_font, fill=(39, 45, 65))

    footer_y = min(height - 55, start_y + max_rows * (card_h + 18) + 2)
    draw.text((66, footer_y), "LIVE SERVER DATA  ·  BOT-TRACKED STATS BEGIN WHEN TRACKING WAS ENABLED", font=load_card_font(14, bold=True), fill=(104, 113, 134))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def get_member_stats(guild_id, user_id):
    row = stats_db.execute(
        "SELECT messages, reactions_added, reactions_removed, reactions_received FROM member_stats WHERE guild_id=? AND user_id=?",
        (guild_id, user_id),
    ).fetchone()
    return row or (0, 0, 0, 0)


def get_guild_stats(guild_id):
    row = stats_db.execute(
        "SELECT COALESCE(SUM(messages),0), COALESCE(SUM(reactions_added),0), COALESCE(SUM(reactions_received),0) FROM member_stats WHERE guild_id=?",
        (guild_id,),
    ).fetchone()
    return row or (0, 0, 0)


def member_activity_text(member):
    status = getattr(member.status, "name", str(member.status)).title()
    activities = []
    for activity in member.activities:
        name = getattr(activity, "name", None)
        detail = getattr(activity, "details", None) or getattr(activity, "state", None)
        if name and name != "Custom Status":
            activities.append(f"{name}: {detail}" if detail else name)
        elif detail:
            activities.append(str(detail))
    activity_text = ", ".join(activities[:2]) or "No activity visible"
    return f"{status} · {activity_text}"


async def deliver_reminder(reminder_id):
    reminder = active_reminders[reminder_id]
    try:
        await asyncio.sleep(reminder["seconds"])
        user = bot.get_user(reminder["user_id"])
        if user is None:
            user = await bot.fetch_user(reminder["user_id"])
        try:
            await user.send(f"⏰ Reminder: {discord.utils.escape_mentions(reminder['text'])}")
        except discord.Forbidden:
            channel = bot.get_channel(reminder["channel_id"])
            if channel:
                await channel.send(
                    f"{user.mention} ⏰ Reminder: {discord.utils.escape_mentions(reminder['text'])}",
                    allowed_mentions=discord.AllowedMentions(users=[user]),
                )
    except asyncio.CancelledError:
        raise
    except discord.HTTPException as error:
        logging.warning("Could not deliver reminder %s (%s)", reminder_id, type(error).__name__)
    finally:
        active_reminders.pop(reminder_id, None)

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


def render_game_card(game, headline, detail, avatar_bytes=None):
    width, height = 1280, 720
    accents = {
        "coin": (255, 189, 89), "dice": (101, 217, 185), "8ball": (169, 139, 255),
        "rps": (255, 111, 145), "rpsls": (255, 111, 145), "highlow": (96, 188, 255),
        "number": (255, 146, 95), "math": (119, 211, 255), "wyr": (255, 133, 204),
        "choose": (119, 224, 169),
    }
    accent = accents.get(game, (148, 132, 255))
    pale = tuple(255 - (255 - component) // 7 for component in accent)
    image = Image.new("RGB", (width, height), (249, 248, 243))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        amount = y / height
        color = (int(255 - 8 * amount), int(252 - 5 * amount), int(242 + 10 * amount))
        draw.line((0, y, width, y), fill=color)
    draw.ellipse((900, -250, 1430, 280), fill=pale)
    draw.ellipse((-210, 550, 190, 950), fill=(241, 244, 255))
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=38, fill=(255, 255, 255), outline=(232, 231, 224), width=2)
    draw.rounded_rectangle((25, 25, width - 25, 185), radius=36, fill=(255, 255, 255))
    draw.rectangle((25, 140, width - 25, 185), fill=(255, 255, 255))
    small = load_card_font(16, bold=True)
    title_font = load_card_font(30, bold=True)
    hero_font = load_card_font(66, bold=True)
    detail_font = load_card_font(27)
    dark = (39, 45, 65)
    muted = (104, 113, 134)
    draw.rounded_rectangle((62, 57, 183, 94), radius=18, fill=accent)
    draw.text((79, 67), "ARCADE", font=small, fill=(255, 255, 255))
    display_game = game.replace("8ball", "MAGIC 8-BALL").replace("rpsls", "RPSLS").replace("rps", "ROCK PAPER SCISSORS").replace("wyr", "WOULD YOU RATHER").upper()
    draw.text((62, 117), fit_text(draw, display_game, title_font, 740), font=title_font, fill=muted)
    draw.rounded_rectangle((62, 236, 75, 510), radius=7, fill=accent)
    wrapped_headline = wrap_card_text(draw, headline, hero_font, 710, max_lines=2)
    for index, line in enumerate(wrapped_headline):
        draw.text((105, 239 + index * 82), line, font=hero_font, fill=dark)
    detail_lines = wrap_card_text(draw, detail.replace("\n", " · "), detail_font, 690, max_lines=2)
    for index, line in enumerate(detail_lines):
        draw.text((107, 432 + index * 39), line, font=detail_font, fill=muted)

    # A bright illustration panel with art tailored to the selected mini-game.
    panel = (840, 218, 1197, 578)
    draw.rounded_rectangle(panel, radius=34, fill=pale)
    cx, cy = 1018, 398
    if game == "coin":
        # Gold coin face explicitly displays the side returned by the flip.
        draw.ellipse((cx - 113, cy - 101, cx + 113, cy + 125), fill=(221, 159, 43))
        draw.ellipse((cx - 111, cy - 112, cx + 111, cy + 110), fill=(255, 195, 54), outline=(221, 145, 27), width=8)
        draw.ellipse((cx - 91, cy - 92, cx + 91, cy + 91), outline=(255, 229, 126), width=5)
        # A simple embossed star gives the coin a readable emblem without emoji fonts.
        star_points = []
        for point in range(10):
            radius = 25 if point % 2 == 0 else 11
            angle = -math.pi / 2 + point * math.pi / 5
            star_points.append((cx + math.cos(angle) * radius, cy - 34 + math.sin(angle) * radius))
        draw.polygon(star_points, fill=(255, 236, 158))
        coin_label = "HEADS" if headline.lower().startswith("heads") else "TAILS"
        coin_font = load_card_font(25, bold=True)
        label_w = draw.textlength(coin_label, font=coin_font)
        draw.text((cx - label_w / 2, cy + 17), coin_label, font=coin_font, fill=(120, 75, 13))
    elif game == "dice":
        import re
        rolled = re.search(r"rolled (\d+)", headline, re.IGNORECASE)
        value = int(rolled.group(1)) if rolled else random.randint(1, 6)
        die = (cx - 88, cy - 88, cx + 88, cy + 88)
        draw.rounded_rectangle((die[0] + 9, die[1] + 12, die[2] + 9, die[3] + 12), radius=30, fill=(202, 89, 83))
        draw.rounded_rectangle(die, radius=30, fill=(255, 255, 255), outline=(225, 225, 231), width=3)
        pip_positions = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)],
                         4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
                         5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
                         6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
        if value <= 6:
            for px, py in pip_positions[value]:
                x, y = cx + px * 48, cy + py * 48
                draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(244, 91, 91))
        else:
            value_font = load_card_font(64, bold=True)
            text = str(value)
            draw.text((cx - draw.textlength(text, font=value_font) / 2, cy - 43), text, font=value_font, fill=(244, 91, 91))
    elif game == "8ball":
        draw.ellipse((cx - 113, cy - 113, cx + 113, cy + 113), fill=(34, 39, 56), outline=(21, 25, 37), width=5)
        draw.ellipse((cx - 65, cy - 65, cx + 65, cy + 65), fill=(255, 255, 255))
        text = "8"
        font = load_card_font(78, bold=True)
        draw.text((cx - draw.textlength(text, font=font) / 2, cy - 54), text, font=font, fill=(34, 39, 56))
    elif game in {"rps", "rpsls"}:
        for index, (label, color) in enumerate((("R", (255, 107, 107)), ("P", (80, 164, 255)), ("S", (117, 203, 135)))):
            x = 900 + index * 93
            draw.rounded_rectangle((x, 315, x + 76, 410), radius=22, fill=color)
            font = load_card_font(42, bold=True)
            draw.text((x + 38 - draw.textlength(label, font=font) / 2, 332), label, font=font, fill=(255, 255, 255))
            draw.text((x + 38 - draw.textlength(label, font=small) / 2, 430), label, font=small, fill=dark)
        draw.text((915, 484), "ROCK     PAPER     SCISSORS", font=load_card_font(12, bold=True), fill=muted)
    elif game == "highlow":
        import re
        cards = re.search(r"First card: (\d+) · next card: (\d+)", detail)
        values = cards.groups() if cards else ("7", "K")
        for index, value in enumerate(values):
            x = 907 + index * 112
            color = (232, 71, 87) if index else (46, 56, 76)
            draw.rounded_rectangle((x + 5, 300, x + 96, 493), radius=16, fill=(217, 216, 210))
            draw.rounded_rectangle((x, 292, x + 91, 485), radius=16, fill=(255, 255, 255), outline=(225, 226, 231), width=2)
            font = load_card_font(36, bold=True)
            draw.text((x + 16, 307), value, font=font, fill=color)
            draw.text((x + 19, 365), "♥" if color[0] > 150 else "♠", font=load_card_font(39, bold=True), fill=color)
    elif game == "number":
        import re
        match = re.search(r"number: (\d+)", detail)
        number = match.group(1) if match else "?"
        draw.ellipse((cx - 112, cy - 112, cx + 112, cy + 112), fill=(255, 143, 95))
        draw.ellipse((cx - 92, cy - 94, cx + 92, cy + 90), fill=(255, 174, 129))
        font = load_card_font(86, bold=True)
        draw.text((cx - draw.textlength(number, font=font) / 2, cy - 60), number, font=font, fill=(255, 255, 255))
    elif game == "math":
        draw.rounded_rectangle((900, 302, 1136, 481), radius=28, fill=(255, 255, 255), outline=(218, 231, 242), width=3)
        equation_font = load_card_font(38, bold=True)
        equation = fit_text(draw, headline.replace("?", "?"), equation_font, 200)
        draw.text((cx - draw.textlength(equation, font=equation_font) / 2, 365), equation, font=equation_font, fill=(62, 153, 224))
    elif game == "wyr":
        for index, (label, color) in enumerate((("A", (255, 133, 204)), ("B", (130, 125, 255)))):
            x = 900 + index * 120
            draw.rounded_rectangle((x, 300, x + 105, 490), radius=25, fill=color)
            font = load_card_font(66, bold=True)
            draw.text((x + 52 - draw.textlength(label, font=font) / 2, 350), label, font=font, fill=(255, 255, 255))
    else:
        star_points = []
        for point in range(10):
            radius = 118 if point % 2 == 0 else 55
            angle = -math.pi / 2 + point * math.pi / 5
            star_points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        draw.polygon(star_points, fill=(255, 200, 66), outline=(238, 154, 28))
        draw.text((cx - 13, cy - 25), "!", font=load_card_font(60, bold=True), fill=(255, 255, 255))

    draw.text((62, 615), "PLAY AGAIN ANYTIME  ·  GOOD LUCK", font=small, fill=muted)
    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = ImageOps.fit(avatar, (42, 42))
            mask = Image.new("L", (42, 42), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 41, 41), fill=255)
            image.paste(avatar, (62, 652), mask)
            draw.ellipse((60, 650, 104, 694), outline=accent, width=2)
            draw.text((117, 665), "PLAYER RESULT CARD", font=small, fill=muted)
        except Exception:
            pass
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


class MathAnswerView(discord.ui.View):
    def __init__(self, player_id, answer, options):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.answer = answer
        for option in options:
            button = discord.ui.Button(label=str(option), style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(option)
            self.add_item(button)

    def make_callback(self, option):
        async def callback(interaction):
            if interaction.user.id != self.player_id:
                await interaction.response.send_message("This round belongs to someone else.", ephemeral=True)
                return
            embed = interaction.message.embeds[0]
            embed.title = "Correct!" if option == self.answer else "Not quite!"
            embed.description = f"You chose **{option}**. The answer was **{self.answer}**."
            embed.color = discord.Color.green() if option == self.answer else discord.Color.red()
            await interaction.response.edit_message(embed=embed, view=None)
        return callback


class DuelInviteView(discord.ui.View):
    def __init__(self, challenger, opponent, game):
        super().__init__(timeout=120)
        self.challenger = challenger
        self.opponent = opponent
        self.game = game

    async def interaction_check(self, interaction):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                f"Only {self.opponent.mention} can answer this challenge.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", emoji="🎮", style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        if self.game == "tictactoe":
            view = TicTacToeView(self.challenger, self.opponent)
            embed = view.make_embed("It’s your turn, " + self.challenger.display_name + "!")
        else:
            view = RockPaperScissorsView(self.challenger, self.opponent)
            embed = view.make_embed()
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = interaction.message

    @discord.ui.button(label="Decline", emoji="✋", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction, button):
        await interaction.response.edit_message(
            content=f"{self.opponent.mention} declined the challenge.", embed=None, view=None
        )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="Challenge expired.", view=self)
            except discord.HTTPException:
                pass


class TicTacToeView(discord.ui.View):
    WIN_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7),
                 (2, 5, 8), (0, 4, 8), (2, 4, 6))

    def __init__(self, player_x, player_o):
        super().__init__(timeout=600)
        self.players = {"❌": player_x, "⭕": player_o}
        self.board = [None] * 9
        self.turn = "❌"
        self.finished = False
        self.message = None
        for position in range(9):
            button = discord.ui.Button(label="▫️", style=discord.ButtonStyle.secondary,
                                       row=position // 3)
            button.callback = self.make_move_callback(position, button)
            self.add_item(button)

    def make_embed(self, status):
        cells = [mark or "▫️" for mark in self.board]
        board = "\n".join("　".join(cells[row:row + 3]) for row in (0, 3, 6))
        embed = discord.Embed(title="⭕ Tic-tac-toe", description=board,
                              color=discord.Color.from_rgb(119, 211, 255))
        embed.add_field(name="Players", value=f"❌ {self.players['❌'].mention}\n⭕ {self.players['⭕'].mention}", inline=True)
        embed.add_field(name="Turn", value=status, inline=True)
        return embed

    def make_move_callback(self, position, button):
        async def callback(interaction):
            if self.finished:
                await interaction.response.send_message("This game has ended.", ephemeral=True)
                return
            if interaction.user.id != self.players[self.turn].id:
                await interaction.response.send_message("It’s not your turn.", ephemeral=True)
                return
            if self.board[position]:
                await interaction.response.send_message("That square is already taken.", ephemeral=True)
                return
            mark = self.turn
            self.board[position] = mark
            button.label = mark
            button.emoji = None
            button.style = discord.ButtonStyle.danger if mark == "❌" else discord.ButtonStyle.primary
            button.disabled = True
            winner = None
            for line in self.WIN_LINES:
                if all(self.board[index] == mark for index in line):
                    winner = mark
                    break
            if winner:
                self.finished = True
                for child in self.children:
                    child.disabled = True
                embed = self.make_embed(f"🏆 {self.players[winner].mention} wins!")
                embed.color = discord.Color.green()
            elif all(self.board):
                self.finished = True
                for child in self.children:
                    child.disabled = True
                embed = self.make_embed("🤝 It’s a draw!")
            else:
                self.turn = "⭕" if mark == "❌" else "❌"
                embed = self.make_embed(f"{self.players[self.turn].mention}, your move!")
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="This game expired.", view=self)
            except discord.HTTPException:
                pass


class RockPaperScissorsView(discord.ui.View):
    MOVES = ("rock", "paper", "scissors")
    EMOJIS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    def __init__(self, player_one, player_two):
        super().__init__(timeout=180)
        self.players = (player_one, player_two)
        self.choices = {}
        self.message = None
        for move, emoji in self.EMOJIS.items():
            button = discord.ui.Button(label=move.title(), emoji=emoji,
                                       style=discord.ButtonStyle.secondary)
            button.callback = self.make_choice_callback(move)
            self.add_item(button)

    def make_embed(self, status="Both players: choose your move (your choice stays hidden)."):
        embed = discord.Embed(title="✊ Rock, paper, scissors",
                              description=status, color=discord.Color.from_rgb(255, 111, 145))
        embed.add_field(name="Players", value=f"{self.players[0].mention} vs {self.players[1].mention}")
        return embed

    def make_choice_callback(self, move):
        async def callback(interaction):
            player_id = interaction.user.id
            if player_id not in {player.id for player in self.players}:
                await interaction.response.send_message("You aren’t playing this round.", ephemeral=True)
                return
            if player_id in self.choices:
                await interaction.response.send_message("Your move is already locked in.", ephemeral=True)
                return
            self.choices[player_id] = move
            if len(self.choices) < 2:
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send("Your move is locked in 🔒", ephemeral=True)
                await interaction.message.edit(embed=self.make_embed(
                    f"{interaction.user.mention} has locked in. Waiting for the other player…"), view=self)
                return

            first, second = self.players
            first_move, second_move = self.choices[first.id], self.choices[second.id]
            if first_move == second_move:
                result, color = "🤝 It’s a tie!", discord.Color.gold()
            elif (first_move, second_move) in (("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")):
                result, color = f"🏆 {first.mention} wins!", discord.Color.green()
            else:
                result, color = f"🏆 {second.mention} wins!", discord.Color.green()
            embed = self.make_embed(result)
            embed.add_field(name=first.display_name, value=self.EMOJIS[first_move], inline=True)
            embed.add_field(name=second.display_name, value=self.EMOJIS[second_move], inline=True)
            embed.color = color
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
        return callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="This round expired.", view=self)
            except discord.HTTPException:
                pass


@bot.hybrid_command(name="duel", description="Challenge someone to a two-player game")
@app_commands.describe(opponent="The server member you want to challenge", game="Pick a game")
@app_commands.choices(game=[
    app_commands.Choice(name="Tic-tac-toe", value="tictactoe"),
    app_commands.Choice(name="Rock paper scissors", value="rps"),
])
async def duel(ctx, opponent: discord.Member, game: str):
    if not ctx.guild:
        await ctx.send("Duel games can only be started in a server.")
        return
    if opponent.bot or opponent.id == ctx.author.id:
        await ctx.send("Choose another human server member to challenge.")
        return
    game_name = "tic-tac-toe" if game == "tictactoe" else "rock, paper, scissors"
    view = DuelInviteView(ctx.author, opponent, game)
    message = await ctx.send(
        f"🎮 {opponent.mention}, {ctx.author.mention} challenged you to **{game_name}**! "
        "Accept within 2 minutes to play.", view=view
    )
    view.message = message


@bot.hybrid_command(name="games", description="Play a game and get a custom result card")
@app_commands.describe(game="Choose a game", choice="Your pick or guess (varies by game)")
@app_commands.choices(game=[
    app_commands.Choice(name="Coin flip", value="coin"),
    app_commands.Choice(name="Dice roll", value="dice"),
    app_commands.Choice(name="Magic 8-ball", value="8ball"),
    app_commands.Choice(name="Rock paper scissors", value="rps"),
    app_commands.Choice(name="Rock paper scissors lizard Spock", value="rpsls"),
    app_commands.Choice(name="High or low", value="highlow"),
    app_commands.Choice(name="Number guess (1–10)", value="number"),
    app_commands.Choice(name="Quick math", value="math"),
    app_commands.Choice(name="Would you rather", value="wyr"),
    app_commands.Choice(name="Random picker", value="choose"),
])
async def games(ctx, game: str, choice: str = ""):
    # Acknowledge slash commands before validating inputs or rendering the card;
    # Discord expires unanswered interactions after a few seconds.
    await ctx.defer()
    headline, detail = "Game result", ""
    game_view = None
    reaction_choices = []
    if game == "coin":
        headline = random.choice(["Heads", "Tails"])
        detail = "The coin has spoken."
    elif game == "dice":
        sides = random.choice([6, 12, 20])
        headline = f"You rolled {random.randint(1, sides)}"
        detail = f"A d{sides} roll. Run it back for another one."
    elif game == "8ball":
        headline = random.choice(["Absolutely", "Ask again later", "The vibes say yes", "Not looking good", "It is certain", "Signs point to no"])
        detail = "The magic 8-ball has delivered its verdict."
    elif game in {"rps", "rpsls"}:
        moves = ["rock", "paper", "scissors"] if game == "rps" else ["rock", "paper", "scissors", "lizard", "spock"]
        if choice.lower() not in moves:
            await ctx.send(f"Pick one: {', '.join(moves)}")
            return
        bot_move = random.choice(moves)
        if choice.lower() == bot_move:
            outcome = "Tie game"
        else:
            defeats = {
                "rock": {"scissors", "lizard"}, "paper": {"rock", "spock"},
                "scissors": {"paper", "lizard"}, "lizard": {"paper", "spock"},
                "spock": {"rock", "scissors"},
            }
            outcome = "You win" if bot_move in defeats[choice.lower()] else "Bot wins"
        headline = outcome
        detail = f"You picked {choice.lower()} · bot picked {bot_move}"
    elif game == "highlow":
        first, second = random.randint(1, 13), random.randint(1, 13)
        if choice.lower() not in {"high", "low"}:
            await ctx.send("Choose **high** or **low** for your guess.")
            return
        won = (choice.lower() == "high" and second > first) or (choice.lower() == "low" and second < first)
        headline = "You got it!" if won else "Not this time"
        detail = f"First card: {first} · next card: {second} · you chose {choice.lower()}"
    elif game == "number":
        if not choice.isdigit() or not 1 <= int(choice) <= 10:
            await ctx.send("Guess a whole number from 1 to 10 in the choice field.")
            return
        answer = random.randint(1, 10)
        guess = int(choice)
        headline = "Bullseye!" if guess == answer else "Close one" if abs(guess - answer) <= 2 else "Missed it"
        detail = f"Your guess: {guess} · number: {answer}"
    elif game == "math":
        left, right = random.randint(2, 18), random.randint(2, 18)
        operation = random.choice(["+", "−", "×"])
        answer = left + right if operation == "+" else left - right if operation == "−" else left * right
        headline = f"{left} {operation} {right} = ?"
        detail = "Choose the answer below."
        answers = {answer}
        while len(answers) < 4:
            answers.add(answer + random.choice([i for i in range(-8, 9) if i != 0]))
        answer_options = list(answers)
        random.shuffle(answer_options)
        game_view = MathAnswerView(ctx.author.id, answer, answer_options)
    elif game == "wyr":
        options = random.choice([
            ("Speak every language", "Talk to animals"),
            ("Explore space", "Explore the deep sea"),
            ("Always be early", "Always have perfect timing"),
        ])
        picked = "A" if choice.lower() in {"a", "1"} else "B" if choice.lower() in {"b", "2"} else ""
        if not picked:
            headline = "Choose your side"
            reaction_choices = ["🅰️", "🅱️"]
        else:
            headline = f"You chose {picked}"
        detail = f"A: {options[0]} · B: {options[1]}"
    elif game == "choose":
        options = [item.strip() for item in choice.split(",") if item.strip()]
        if len(options) < 2:
            await ctx.send("Give me at least two comma-separated options in the choice field.")
            return
        headline = random.choice(options)[:42]
        detail = f"Picked from {len(options)} options"

    avatar = None
    try:
        avatar = await ctx.author.display_avatar.read()
    except discord.HTTPException:
        pass
    image_bytes = await asyncio.to_thread(render_game_card, game, headline, detail, avatar)
    file = discord.File(io.BytesIO(image_bytes), filename="game-result.png")
    embed = discord.Embed(title=f"{ctx.author.display_name} · {game}", description=detail, color=discord.Color.blurple())
    embed.set_image(url="attachment://game-result.png")
    message = await ctx.send(embed=embed, file=file, view=game_view)
    for emoji in reaction_choices:
        await message.add_reaction(emoji)


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


YTDL_OPTIONS = {
    "format": "bestaudio/best", "noplaylist": True, "default_search": "ytsearch",
    "quiet": True, "noprogress": True,
}
_js_runtimes = {}
_deno_path = shutil.which("deno") or os.path.join(os.path.expanduser("~"), ".deno", "bin", "deno")
for _runtime, _candidates in (
    ("deno", (_deno_path,)),
    ("node", (shutil.which("node"),)),
    ("bun", (shutil.which("bun"),)),
    ("quickjs", (shutil.which("qjs"), shutil.which("quickjs"))),
):
    _runtime_path = next((path for path in _candidates if path and os.path.isfile(path)), None)
    if _runtime_path:
        _js_runtimes[_runtime] = {"path": _runtime_path}
if _js_runtimes:
    YTDL_OPTIONS["js_runtimes"] = _js_runtimes
YTDL_OPTIONS["remote_components"] = {"ejs:npm"}
YTDL_OPTIONS["sleep_interval_requests"] = 1.5
print(f"yt-dlp JavaScript runtimes detected: {', '.join(_js_runtimes) if _js_runtimes else 'none'}")
YOUTUBE_COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE", "youtube-cookies.txt")
_youtube_cookie_temp_path = None


def _remove_youtube_cookie_temp():
    if _youtube_cookie_temp_path:
        try:
            os.remove(_youtube_cookie_temp_path)
        except FileNotFoundError:
            pass
        except OSError:
            logging.warning("Could not remove temporary YouTube cookies file")


def get_ytdl_options():
    """Build yt-dlp options and copy optional cookies into writable private temp storage."""
    global _youtube_cookie_temp_path
    options = YTDL_OPTIONS.copy()
    cookie_source = os.path.abspath(YOUTUBE_COOKIES_FILE)
    if os.path.isfile(cookie_source):
        if _youtube_cookie_temp_path is None:
            with tempfile.NamedTemporaryFile(prefix="youtube-cookies-", suffix=".txt", delete=False) as temp_cookie:
                _youtube_cookie_temp_path = temp_cookie.name
            os.chmod(_youtube_cookie_temp_path, 0o600)
            shutil.copyfile(cookie_source, _youtube_cookie_temp_path)
            atexit.register(_remove_youtube_cookie_temp)
        options["cookiefile"] = _youtube_cookie_temp_path
    elif os.getenv("YOUTUBE_COOKIES_FILE"):
        raise FileNotFoundError("YOUTUBE_COOKIES_FILE does not point to an accessible cookies file")
    return options


def extract_info_with_cookie_fallback(query, options, download=False):
    """Retry a cookie-rejected YouTube lookup anonymously, preserving old behavior."""
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(query, download=download)
    except yt_dlp.utils.DownloadError as error:
        error_text = str(error).lower()
        if not options.get("cookiefile") or "sign in to confirm" not in error_text:
            raise
        logging.warning("YouTube rejected the cookie-authenticated request; retrying without cookies")
        anonymous_options = options.copy()
        anonymous_options.pop("cookiefile", None)
        with yt_dlp.YoutubeDL(anonymous_options) as ydl:
            return ydl.extract_info(query, download=download)


# Try the bundled FFmpeg first, then a configured or system build if decoding
# a specific audio format is unsupported.
SYSTEM_FFMPEG = shutil.which("ffmpeg")
try:
    BUNDLED_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except RuntimeError:
    BUNDLED_FFMPEG = None
FFMPEG_OPTIONS = {"options": "-vn"}
# Prefer the host FFmpeg: the bundled imageio build crashed with exit -11
# during earlier playback attempts. Keep the bundled binary as a fallback.
FFMPEG_CANDIDATES = list(dict.fromkeys(
    executable for executable in (os.getenv("FFMPEG_BINARY"), SYSTEM_FFMPEG, BUNDLED_FFMPEG)
    if executable
))
logging.info("Music FFmpeg candidates: %s", FFMPEG_CANDIDATES)


def read_pcm_probe(source, frame_limit=5):
    """Read a short PCM sample and report its loudest decoded sample."""
    frames = []
    peak = 0
    for _ in range(frame_limit):
        frame = source.read()
        if not frame:
            break
        frames.append(frame)
        peak = max(peak, max((abs(sample[0]) for sample in struct.iter_unpack("<h", frame)), default=0))
    return frames, peak


class BufferedAudioSource(discord.AudioSource):
    """Replay the PCM frames consumed while checking the remote audio stream."""
    def __init__(self, source, initial_frames, stderr_log, temp_dir=None):
        self.source = source
        self.initial_frames = deque(initial_frames)
        self.stderr_log = stderr_log
        self.temp_dir = temp_dir
        self.read_frames = 0

    def read(self):
        frame = self.initial_frames.popleft() if self.initial_frames else self.source.read()
        if frame:
            self.read_frames += 1
        return frame

    def is_opus(self):
        return False

    def cleanup(self):
        self.source.cleanup()
        self.stderr_log.close()
        if self.temp_dir:
            self.temp_dir.cleanup()
            self.temp_dir = None

    def error_output(self):
        try:
            self.stderr_log.flush()
            self.stderr_log.seek(0)
            detail = self.stderr_log.read(4096).decode(errors="replace").strip()
            return re.sub(r"https?://\S+", "[stream URL]", detail) or "<no FFmpeg details>"
        except Exception:
            return "<FFmpeg details unavailable>"


music_states = {}
youtube_lookup_lock = asyncio.Lock()
last_youtube_lookup = 0.0


def get_music_state(guild_id):
    return music_states.setdefault(guild_id, {
        "queue": deque(), "history": [], "current": None, "offset": 0,
        "started_at": None, "text_channel_id": None, "suppress_after": False,
        "volume": 100, "loop": "off", "paused": False,
    })


def format_duration(seconds):
    if not seconds:
        return "Live / unknown length"
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def now_playing_embed(state):
    track = state["current"]
    if not track:
        return discord.Embed(title="Nothing is playing", color=discord.Color.blurple())
    embed = discord.Embed(
        title="🎶 Now playing",
        description=f"[{discord.utils.escape_markdown(track['title'])}]({track['webpage_url']})",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Duration", value=format_duration(track.get("duration")), inline=True)
    embed.add_field(name="Requested by", value=track["requester"], inline=True)
    embed.add_field(name="Status", value="Paused" if state.get("paused") else "Playing", inline=True)
    if track.get("thumbnail"):
        embed.set_thumbnail(url=track["thumbnail"])
    return embed


async def post_now_playing(guild_id):
    state = get_music_state(guild_id)
    channel = bot.get_channel(state["text_channel_id"])
    if channel:
        view = MusicControlView(guild_id) if state["current"] else None
        message = await channel.send(embed=now_playing_embed(state), view=view)
        if view:
            view.message = message


class MusicControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=7200)
        self.guild_id = guild_id
        self.message = None

    async def interaction_check(self, interaction):
        guild = interaction.guild
        voice = guild.voice_client if guild else None
        member_voice = getattr(interaction.user, "voice", None)
        if (not guild or guild.id != self.guild_id or not voice or not member_voice
                or member_voice.channel != voice.channel):
            await interaction.response.send_message(
                "Join the bot's voice channel to use these controls.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, row=0)
    async def previous_button(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await previous_music_track(self.guild_id)
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary, row=0)
    async def rewind_button(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await seek_music_state(self.guild_id, -10)
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(emoji="⏸️", label="Pause", style=discord.ButtonStyle.primary, row=0)
    async def pause_button(self, interaction, button):
        guild = interaction.guild
        voice = guild.voice_client if guild else None
        state = get_music_state(self.guild_id)
        if voice and voice.is_paused():
            state["started_at"] = asyncio.get_running_loop().time()
            state["paused"] = False
            voice.resume()
            button.label = "Pause"
            button.emoji = "⏸️"
        elif voice and voice.is_playing():
            if state["started_at"] is not None:
                state["offset"] += int(asyncio.get_running_loop().time() - state["started_at"])
            state["started_at"] = None
            state["paused"] = True
            voice.pause()
            button.label = "Resume"
            button.emoji = "▶️"
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=now_playing_embed(state), view=self)

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary, row=0)
    async def forward_button(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await seek_music_state(self.guild_id, 10)
        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip_button(self, interaction, button):
        guild = interaction.guild
        voice = guild.voice_client if guild else None
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()
            await interaction.response.edit_message(content="⏭️ Skipped.", embed=None, view=None)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @discord.ui.button(emoji="📜", label="Queue", style=discord.ButtonStyle.secondary, row=1)
    async def queue_button(self, interaction, button):
        state = get_music_state(self.guild_id)
        lines = [f"**Now:** {state['current']['title']}" if state["current"] else "**Now:** Nothing playing"]
        lines.extend(
            f"{index}. {track['title']} — {format_duration(track.get('duration'))}"
            for index, track in enumerate(state["queue"], 1)
        )
        description = "\n".join(lines)
        if len(description) > 4000:
            description = description[:3990] + "…"
        embed = discord.Embed(title="🎵 Music queue", description=description, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="⏹️", label="Stop", style=discord.ButtonStyle.danger, row=1)
    async def stop_button(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await stop_music_state(self.guild_id)
        try:
            await interaction.message.edit(embed=now_playing_embed(get_music_state(self.guild_id)), view=None)
        except discord.HTTPException:
            pass
        await interaction.followup.send(message, ephemeral=True)


def resolve_track_stream(track):
    """Resolve a fresh direct audio URL immediately before playback."""
    options = get_ytdl_options()
    options.update({"format": "bestaudio/best", "skip_download": True, "noplaylist": True})
    info = extract_info_with_cookie_fallback(track["webpage_url"], options, download=False)
    if info and "entries" in info:
        info = next((entry for entry in info["entries"] if entry), None)
    if not info:
        raise ValueError("No playable audio stream found")
    stream_url = info.get("url")
    if not stream_url:
        formats = info.get("requested_formats") or info.get("formats") or []
        audio_formats = [item for item in formats if item.get("acodec") not in (None, "none")]
        if audio_formats:
            stream_url = audio_formats[-1].get("url")
    if not stream_url:
        raise RuntimeError("yt-dlp did not return a direct audio stream URL")
    return stream_url, info


def download_track_for_cookie_playback(track, options):
    """Download through yt-dlp when cookies are needed, keeping them out of FFmpeg."""
    temp_dir = tempfile.TemporaryDirectory(prefix="discord-music-")
    download_options = options.copy()
    download_options.update({
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": os.path.join(temp_dir.name, "audio.%(ext)s"),
        "quiet": True,
        "noprogress": True,
    })
    try:
        info = extract_info_with_cookie_fallback(
            track["webpage_url"], download_options, download=True
        )
        if info and "entries" in info:
            info = next((entry for entry in info["entries"] if entry), None)
        audio_files = [
            os.path.join(temp_dir.name, name)
            for name in os.listdir(temp_dir.name)
            if os.path.isfile(os.path.join(temp_dir.name, name))
            and not name.endswith((".part", ".ytdl"))
        ]
        if not info or not audio_files:
            raise RuntimeError("yt-dlp completed without creating an audio file")
        return temp_dir, audio_files[0], info
    except Exception:
        temp_dir.cleanup()
        raise


async def resolve_track_stream_async(track):
    global last_youtube_lookup
    loop = asyncio.get_running_loop()
    async with youtube_lookup_lock:
        wait_for = 4.0 - (loop.time() - last_youtube_lookup)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        try:
            return await asyncio.to_thread(resolve_track_stream, track)
        finally:
            last_youtube_lookup = loop.time()


async def download_track_for_cookie_playback_async(track, options):
    global last_youtube_lookup
    loop = asyncio.get_running_loop()
    async with youtube_lookup_lock:
        wait_for = 4.0 - (loop.time() - last_youtube_lookup)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        try:
            return await asyncio.to_thread(download_track_for_cookie_playback, track, options)
        finally:
            last_youtube_lookup = loop.time()


async def start_music_track(guild_id, track, record_history=True):
    guild = bot.get_guild(guild_id)
    state = get_music_state(guild_id)
    voice = guild.voice_client if guild else None
    if not voice or not track:
        return
    if record_history and state["current"]:
        state["history"].append(state["current"])
    state["current"] = track
    offset = max(0, int(state["offset"]))
    ytdl_options = get_ytdl_options()
    temp_dir = None
    if ytdl_options.get("cookiefile"):
        temp_dir, audio_input, stream_info = await download_track_for_cookie_playback_async(
            track, ytdl_options
        )
        reconnect_options = ""
        logging.info("Using yt-dlp-managed temporary audio for cookie-authenticated playback")
    else:
        audio_input, stream_info = await resolve_track_stream_async(track)
        reconnect_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
    track["title"] = stream_info.get("title") or track["title"]
    track["duration"] = stream_info.get("duration") or track.get("duration")
    track["thumbnail"] = stream_info.get("thumbnail") or track.get("thumbnail")
    before_options = " ".join(part for part in (
        reconnect_options, f"-ss {offset}" if offset else ""
    ) if part)
    audio_options = FFMPEG_OPTIONS["options"]
    audio = None
    ffmpeg_stderr = None
    initial_frames = []
    probe_peak = 0
    ffmpeg_executable = None
    ffmpeg_failures = []
    logging.info("Music audio resolved format=%s protocol=%s", stream_info.get("ext"), stream_info.get("protocol"))
    for candidate in FFMPEG_CANDIDATES:
        candidate_stderr = tempfile.TemporaryFile()
        candidate_audio = None
        try:
            candidate_audio = discord.FFmpegPCMAudio(
                audio_input, executable=candidate, before_options=before_options,
                options=audio_options, stderr=candidate_stderr,
            )
            read_task = asyncio.create_task(asyncio.to_thread(read_pcm_probe, candidate_audio))
            read_task.add_done_callback(
                lambda task: task.exception() if not task.cancelled() else None
            )
            try:
                candidate_frames, candidate_peak = await asyncio.wait_for(asyncio.shield(read_task), timeout=15)
            except asyncio.TimeoutError:
                candidate_audio._process.kill()
                candidate_stderr.flush()
                candidate_stderr.seek(0)
                detail = candidate_stderr.read(4096).decode(errors="replace").strip()
                detail = re.sub(r"https?://\S+", "[stream URL]", detail) or "<no FFmpeg details>"
                candidate_audio._stopped = True
                try:
                    candidate_audio._stdout.close()
                except Exception:
                    pass
                candidate_audio._process.poll()
                ffmpeg_failures.append(f"{candidate} timed out waiting for audio: {detail}")
                candidate_stderr.close()
                continue
            if candidate_frames:
                audio, ffmpeg_stderr = candidate_audio, candidate_stderr
                initial_frames, probe_peak = candidate_frames, candidate_peak
                ffmpeg_executable = candidate
                break
            return_code = candidate_audio._process.poll()
            candidate_stderr.flush()
            candidate_stderr.seek(0)
            detail = candidate_stderr.read(4096).decode(errors="replace").strip()
            detail = re.sub(r"https?://\S+", "[stream URL]", detail)
            ffmpeg_failures.append(f"{candidate} exit {return_code}: {detail or '<no FFmpeg details>'}")
            candidate_audio.cleanup()
            candidate_stderr.close()
            logging.warning("FFmpeg %s returned no audio (exit %s): %s", candidate, return_code, detail)
        except Exception as error:
            ffmpeg_failures.append(f"{candidate}: {type(error).__name__}: {error}")
            if candidate_audio is not None:
                try:
                    candidate_audio.cleanup()
                except Exception:
                    pass
            candidate_stderr.close()
    if not initial_frames:
        if temp_dir:
            temp_dir.cleanup()
        raise RuntimeError("No FFmpeg build produced audio frames. " + " | ".join(ffmpeg_failures))
    logging.warning(
        "Music diagnostic: FFmpeg decoded audio probe_frames=%d duration=%.2fs peak=%d executable=%s",
        len(initial_frames), len(initial_frames) * 0.02, probe_peak, ffmpeg_executable,
    )
    buffered_source = BufferedAudioSource(audio, initial_frames, ffmpeg_stderr, temp_dir=temp_dir)
    source = discord.PCMVolumeTransformer(buffered_source, volume=state["volume"] / 100)
    state["offset"] = offset
    state["paused"] = False
    state["started_at"] = asyncio.get_running_loop().time()

    def after_playback(error):
        if state["suppress_after"]:
            state["suppress_after"] = False
            return
        sent_frames = getattr(voice._player, "loops", "unknown")
        if error:
            ffmpeg_detail = buffered_source.error_output()
            logging.error(
                "Music playback failed for %r using %s after %s voice frames: %s; stderr: %s",
                track.get("title", "unknown track"), ffmpeg_executable, sent_frames, error, ffmpeg_detail,
            )
            state["current"] = None
            state["started_at"] = None
            async def report_playback_error():
                channel = bot.get_channel(state.get("text_channel_id"))
                if channel:
                    await channel.send(
                        "I couldn't play that track. FFmpeg reported: "
                        f"`{str(error)[:180]}` · `{ffmpeg_detail[:180]}`. Try `/play` again."
                    )
                await advance_music(guild_id)
            future = asyncio.run_coroutine_threadsafe(report_playback_error(), bot.loop)
            try:
                future.result()
            except Exception as callback_error:
                logging.error("Music queue callback failed after FFmpeg error: %s", callback_error)
            return
        logging.warning(
            "Music track %r ended normally: sent_frames=%s voice_connected=%s channel=%s ffmpeg=%s",
            track.get("title", "unknown track"), sent_frames, voice.is_connected(),
            getattr(voice.channel, "id", None), ffmpeg_executable,
        )
        future = asyncio.run_coroutine_threadsafe(advance_music(guild_id), bot.loop)
        try:
            future.result()
        except Exception as callback_error:
            logging.error("Music queue callback failed: %s", callback_error)

    try:
        voice.play(source, after=after_playback)
    except Exception:
        source.cleanup()
        state["current"] = None
        state["started_at"] = None
        raise
    bot_voice_state = guild.me.voice if guild and guild.me else None
    voice_permissions = voice.channel.permissions_for(guild.me) if guild and guild.me and voice.channel else None
    logging.warning(
        "Music playback started title=%r stream_peak=%d voice_connected=%s channel=%s "
        "can_speak=%s server_muted=%s self_muted=%s server_deafened=%s ffmpeg=%s",
        track.get("title", "unknown track"), probe_peak, voice.is_connected(),
        getattr(voice.channel, "id", None), getattr(voice_permissions, "speak", None),
        getattr(bot_voice_state, "mute", None), getattr(bot_voice_state, "self_mute", None),
        getattr(bot_voice_state, "deaf", None), ffmpeg_executable,
    )
    await post_now_playing(guild_id)

    async def log_voice_delivery_probe():
        await asyncio.sleep(3)
        player = voice._player
        logging.warning(
            "Music diagnostic: after 3s sent_voice_packets=%s source_frames_read=%s "
            "playing=%s paused=%s connected=%s",
            getattr(player, "loops", None), buffered_source.read_frames,
            voice.is_playing(), voice.is_paused(), voice.is_connected(),
        )

    asyncio.create_task(log_voice_delivery_probe())


async def advance_music(guild_id):
    state = get_music_state(guild_id)
    finished = state["current"]
    if finished and state["loop"] == "track":
        await start_music_track(guild_id, finished, record_history=False)
        return
    if finished and state["loop"] == "queue":
        state["queue"].append(finished)
    state["current"] = None
    state["offset"] = 0
    state["started_at"] = None
    while state["queue"]:
        try:
            await start_music_track(guild_id, state["queue"].popleft())
            return
        except Exception as error:
            print(f"Skipping unavailable queued track: {error}")
    await post_now_playing(guild_id)


async def extract_track(query, requester):
    global last_youtube_lookup
    loop = asyncio.get_running_loop()
    def extract():
        options = get_ytdl_options()
        info = extract_info_with_cookie_fallback(query, options, download=False)
        if info and "entries" in info:
            info = next((entry for entry in info["entries"] if entry), None)
        if not info:
            raise ValueError("No playable result found")
        return {
            "title": info.get("title", query),
            "webpage_url": info.get("webpage_url", query),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "requester": requester,
        }
    # Serialize lookups and leave breathing room between searches so multiple
    # queued requests do not immediately amplify YouTube's rate limiting.
    async with youtube_lookup_lock:
        now = loop.time()
        wait_for = 4.0 - (now - last_youtube_lookup)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        try:
            return await loop.run_in_executor(None, extract)
        finally:
            last_youtube_lookup = loop.time()


async def add_music_request(ctx, query):
    if not ctx.guild:
        await ctx.send("Music commands work in a server voice channel.")
        return
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("Join a voice channel first.")
        return

    # Send an initial response immediately so slash invocations never sit on
    # Discord's deferred "thinking" indicator while yt-dlp downloads a track.
    progress = await ctx.send("Joining voice and looking up the track…")
    guild_id = ctx.guild.id
    state = get_music_state(guild_id)
    voice = ctx.guild.voice_client
    stage = "joining voice"
    try:
        if voice is None:
            voice = await ctx.author.voice.channel.connect()
        elif voice.channel != ctx.author.voice.channel:
            if voice.is_playing() or voice.is_paused():
                await progress.edit(content=f"I'm already playing in **{voice.channel.name}**.")
                return
            await voice.move_to(ctx.author.voice.channel)
        stage = "looking up the track with yt-dlp"
        track = await extract_track(query, ctx.author.display_name)
        state["text_channel_id"] = ctx.channel.id
        if voice.is_playing() or voice.is_paused():
            state["queue"].append(track)
            await progress.edit(content=f"Added **{discord.utils.escape_markdown(track['title'])}** to the queue (#{len(state['queue'])}).")
        else:
            state["offset"] = 0
            stage = "opening the audio stream"
            await progress.edit(content=f"Found **{discord.utils.escape_markdown(track['title'])}**. Preparing audio…")
            await start_music_track(guild_id, track)
            await progress.edit(content=f"Started **{discord.utils.escape_markdown(track['title'])}**.")
    except Exception as error:
        detail = str(error).replace("\n", " ")[:300]
        logging.error("Music command failed during %s (%s): %s", stage, type(error).__name__, detail)
        if isinstance(error, RuntimeError) and "PyNaCl" in str(error):
            message = "Voice support is missing PyNaCl. Install the project dependencies from `requirements.txt`."
        elif isinstance(error, RuntimeError) and "davey" in str(error).lower():
            message = "Voice support is missing davey. Install the project dependencies from `requirements.txt`."
        elif stage == "looking up the track with yt-dlp":
            error_text = str(error).lower()
            if "429" in error_text or "too many requests" in error_text:
                message = "YouTube is rate-limiting the bot host (HTTP 429). Wait before trying again."
            elif "requested format is not available" in error_text:
                message = "YouTube did not expose an audio format for this track. Try another track."
            elif "page needs to be reloaded" in error_text:
                message = "YouTube rejected this request from the bot host. Try again later or use another track."
            elif "sign in to confirm" in error_text:
                message = "YouTube blocked this track's anonymous request. Try another track or retry later."
            elif "signature solving failed" in error_text or "challenge solving failed" in error_text:
                message = "YouTube's playback challenge could not be solved. Install Deno 2.3+ or Node.js 22+ on the bot host, then restart it."
            else:
                message = "yt-dlp couldn't resolve that track. Check that Deno 2.3+ or Node.js 22+ is available and review the bot log."
        else:
            message = f"Couldn't load the track while {stage} ({type(error).__name__}). See the bot log for details."
        try:
            await progress.edit(content=message)
        except discord.HTTPException:
            await ctx.send(message)


@bot.hybrid_command(name="play", description="Play a song or add it to the queue")
async def play(ctx, *, query: str):
    await add_music_request(ctx, query)


@bot.hybrid_command(name="add", description="Add a song to the queue")
async def add(ctx, *, query: str):
    await add_music_request(ctx, query)


@bot.hybrid_command(name="queue", description="Show the current song and upcoming queue")
async def queue(ctx):
    if not ctx.guild:
        await ctx.send("Music queues are per server.")
        return
    state = get_music_state(ctx.guild.id)
    lines = [f"**Now:** {state['current']['title']}" if state["current"] else "**Now:** Nothing playing"]
    lines.extend(f"{index}. {track['title']} — {format_duration(track.get('duration'))}" for index, track in enumerate(state["queue"], 1))
    description = "\n".join(lines)
    if len(description) > 4000:
        description = description[:3990] + "…"
    await ctx.send(embed=discord.Embed(title="🎵 Music queue", description=description, color=discord.Color.blurple()))


@bot.hybrid_command(name="nowplaying", description="Show the currently playing song")
async def nowplaying(ctx):
    if not ctx.guild:
        await ctx.send("Music works in a server voice channel.")
        return
    state = get_music_state(ctx.guild.id)
    await ctx.send(embed=now_playing_embed(state), view=MusicControlView(ctx.guild.id) if state["current"] else None)


async def previous_music_track(guild_id):
    state = get_music_state(guild_id)
    guild = bot.get_guild(guild_id)
    voice = guild.voice_client if guild else None
    if not state["history"] or not voice:
        return "There isn't a previous track in the history yet."
    previous_track = state["history"].pop()
    if state["current"]:
        state["queue"].appendleft(state["current"])
    active = voice.is_playing() or voice.is_paused()
    state["suppress_after"] = active
    if active:
        voice.stop()
    state["offset"] = 0
    await start_music_track(guild_id, previous_track, record_history=False)
    return "⏮️ Playing the previous track."


async def stop_music_state(guild_id):
    state = get_music_state(guild_id)
    guild = bot.get_guild(guild_id)
    voice = guild.voice_client if guild else None
    state["queue"].clear()
    state["current"] = None
    state["history"].clear()
    state["offset"] = 0
    state["paused"] = False
    state["started_at"] = None
    state["suppress_after"] = bool(voice and (voice.is_playing() or voice.is_paused()))
    if voice:
        if voice.is_playing() or voice.is_paused():
            voice.stop()
        await voice.disconnect()
    return "⏹️ Stopped playback, cleared the queue, and left voice."


async def seek_music_state(guild_id, delta, absolute=False):
    state = get_music_state(guild_id)
    guild = bot.get_guild(guild_id)
    voice = guild.voice_client if guild else None
    if not state["current"] or not voice or not (voice.is_playing() or voice.is_paused()):
        return "Nothing is playing to seek."
    elapsed = state["offset"]
    if voice.is_playing() and state["started_at"] is not None:
        elapsed += asyncio.get_running_loop().time() - state["started_at"]
    duration = state["current"].get("duration")
    new_offset = max(0, int(delta if absolute else elapsed + delta))
    if duration:
        new_offset = min(new_offset, max(0, int(duration) - 2))
    state["offset"] = new_offset
    current = state["current"]
    state["suppress_after"] = True
    voice.stop()
    await start_music_track(guild_id, current, record_history=False)
    icon = "⏪" if delta < 0 else "⏩"
    return f"{icon} Moved to {format_duration(new_offset)}."


@bot.hybrid_command(name="skip", description="Skip the current song")
async def skip(ctx):
    voice = ctx.guild.voice_client if ctx.guild else None
    if voice and (voice.is_playing() or voice.is_paused()):
        voice.stop()
        await ctx.send("⏭️ Skipped.")
    else:
        await ctx.send("Nothing is playing to skip.")


@bot.hybrid_command(name="previous", description="Play the previous song")
async def previous(ctx):
    if not ctx.guild:
        await ctx.send("Music works in a server voice channel.")
        return
    await ctx.send(await previous_music_track(ctx.guild.id))


@bot.hybrid_command(name="pause", description="Pause music")
async def pause(ctx):
    voice = ctx.guild.voice_client if ctx.guild else None
    state = get_music_state(ctx.guild.id) if ctx.guild else None
    if voice and state and voice.is_playing():
        state["offset"] += int(asyncio.get_running_loop().time() - state["started_at"])
        state["started_at"] = None
        voice.pause()
        state["paused"] = True
        await ctx.send("⏸️ Paused.")
    else:
        await ctx.send("Nothing is playing to pause.")


@bot.hybrid_command(name="resume", description="Resume paused music")
async def resume(ctx):
    voice = ctx.guild.voice_client if ctx.guild else None
    state = get_music_state(ctx.guild.id) if ctx.guild else None
    if voice and state and voice.is_paused():
        state["started_at"] = asyncio.get_running_loop().time()
        state["paused"] = False
        voice.resume()
        await ctx.send("▶️ Resumed.")
    else:
        await ctx.send("Nothing is paused right now.")


@bot.hybrid_command(name="stop", description="Stop playback, clear the queue, and leave voice")
async def stop(ctx):
    if not ctx.guild:
        await ctx.send("Music works in a server voice channel.")
        return
    await ctx.send(await stop_music_state(ctx.guild.id))


async def seek_music(ctx, delta, absolute=False):
    if not ctx.guild:
        await ctx.send("Music works in a server voice channel.")
        return
    await ctx.send(await seek_music_state(ctx.guild.id, delta, absolute))


@bot.hybrid_command(name="back", description="Rewind music by 10 seconds")
async def back(ctx):
    await seek_music(ctx, -10)


@bot.hybrid_command(name="forward", description="Move forward 10 seconds")
async def forward(ctx):
    await seek_music(ctx, 10)


@bot.hybrid_command(name="seek", description="Jump to a position in the current song")
@app_commands.describe(seconds="Position in the song, in seconds")
async def seek(ctx, seconds: int):
    if seconds < 0 or seconds > 86400:
        await ctx.send("Choose a position from 0 to 86400 seconds.")
        return
    await seek_music(ctx, seconds, absolute=True)


@bot.hybrid_command(name="volume", description="Set playback volume from 0 to 200 percent")
@app_commands.describe(percent="Volume percentage (0 to 200)")
async def volume(ctx, percent: int):
    if not ctx.guild:
        await ctx.send("Music works in a server voice channel.")
        return
    if percent < 0 or percent > 200:
        await ctx.send("Choose a volume from 0 to 200 percent.")
        return
    state = get_music_state(ctx.guild.id)
    state["volume"] = percent
    voice = ctx.guild.voice_client
    if voice and isinstance(voice.source, discord.PCMVolumeTransformer):
        voice.source.volume = percent / 100
    await ctx.send(f"🔊 Volume set to **{percent}%**.")


@bot.hybrid_command(name="shuffle", description="Shuffle the upcoming queue")
async def shuffle(ctx):
    if not ctx.guild:
        await ctx.send("Music queues are per server.")
        return
    state = get_music_state(ctx.guild.id)
    tracks = list(state["queue"])
    random.shuffle(tracks)
    state["queue"] = deque(tracks)
    await ctx.send("🔀 Shuffled the queue." if tracks else "The queue is empty.")


@bot.hybrid_command(name="remove", description="Remove a song from the queue by its position")
@app_commands.describe(position="The song number shown by /queue")
async def remove(ctx, position: int):
    if not ctx.guild:
        await ctx.send("Music queues are per server.")
        return
    state = get_music_state(ctx.guild.id)
    if position < 1:
        await ctx.send("Position must be 1 or higher.")
        return
    if position > len(state["queue"]):
        await ctx.send("There is no song at that queue position.")
        return
    tracks = list(state["queue"])
    removed = tracks.pop(position - 1)
    state["queue"] = deque(tracks)
    await ctx.send(f"Removed **{discord.utils.escape_markdown(removed['title'])}** from the queue.")


@bot.hybrid_command(name="clearqueue", description="Clear all upcoming songs")
async def clearqueue(ctx):
    if not ctx.guild:
        await ctx.send("Music queues are per server.")
        return
    state = get_music_state(ctx.guild.id)
    count = len(state["queue"])
    state["queue"].clear()
    await ctx.send(f"Cleared {count} queued song{'s' if count != 1 else ''}.")


@bot.hybrid_command(name="loop", description="Set repeat mode")
@app_commands.choices(mode=[
    app_commands.Choice(name="Off", value="off"),
    app_commands.Choice(name="Current song", value="track"),
    app_commands.Choice(name="Queue", value="queue"),
])
async def loop(ctx, mode: str):
    if not ctx.guild:
        await ctx.send("Music queues are per server.")
        return
    if mode not in {"off", "track", "queue"}:
        await ctx.send("Choose loop mode: off, track, or queue.")
        return
    state = get_music_state(ctx.guild.id)
    state["loop"] = mode
    labels = {"off": "Looping off", "track": "Looping the current song", "queue": "Looping the queue"}
    await ctx.send(f"🔁 {labels[mode]}.")


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

if __name__ == "__main__":
    if not token:
        raise RuntimeError("Set DISCORD_TOKEN in the environment before starting the bot")
    discord.utils.setup_logging(level=logging.INFO)
    bot.run(token)
