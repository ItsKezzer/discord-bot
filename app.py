import asyncio
import logging
import sys
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.checks import CommandPermissionDenied
from utils.database import Database

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("discord.bot")


class BouloumbeleBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # Useful for resolving roles, kicks, and timeouts
        super().__init__(
            command_prefix="!",  # Unused for slash commands, required by commands.Bot
            intents=intents,
        )
        self.db = Database(config.DB_PATH)

    async def setup_hook(self) -> None:
        # Initialize SQLite database
        logger.info("Initializing database...")
        await self.db.initialize()

        # Load extension cogs
        cogs = [
            "cogs.general",
            "cogs.moderation",
            "cogs.docker_mgmt",
            "cogs.role_menu",
            "cogs.admin_config",
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.exception(f"Failed to load extension {cog}: {e}")

        # Register global app_command error handler
        self.tree.on_error = self.on_app_command_error

        # Sync application commands
        logger.info("Syncing application commands globally...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash command(s).")
        except Exception as e:
            logger.exception(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        logger.info(f"Logged in successfully as {self.user} (ID: {self.user.id})")
        if self.guilds:
            logger.info(f"Connected to {len(self.guilds)} guild(s):")
            for guild in self.guilds:
                logger.info(f"  • {guild.name} (ID: {guild.id}, Members: {guild.member_count})")
        else:
            logger.info("Connected to 0 guilds (invite the bot to a server to get started).")

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="/help | Server Manager",
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Global slash command error handler."""
        if isinstance(error, CommandPermissionDenied):
            embed = discord.Embed(
                title="🔒 Access Denied",
                description=(
                    f"You do not have permission to run `/{error.command_name}` on this server.\n\n"
                    "If you believe you should have access, ask a server Administrator to grant your "
                    "role or user account permission via `/config`."
                ),
                color=0xE74C3C,
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if isinstance(error, app_commands.BotMissingPermissions):
            missing = ", ".join(f"`{p}`" for p in error.missing_permissions)
            msg = f"❌ I am missing the following required Discord permissions: {missing}"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Command is on cooldown. Try again in {error.retry_after:.1f} seconds."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        logger.exception(
            f"Unhandled app command error in /{interaction.command.name if interaction.command else 'unknown'}: {error}"
        )
        msg = f"❌ An unexpected error occurred while processing this command: `{error}`"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


def main():
    if not config.TOKEN:
        logger.error(
            "No bot token provided! Please set the 'TOKEN' environment variable or add it to your .env file."
        )
        sys.exit(1)

    bot = BouloumbeleBot()
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()
