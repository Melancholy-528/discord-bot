"""Music playback, queue controls, and yt-dlp integration."""

from bot_state import (
    app_commands, asyncio, atexit, bot, deque,
    discord, imageio_ffmpeg, logging, os, random,
    re, shutil, struct, tempfile, yt_dlp,
)


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

SYSTEM_FFMPEG = shutil.which("ffmpeg")

try:
    BUNDLED_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except RuntimeError:
    BUNDLED_FFMPEG = None

FFMPEG_OPTIONS = {"options": "-vn"}

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
