import datetime
import time
import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import check_member_permission


class General(commands.Cog):
    """General utility commands like ping and help."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.datetime.now(datetime.timezone.utc)

    @app_commands.command(name="ping", description="Check bot latency and status")
    async def ping(self, interaction: discord.Interaction):
        """Displays gateway latency, API response time, and bot uptime."""
        start = time.monotonic()
        await interaction.response.defer(ephemeral=False)
        roundtrip = round((time.monotonic() - start) * 1000)
        gateway_ping = round(self.bot.latency * 1000)

        uptime = datetime.datetime.now(datetime.timezone.utc) - self.start_time
        days, remainder = divmod(int(uptime.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = (
            f"{days}d {hours}h {minutes}m {seconds}s"
            if days
            else f"{hours}h {minutes}m {seconds}s"
        )

        embed = discord.Embed(
            title="🏓 Pong!",
            color=0x2ECC71,
        )
        embed.add_field(
            name="Gateway Latency", value=f"`{gateway_ping}ms`", inline=True
        )
        embed.add_field(name="API Round-trip", value=f"`{roundtrip}ms`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime_str}`", inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="help", description="Show available commands and your permissions"
    )
    async def help(self, interaction: discord.Interaction):
        """Dynamic help listing commands and indicating which ones you have permission to use."""
        embed = discord.Embed(
            title="🤖 Bouloumbele Bot Help",
            description="Here are the available slash commands for this server:",
            color=0x3498DB,
        )

        member = (
            interaction.user
            if isinstance(interaction.user, discord.Member)
            else None
        )
        guild = interaction.guild
        db = getattr(self.bot, "db", None)

        commands_info = [
            ("ping", "Check bot latency, API round-trip, and uptime", "Everyone"),
            ("help", "Display this command list and your permissions", "Everyone"),
            ("restart", "Restart a configured server (e.g. Minecraft)", "restart"),
            ("purge", "Bulk delete between 1 and 100 messages in the channel", "purge"),
            ("kick", "Kick a member with an optional reason", "kick"),
            ("timeout", "Timeout (mute) a member for a given duration (max 28d)", "timeout"),
            ("untimeout", "Remove an active timeout from a member early", "timeout"),
            ("rolemenu", "Create an interactive button role menu for self-assigning roles", "rolemenu"),
            ("config", "Interactive panel to manage command permissions and server mappings", "admin"),
        ]

        for cmd_name, desc, perm_type in commands_info:
            status = "✅ Allowed"
            if perm_type == "Everyone":
                status = "✅ Everyone"
            elif perm_type == "admin":
                if member and (
                    member.guild_permissions.administrator
                    or member.id == guild.owner_id
                ):
                    status = "✅ Administrator"
                else:
                    status = "🔒 Admin Only"
            elif member and guild and db:
                allowed = await check_member_permission(guild, member, perm_type, db)
                status = "✅ Allowed for you" if allowed else "🔒 No Permission"

            embed.add_field(
                name=f"`/{cmd_name}` • {status}",
                value=desc,
                inline=False,
            )

        embed.set_footer(
            text="Tip: Administrators can manage who can run commands using /config"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
