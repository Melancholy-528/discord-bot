"""Install the official Deno Linux binary without unzip, root, or extra disk copies."""

import io
import os
import platform
import shutil
import urllib.request
import zipfile
from pathlib import Path


ASSETS = {
    "x86_64": "deno-x86_64-unknown-linux-gnu.zip",
    "amd64": "deno-x86_64-unknown-linux-gnu.zip",
    "aarch64": "deno-aarch64-unknown-linux-gnu.zip",
    "arm64": "deno-aarch64-unknown-linux-gnu.zip",
}


def main():
    home_deno = Path.home() / ".deno" / "bin" / "deno"
    existing = shutil_which("deno") or (str(home_deno) if home_deno.is_file() else None)
    if existing:
        print(f"Using existing Deno executable: {existing}")
        return

    asset = ASSETS.get(platform.machine().lower())
    if not asset:
        raise SystemExit(f"Unsupported Linux architecture for automatic Deno install: {platform.machine()}")

    url = f"https://github.com/denoland/deno/releases/latest/download/{asset}"
    print(f"Downloading Deno for {platform.machine()}...")
    request = urllib.request.Request(url, headers={"User-Agent": "discord-bot-deno-installer"})
    install_dir = Path.home() / ".deno" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)
    binary_path = install_dir / "deno"
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            with archive.open("deno") as source, binary_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
        binary_path.chmod(0o755)
    except Exception:
        binary_path.unlink(missing_ok=True)
        raise
    print(f"Installed Deno to {binary_path}")


def shutil_which(name):
    # Avoid importing extra packages into this minimal bootstrap script.
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


if __name__ == "__main__":
    main()
