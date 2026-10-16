import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from better_profanity import profanity
from flask import Flask
from threading import Thread
import os
import random
import asyncio
import yt_dlp
import imageio_ffmpeg
from collections import deque
from discord import app_commands

load_dotenv()

token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(
    filename="discord.log",
    encoding="utf-8",
    mode="w"
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="$", intents=intents)
afk_users = {}

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

@app.route("/ping")
def ping():
    return "OK"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()

sniped_messages = {}

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

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as error:
        print(f"Slash command sync failed: {error}")

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

    # Clear AFK when the user speaks, and let people know when they mention
    # someone who is away.
    if message.guild:
        author_key = (message.guild.id, message.author.id)
        if author_key in afk_users:
            afk_users.pop(author_key, None)
            await message.reply("welcome back! your AFK status is cleared ✨", mention_author=False)
        for mentioned in message.mentions:
            afk = afk_users.get((message.guild.id, mentioned.id))
            if afk:
                await message.channel.send(
                    f"{mentioned.mention} is AFK: {discord.utils.escape_mentions(afk)}",
                    allowed_mentions=discord.AllowedMentions(users=[message.author])
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
        await ctx.send("AFK status works in servers.")
        return
    if reason.strip().lower() in {"off", "clear", "back"}:
        afk_users.pop((ctx.guild.id, ctx.author.id), None)
        await ctx.send("welcome back! your AFK status is cleared ✨")
        return
    afk_users[(ctx.guild.id, ctx.author.id)] = reason[:200]
    await ctx.send(f"{ctx.author.mention} is now AFK: {discord.utils.escape_mentions(reason[:200])}")
    if ctx.interaction is None:
        await ctx.message.add_reaction("💤")


@bot.hybrid_command(name="games", description="Play a quick chat game")
@app_commands.describe(game="Choose a game", choice="Your choice for rock-paper-scissors")
@app_commands.choices(game=[
    app_commands.Choice(name="Coin flip", value="coin"),
    app_commands.Choice(name="Roll a die", value="dice"),
    app_commands.Choice(name="Magic 8-ball", value="8ball"),
    app_commands.Choice(name="Rock paper scissors", value="rps"),
])
@app_commands.choices(choice=[
    app_commands.Choice(name="Rock", value="rock"),
    app_commands.Choice(name="Paper", value="paper"),
    app_commands.Choice(name="Scissors", value="scissors"),
])
async def games(ctx, game: str, choice: str = ""):
    if game == "coin":
        result = f"🪙 {random.choice(['Heads', 'Tails'])}!"
    elif game == "dice":
        result = f"🎲 You rolled **{random.randint(1, 6)}**!"
    elif game == "8ball":
        result = random.choice(["It is certain.", "Ask again later.", "Absolutely.", "Signs point to no.", "The vibes say yes.", "Not looking good, bestie."])
    else:
        if choice not in {"rock", "paper", "scissors"}:
            await ctx.send("For RPS, include a choice: rock, paper, or scissors.")
            return
        bot_choice = random.choice(["rock", "paper", "scissors"])
        outcome = "tie" if choice == bot_choice else "you win" if (choice, bot_choice) in {("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")} else "I win"
        result = f"You: **{choice}** · me: **{bot_choice}** — **{outcome}!**"
    await ctx.send(result)


@bot.hybrid_command(name="fetch", description="Show a user's avatar and, when available, banner")
async def fetch(ctx, user: discord.User = None):
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


YTDL_OPTIONS = {"format": "bestaudio/best", "noplaylist": True, "default_search": "ytsearch", "quiet": True}
FFMPEG_OPTIONS = {
    "executable": imageio_ffmpeg.get_ffmpeg_exe(),
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
music_states = {}


def get_music_state(guild_id):
    return music_states.setdefault(guild_id, {
        "queue": deque(), "history": [], "current": None, "offset": 0,
        "started_at": None, "text_channel_id": None, "suppress_after": False,
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
    if track.get("thumbnail"):
        embed.set_thumbnail(url=track["thumbnail"])
    return embed


async def post_now_playing(guild_id):
    state = get_music_state(guild_id)
    channel = bot.get_channel(state["text_channel_id"])
    if channel:
        await channel.send(embed=now_playing_embed(state))


async def start_music_track(guild_id, track, record_history=True, refresh_stream=False):
    guild = bot.get_guild(guild_id)
    state = get_music_state(guild_id)
    voice = guild.voice_client if guild else None
    if not voice or not track:
        return
    if record_history and state["current"]:
        state["history"].append(state["current"])
    if refresh_stream:
        track = await extract_track(track["webpage_url"], track["requester"])
    state["current"] = track
    offset = max(0, int(state["offset"]))
    before_options = FFMPEG_OPTIONS["before_options"]
    if offset:
        before_options = f"-ss {offset} {before_options}"
    source = discord.FFmpegPCMAudio(
        track["stream_url"], executable=FFMPEG_OPTIONS["executable"],
        before_options=before_options, options=FFMPEG_OPTIONS["options"],
    )
    state["offset"] = offset
    state["started_at"] = asyncio.get_running_loop().time()

    def after_playback(error):
        if state["suppress_after"]:
            state["suppress_after"] = False
            return
        future = asyncio.run_coroutine_threadsafe(advance_music(guild_id), bot.loop)
        try:
            future.result()
        except Exception as callback_error:
            print(f"Music queue callback failed: {callback_error}")

    voice.play(source, after=after_playback)
    await post_now_playing(guild_id)


async def advance_music(guild_id):
    state = get_music_state(guild_id)
    state["current"] = None
    state["offset"] = 0
    state["started_at"] = None
    while state["queue"]:
        try:
            await start_music_track(guild_id, state["queue"].popleft(), refresh_stream=True)
            return
        except Exception as error:
            print(f"Skipping unavailable queued track: {error}")
    await post_now_playing(guild_id)


async def extract_track(query, requester):
    loop = asyncio.get_running_loop()
    def extract():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = next((entry for entry in info["entries"] if entry), None)
            if not info:
                raise ValueError("No playable result found")
            return {
                "title": info.get("title", query),
                "stream_url": info["url"],
                "webpage_url": info.get("webpage_url", query),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "requester": requester,
            }
    return await loop.run_in_executor(None, extract)


@bot.hybrid_command(name="music", description="Play music and manage the server queue")
@app_commands.describe(action="Playback or queue action", query="Song name or URL")
@app_commands.choices(action=[
    app_commands.Choice(name="Play (or queue)", value="play"),
    app_commands.Choice(name="Add to queue", value="add"),
    app_commands.Choice(name="Show queue", value="queue"),
    app_commands.Choice(name="Now playing", value="now"),
    app_commands.Choice(name="Skip", value="skip"),
    app_commands.Choice(name="Previous track", value="previous"),
    app_commands.Choice(name="Back 10 seconds", value="back"),
    app_commands.Choice(name="Forward 10 seconds", value="forward"),
    app_commands.Choice(name="Pause", value="pause"),
    app_commands.Choice(name="Resume", value="resume"),
    app_commands.Choice(name="Stop and clear queue", value="stop"),
])
async def music(ctx, action: str, *, query: str = ""):
    if not ctx.guild:
        await ctx.send("Music commands work in a server voice channel.")
        return
    guild_id = ctx.guild.id
    state = get_music_state(guild_id)
    voice = ctx.guild.voice_client

    if action in {"play", "add"}:
        if not query:
            await ctx.send("Give me a song name or URL.")
            return
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Join a voice channel first.")
            return
        if ctx.interaction:
            await ctx.defer()
        try:
            if voice is None:
                voice = await ctx.author.voice.channel.connect()
            elif voice.channel != ctx.author.voice.channel:
                await voice.move_to(ctx.author.voice.channel)
            track = await extract_track(query, ctx.author.display_name)
            state["text_channel_id"] = ctx.channel.id
            if action == "add" or voice.is_playing() or voice.is_paused():
                state["queue"].append(track)
                pos = len(state["queue"])
                await ctx.send(f"Added **{discord.utils.escape_markdown(track['title'])}** to the queue (#{pos}).")
            else:
                state["offset"] = 0
                await start_music_track(guild_id, track)
                await ctx.send(embed=now_playing_embed(state))
        except Exception as error:
            await ctx.send(f"Couldn't load that track ({type(error).__name__}). Make sure yt-dlp can access it.")
        return

    if action == "queue":
        lines = [f"**Now:** {state['current']['title']}" if state["current"] else "**Now:** Nothing playing"]
        lines.extend(f"{index}. {track['title']} — {format_duration(track.get('duration'))}" for index, track in enumerate(state["queue"], 1))
        description = "\n".join(lines)
        if len(description) > 4000:
            description = description[:3990] + "…"
        await ctx.send(embed=discord.Embed(title="🎵 Music queue", description=description, color=discord.Color.blurple()))
        return
    if action == "now":
        await ctx.send(embed=now_playing_embed(state))
        return
    if action == "skip":
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()
            await ctx.send("⏭️ Skipped.")
        else:
            await ctx.send("Nothing is playing to skip.")
        return
    if action == "previous":
        if not state["history"]:
            await ctx.send("There isn't a previous track in the history yet.")
            return
        previous_track = state["history"].pop()
        if state["current"]:
            state["queue"].appendleft(state["current"])
        state["suppress_after"] = bool(voice and (voice.is_playing() or voice.is_paused()))
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()
        state["offset"] = 0
        await start_music_track(guild_id, previous_track, record_history=False, refresh_stream=True)
        await ctx.send("⏮️ Playing the previous track.")
        return
    if action in {"back", "forward"}:
        if not state["current"] or not voice or not (voice.is_playing() or voice.is_paused()):
            await ctx.send("Nothing is playing to seek.")
            return
        elapsed = state["offset"]
        if voice.is_playing() and state["started_at"] is not None:
            elapsed += asyncio.get_running_loop().time() - state["started_at"]
        delta = -10 if action == "back" else 10
        duration = state["current"].get("duration")
        new_offset = max(0, int(elapsed + delta))
        if duration:
            new_offset = min(new_offset, max(0, int(duration) - 2))
        state["offset"] = new_offset
        current = state["current"]
        state["suppress_after"] = True
        voice.stop()
        await start_music_track(guild_id, current, record_history=False)
        await ctx.send(f"⏪ Moved to {format_duration(new_offset)}.")
        return
    if action == "pause" and voice and voice.is_playing():
        state["offset"] += int(asyncio.get_running_loop().time() - state["started_at"])
        state["started_at"] = None
        voice.pause()
        await ctx.send("⏸️ Paused.")
    elif action == "resume" and voice and voice.is_paused():
        state["started_at"] = asyncio.get_running_loop().time()
        voice.resume()
        await ctx.send("▶️ Resumed.")
    elif action == "stop":
        state["queue"].clear()
        state["current"] = None
        state["history"].clear()
        state["offset"] = 0
        state["suppress_after"] = bool(voice and (voice.is_playing() or voice.is_paused()))
        if voice:
            voice.stop()
            await voice.disconnect()
        await ctx.send("⏹️ Stopped playback and cleared the queue.")
    else:
        await ctx.send("That action isn't available for the current playback state.")

@bot.command(name="catch")
async def catch(ctx):
    await snipe(ctx)

bot.run(token)
