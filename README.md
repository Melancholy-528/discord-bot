# Discord Bot

## Deploy on Wispbyte

1. Choose the Python runtime and upload the project files, including `main.py`, `install_deno.py`, and `requirements.txt` (or `req.txt` if your startup command uses that filename).
2. Set the Wispbyte startup command to install Deno with Python's built-in ZIP support, expose it on `PATH`, install Python dependencies, then start the bot:

   ```sh
   python install_deno.py && export PATH="$HOME/.deno/bin:$PATH" && pip install --no-cache-dir -r requirements.txt && python main.py
   ```

   The installer downloads Deno's official Linux release and writes it directly to its install path, without root, `unzip`, or `7z`. If your panel already installs Deno, it reuses that executable.
3. Add `DISCORD_TOKEN` in the server's environment variables. Do not put the token in source code.
4. Start the server and check its console for `yt-dlp JavaScript runtimes detected: deno`, `has connected to Discord!`, and `Synced ... slash commands`.
5. Enable **Message Content**, **Server Members**, and **Presence** intents for the bot in the Discord Developer Portal. Prefix commands need Message Content Intent.

This is a Discord gateway bot, so it does not need an HTTP server or an allocated public port. Music normally uses a remote audio stream; when a YouTube cookies file is configured, yt-dlp downloads authenticated audio to a temporary file that is removed when playback ends. The included `imageio-ffmpeg` package supplies FFmpeg if the host does not provide a system FFmpeg.

### YouTube JavaScript runtime

Current YouTube playback requires yt-dlp's EJS challenge solver and a supported JavaScript runtime. `yt-dlp[default]` installs the solver scripts, but the host must also provide Deno 2.3+ or Node.js 22+. The bot detects installed Deno, Node, Bun, or QuickJS executables at startup. On Wispbyte, install Deno or Node in the container and make sure its executable is on `PATH` when `python main.py` starts; the startup log reports which runtimes yt-dlp can see. Cookies do not replace this runtime requirement.

## Commands

Hybrid commands work as slash commands or with the `!` prefix. The older `$` prefix is also accepted. Examples: `!play <song or URL>`, `!queue`, `!skip`, `!pause`, `!resume`, `!duel @member tictactoe`, `!duel @member rps`, and `!help`. `/duel` offers game choices and an accept/decline challenge flow.

## Run locally

```sh
python -m pip install -r requirements.txt  # req.txt is also provided for existing panel commands
python main.py
```


### Optional YouTube cookies

If yt-dlp reports that YouTube requires sign-in, export a Netscape-format YouTube cookies file and upload it to the server as `youtube-cookies.txt` (this filename is git-ignored). Alternatively, set `YOUTUBE_COOKIES_FILE` to the uploaded file's path. The bot copies it to private writable temporary storage for yt-dlp, so read-only secret mounts work. With cookies configured, playback audio is downloaded through yt-dlp to a temporary file because FFmpeg cannot reuse yt-dlp's authenticated cookie session; without cookies, the bot keeps using remote streaming. Never commit or post the file; it contains an account session. yt-dlp warns that using account cookies can lead to temporary or permanent account restrictions, so use a throwaway account and keep request volume low. Cookies can expire and are not guaranteed to resolve YouTube's checks.
