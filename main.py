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
FFMPEG_OPTIONS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}


@bot.hybrid_command(name="music", description="Play, pause, resume, skip, or stop music in your voice channel")
@app_commands.describe(action="Playback action", query="Song name or URL (for play)")
@app_commands.choices(action=[
    app_commands.Choice(name="Play", value="play"), app_commands.Choice(name="Pause", value="pause"),
    app_commands.Choice(name="Resume", value="resume"), app_commands.Choice(name="Skip", value="skip"),
    app_commands.Choice(name="Stop", value="stop"),
])
async def music(ctx, action: str, *, query: str = ""):
    if not ctx.guild:
        await ctx.send("Music commands work in a server voice channel.")
        return
    voice = ctx.guild.voice_client
    if action == "play":
        if not query:
            await ctx.send("Give me a song name or URL to play.")
            return
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Join a voice channel first.")
            return
        await ctx.defer()
        try:
            if voice is None:
                voice = await ctx.author.voice.channel.connect()
            elif voice.channel != ctx.author.voice.channel:
                await voice.move_to(ctx.author.voice.channel)
            loop = asyncio.get_running_loop()
            with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            if "entries" in info:
                info = info["entries"][0]
            source = discord.FFmpegPCMAudio(info["url"], **FFMPEG_OPTIONS)
            if voice.is_playing() or voice.is_paused():
                await ctx.send("Already playing something. Pause, skip, or stop it first.")
                source.cleanup()
                return
            voice.play(source)
            await ctx.send(f"🎶 Now playing **{discord.utils.escape_markdown(info.get('title', query))}**")
        except Exception as error:
            await ctx.send(f"Couldn't play that track. Check yt-dlp and FFmpeg are installed. ({type(error).__name__})")
        return
    if voice is None:
        await ctx.send("I'm not playing anything right now.")
    elif action == "pause" and voice.is_playing():
        voice.pause(); await ctx.send("⏸️ Paused.")
    elif action == "resume" and voice.is_paused():
        voice.resume(); await ctx.send("▶️ Resumed.")
    elif action == "skip" and (voice.is_playing() or voice.is_paused()):
        voice.stop(); await ctx.send("⏭️ Skipped. (No queue is active.)")
    elif action == "stop":
        voice.stop()
        await voice.disconnect()
        await ctx.send("⏹️ Stopped and left voice chat.")
    else:
        await ctx.send("That action isn't available for the current playback state.")

@bot.command(name="catch")
async def catch(ctx):
    await snipe(ctx)

bot.run(token)
