"""Start the Discord bot after loading its feature modules."""

import logging
import discord
from bot_state import bot, token

# Importing each feature module registers its commands and listeners on bot.
import events  # noqa: F401
import games  # noqa: F401
import music  # noqa: F401
import profiles  # noqa: F401
import community  # noqa: F401
import moderation  # noqa: F401
import help_commands  # noqa: F401


if __name__ == "__main__":
    if not token:
        raise RuntimeError("Set DISCORD_TOKEN in the environment before starting the bot")
    discord.utils.setup_logging(level=logging.INFO)
    bot.run(token)
