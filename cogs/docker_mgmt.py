import asyncio
import logging
import time
from typing import List
import discord
from discord import app_commands
from discord.ext import commands

import docker
from docker.errors import DockerException, NotFound

from config import DEFAULT_CONTAINER_ALIASES
from utils.checks import has_command_permission

logger = logging.getLogger("discord.bot.docker")


def _sync_restart_container(container_name: str) -> None:
    """Synchronous Docker restart call executed inside asyncio.to_thread."""
    client = docker.from_env()
    container = client.containers.get(container_name)
    container.restart()
    client.close()


class DockerManagement(commands.Cog):
    """Docker container management with friendly aliases and hidden internal names."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def server_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete choices for friendly server aliases, hiding real container names."""
        guild_id = interaction.guild_id or 0
        db = getattr(self.bot, "db", None)

        if db:
            aliases = await db.get_container_aliases(
                guild_id, DEFAULT_CONTAINER_ALIASES
            )
        else:
            aliases = DEFAULT_CONTAINER_ALIASES

        choices = [
            app_commands.Choice(name=alias, value=alias)
            for alias in aliases.keys()
            if current.lower() in alias.lower()
        ]
        return choices[:25]

    @app_commands.command(
        name="restart",
        description="Restart a configured server (e.g. Minecraft)",
    )
    @app_commands.describe(
        server="Friendly name of the server to restart (e.g. Minecraft)"
    )
    @app_commands.autocomplete(server=server_autocomplete)
    @has_command_permission("restart")
    async def restart(
        self, interaction: discord.Interaction, server: str = ""
    ):
        """Restart an allowed server using its friendly alias, keeping internal container names secret."""
        guild_id = interaction.guild_id or 0
        db = getattr(self.bot, "db", None)

        aliases = (
            await db.get_container_aliases(guild_id, DEFAULT_CONTAINER_ALIASES)
            if db
            else DEFAULT_CONTAINER_ALIASES
        )

        if not aliases:
            await interaction.response.send_message(
                "❌ No servers have been configured for restarting on this Discord server.",
                ephemeral=True,
            )
            return

        # Determine target alias
        target_alias = server.strip() if server else next(iter(aliases.keys()))

        # Check if the requested alias exists
        if target_alias not in aliases:
            available = ", ".join(f"`{a}`" for a in aliases.keys())
            await interaction.response.send_message(
                f"❌ Unknown server `{target_alias}`.\n"
                f"Available servers to restart: {available}",
                ephemeral=True,
            )
            return

        # Resolve internal container name confidentially
        internal_container = aliases[target_alias]

        # Defer interaction while restarting
        await interaction.response.defer()

        start_time = time.monotonic()
        logger.info(
            f"Server '{target_alias}' (internal container '{internal_container}') restart initiated "
            f"by {interaction.user.name} ({interaction.user.id}) in {interaction.guild.name}"
        )

        try:
            # Run blocking docker call in thread pool
            await asyncio.to_thread(_sync_restart_container, internal_container)
            duration = round(time.monotonic() - start_time, 2)

            embed = discord.Embed(
                title="🔄 Server Restarted",
                description=f"Server **`{target_alias}`** has been successfully restarted.",
                color=0x2ECC71,
            )
            embed.add_field(name="Server", value=f"`{target_alias}`", inline=True)
            embed.add_field(name="Duration", value=f"`{duration}s`", inline=True)
            embed.add_field(name="Triggered By", value=interaction.user.mention, inline=True)

            logger.info(f"Server '{target_alias}' restarted successfully in {duration}s.")
            await interaction.followup.send(embed=embed)

        except NotFound:
            logger.warning(
                f"Host container for alias '{target_alias}' was not found on Docker."
            )
            await interaction.followup.send(
                f"❌ The host service for **`{target_alias}`** could not be reached. Please inform an administrator.",
                ephemeral=True,
            )
        except DockerException as e:
            logger.exception(f"Docker API error while restarting '{target_alias}': {e}")
            await interaction.followup.send(
                f"❌ An error occurred while restarting **`{target_alias}`**.",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception(f"Unexpected error restarting server '{target_alias}': {e}")
            await interaction.followup.send(
                f"❌ Unexpected error occurred.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(DockerManagement(bot))
