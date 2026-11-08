import datetime
import logging
import re
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import has_command_permission

logger = logging.getLogger("discord.bot.moderation")

DURATION_REGEX = re.compile(
    r"^((?P<days>\d+)\s*d)?\s*((?P<hours>\d+)\s*h)?\s*((?P<minutes>\d+)\s*m)?\s*((?P<seconds>\d+)\s*s)?$",
    re.IGNORECASE,
)


def parse_duration(duration_str: str) -> Optional[datetime.timedelta]:
    """Parse duration string like '10m', '2h', '1d', '3d 12h' into timedelta."""
    match = DURATION_REGEX.match(duration_str.strip())
    if not match:
        return None

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
    if total_seconds <= 0 or total_seconds > (28 * 86400):  # Discord limit: 28 days
        return None

    return datetime.timedelta(seconds=total_seconds)


class Moderation(commands.Cog):
    """Server moderation commands: purge, kick, timeout, and untimeout."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="purge",
        description="Delete the last n messages in this channel (max: 100)",
    )
    @app_commands.describe(count="Number of messages to delete (1 - 100)")
    @has_command_permission("purge")
    async def purge(
        self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]
    ):
        """Bulk delete messages from the current channel."""
        if not interaction.channel or not isinstance(
            interaction.channel,
            (discord.TextChannel, discord.Thread, discord.VoiceChannel),
        ):
            await interaction.response.send_message(
                "❌ Purge can only be performed in text channels or threads.",
                ephemeral=True,
            )
            return

        # Check bot permissions
        if not interaction.channel.permissions_for(
            interaction.guild.me
        ).manage_messages:
            await interaction.response.send_message(
                "❌ I do not have permission to delete messages in this channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=count)
            logger.info(
                f"{len(deleted)} messages purged in {interaction.guild.name}/#{interaction.channel.name} by {interaction.user.name}"
            )
            await interaction.followup.send(
                f"🗑️ Successfully deleted **{len(deleted)}** message(s).",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permissions to delete messages.", ephemeral=True
            )
        except Exception as e:
            logger.exception(f"Error purging messages: {e}")
            await interaction.followup.send(
                f"❌ Failed to delete messages: `{e}`", ephemeral=True
            )

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(
        member="The member to kick",
        reason="Optional reason for the kick",
    )
    @has_command_permission("kick")
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        """Kick a member from the guild with hierarchy and permission checks."""
        guild = interaction.guild
        author = interaction.user

        # Safety checks
        if member.id == author.id:
            await interaction.response.send_message(
                "❌ You cannot kick yourself.", ephemeral=True
            )
            return

        if member.id == self.bot.user.id:
            await interaction.response.send_message(
                "❌ I cannot kick myself.", ephemeral=True
            )
            return

        if member.id == guild.owner_id:
            await interaction.response.send_message(
                "❌ You cannot kick the server owner.", ephemeral=True
            )
            return

        # Hierarchy check between author and target
        if author.id != guild.owner_id and member.top_role >= author.top_role:
            await interaction.response.send_message(
                "❌ You cannot kick someone with a role equal to or higher than your own.",
                ephemeral=True,
            )
            return

        # Hierarchy check between bot and target
        if member.top_role >= guild.me.top_role:
            await interaction.response.send_message(
                "❌ My highest role is not high enough to kick this member.",
                ephemeral=True,
            )
            return

        if not guild.me.guild_permissions.kick_members:
            await interaction.response.send_message(
                "❌ I do not have the 'Kick Members' permission in this server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            full_reason = f"Kicked by {author.name} ({author.id}): {reason}"
            await member.kick(reason=full_reason)
            logger.info(
                f"{member.name} ({member.id}) kicked from {guild.name} by {author.name}. Reason: {reason}"
            )

            embed = discord.Embed(
                title="👢 Member Kicked",
                color=0xE74C3C,
            )
            embed.add_field(
                name="User",
                value=f"{member.mention} (`{member.id}`)",
                inline=True,
            )
            embed.add_field(name="Kicked By", value=author.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)

            await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Discord rejected the kick (Missing Permissions).",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception(f"Error kicking member {member}: {e}")
            await interaction.followup.send(
                f"❌ Failed to kick member: `{e}`", ephemeral=True
            )

    @app_commands.command(
        name="timeout",
        description="Timeout (mute) a member for a specified duration (max 28 days)",
    )
    @app_commands.describe(
        member="The member to timeout",
        duration="Duration (e.g. 10m, 2h, 1d, 7d)",
        reason="Reason for the timeout",
    )
    @has_command_permission("timeout")
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str,
        reason: str = "No reason provided",
    ):
        """Put a member in timeout."""
        guild = interaction.guild
        author = interaction.user

        td = parse_duration(duration)
        if not td:
            await interaction.response.send_message(
                "❌ Invalid duration format. Examples: `10m`, `2h`, `1d`, `7d` (maximum: `28d`).",
                ephemeral=True,
            )
            return

        if member.id == author.id:
            await interaction.response.send_message(
                "❌ You cannot timeout yourself.", ephemeral=True
            )
            return

        if member.id == self.bot.user.id:
            await interaction.response.send_message(
                "❌ I cannot timeout myself.", ephemeral=True
            )
            return

        if member.id == guild.owner_id:
            await interaction.response.send_message(
                "❌ You cannot timeout the server owner.", ephemeral=True
            )
            return

        if author.id != guild.owner_id and member.top_role >= author.top_role:
            await interaction.response.send_message(
                "❌ You cannot timeout someone with a role equal to or higher than your own.",
                ephemeral=True,
            )
            return

        if member.top_role >= guild.me.top_role:
            await interaction.response.send_message(
                "❌ My highest role is not high enough to timeout this member.",
                ephemeral=True,
            )
            return

        if not guild.me.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "❌ I do not have the 'Timeout Members' permission in this server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            until = discord.utils.utcnow() + td
            full_reason = f"Timeout by {author.name} ({author.id}): {reason}"
            await member.timeout(until, reason=full_reason)

            until_unix = int(until.timestamp())
            embed = discord.Embed(
                title="⏱️ Member Timed Out",
                color=0xF39C12,
            )
            embed.add_field(
                name="Member",
                value=f"{member.mention} (`{member.id}`)",
                inline=True,
            )
            embed.add_field(name="Timed Out By", value=author.mention, inline=True)
            embed.add_field(name="Duration", value=f"`{duration}` (Expires <t:{until_unix}:R>)", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)

            logger.info(
                f"{member.name} timed out for {duration} in {guild.name} by {author.name}"
            )
            await interaction.followup.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Discord rejected the timeout (Missing Permissions).",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception(f"Error timing out member: {e}")
            await interaction.followup.send(
                f"❌ Failed to timeout member: `{e}`", ephemeral=True
            )

    @app_commands.command(
        name="untimeout",
        description="Remove a timeout from a member early",
    )
    @app_commands.describe(
        member="The member to remove timeout from",
        reason="Reason for removing the timeout",
    )
    @has_command_permission("timeout")
    async def untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Timeout removed early",
    ):
        """Remove a timeout from a member."""
        if not member.is_timed_out():
            await interaction.response.send_message(
                f"ℹ️ {member.mention} is not currently timed out.", ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            full_reason = f"Timeout removed by {interaction.user.name}: {reason}"
            await member.timeout(None, reason=full_reason)

            embed = discord.Embed(
                title="⏱️ Timeout Removed",
                description=f"Timeout for {member.mention} has been lifted.",
                color=0x2ECC71,
            )
            embed.add_field(name="Removed By", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to remove timeout: `{e}`", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
