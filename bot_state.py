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
