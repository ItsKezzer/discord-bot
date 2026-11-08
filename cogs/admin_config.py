import logging
from typing import Dict, List, Optional
import discord
from discord import app_commands
from discord.ext import commands

from config import DEFAULT_CONTAINER_ALIASES

logger = logging.getLogger("discord.bot.config")

MANAGED_COMMANDS = [
    ("restart", "Docker server restart", "🔄"),
    ("purge", "Bulk message deletion", "🗑️"),
    ("kick", "Kick members", "👢"),
    ("timeout", "Timeout (mute) members", "⏱️"),
    ("rolemenu", "Create self-assignable role menus", "🏷️"),
]


class AddServerAliasModal(discord.ui.Modal, title="Add Server Mapping"):
    alias = discord.ui.TextInput(
        label="Friendly Display Name (Seen by users)",
        placeholder="e.g. Minecraft Modded, Valheim",
        required=True,
        max_length=50,
    )
    container_name = discord.ui.TextInput(
        label="Internal Docker Container Name (Hidden)",
        placeholder="e.g. mc-modded, valheim-server",
        required=True,
        max_length=100,
    )

    def __init__(self, parent_view: "ConfigDashboardView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        alias_val = self.alias.value.strip()
        container_val = self.container_name.value.strip()
        guild_id = interaction.guild_id or 0
        db = self.parent_view.bot.db

        await db.set_container_alias(guild_id, alias_val, container_val)
        aliases = await db.get_container_aliases(guild_id, DEFAULT_CONTAINER_ALIASES)
        embed = await self.parent_view.build_containers_embed(guild_id)
        self.parent_view.setup_containers_ui(guild_id, aliases)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ConfigDashboardView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild: discord.Guild, author: discord.Member):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.author = author
        self.current_section: str = "overview"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Only the administrator who opened this configuration panel can interact with it.",
                ephemeral=True,
            )
            return False
        return True

    async def build_overview_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚙️ Server Configuration & Permissions Dashboard",
            description=(
                "Use the menu below to select a command and assign which roles or members "
                "can run it, or configure Docker server aliases."
            ),
            color=0x3498DB,
        )

        db = self.bot.db
        guild_id = self.guild.id

        for cmd_name, desc, emoji in MANAGED_COMMANDS:
            perms = await db.get_command_permissions(guild_id, cmd_name)
            roles = perms.get("roles", [])
            users = perms.get("users", [])

            parts = []
            if roles:
                parts.append("Roles: " + ", ".join(f"<@&{r}>" for r in roles))
            if users:
                parts.append("Users: " + ", ".join(f"<@{u}>" for u in users))

            if not parts:
                if cmd_name == "restart":
                    fallback = "Administrators only"
                elif cmd_name == "purge":
                    fallback = "Manage Messages / Admin"
                elif cmd_name == "kick":
                    fallback = "Kick Members / Admin"
                elif cmd_name == "timeout":
                    fallback = "Moderate Members / Admin"
                elif cmd_name == "rolemenu":
                    fallback = "Manage Roles / Admin"
                else:
                    fallback = "Default"
                val = f"*{fallback}*"
            else:
                val = " • ".join(parts)

            embed.add_field(
                name=f"{emoji} /{cmd_name}",
                value=f"{desc}\n**Access:** {val}",
                inline=False,
            )

        aliases = await db.get_container_aliases(guild_id, DEFAULT_CONTAINER_ALIASES)
        aliases_str = (
            ", ".join(f"`{alias}`" for alias in aliases.keys())
            if aliases
            else "*None*"
        )
        embed.add_field(
            name="🐳 Configured Servers (/restart)",
            value=f"Public Names: {aliases_str}",
            inline=False,
        )

        embed.set_footer(text="Select an option below to modify settings on the fly.")
        return embed

    async def build_command_embed(self, command_name: str) -> discord.Embed:
        cmd_info = next(
            (item for item in MANAGED_COMMANDS if item[0] == command_name),
            (command_name, "", "⚡"),
        )
        emoji = cmd_info[2]
        desc = cmd_info[1]

        db = self.bot.db
        perms = await db.get_command_permissions(self.guild.id, command_name)
        roles = perms.get("roles", [])
        users = perms.get("users", [])

        embed = discord.Embed(
            title=f"{emoji} Configure Permissions for `/{command_name}`",
            description=f"**Description:** {desc}\n\n*Server Administrators always have permission to run every command.*",
            color=0x9B59B6,
        )

        roles_text = (
            "\n".join(f"• <@&{r}> (`{r}`)" for r in roles)
            if roles
            else "*No custom roles configured.*"
        )
        users_text = (
            "\n".join(f"• <@{u}> (`{u}`)" for u in users)
            if users
            else "*No individual users configured.*"
        )

        embed.add_field(name="Allowed Roles", value=roles_text, inline=True)
        embed.add_field(name="Allowed Users", value=users_text, inline=True)

        if not roles and not users:
            fallback = "Server Administrators only" if command_name == "restart" else "Standard Discord permission defaults"
            embed.add_field(
                name="Current Policy",
                value=f"Since no specific roles or users are configured, access defaults to: **{fallback}**.",
                inline=False,
            )
        else:
            embed.add_field(
                name="Current Policy",
                value="Only the specified roles/users above (plus Administrators) can run this command.",
                inline=False,
            )

        return embed

    async def build_containers_embed(self, guild_id: int) -> discord.Embed:
        db = self.bot.db
        aliases = await db.get_container_aliases(guild_id, DEFAULT_CONTAINER_ALIASES)

        embed = discord.Embed(
            title="🐳 Docker Server Mappings (Security & Aliases)",
            description=(
                "Map user-friendly server names to internal Docker container names.\n"
                "Regular members only see the friendly name when using `/restart`."
            ),
            color=0x1ABC9C,
        )

        if aliases:
            lines = [f"• **{alias}** ➔ `{container}` *(hidden from chat)*" for alias, container in aliases.items()]
            mappings_text = "\n".join(lines)
        else:
            mappings_text = "*No servers configured. `/restart` will be disabled until a server is mapped.*"

        embed.add_field(name="Configured Server Mappings", value=mappings_text, inline=False)
        embed.set_footer(text="Click 'Add Server Mapping' to add, or select one below to delete.")
        return embed

    def setup_overview_ui(self):
        self.clear_items()
        self.current_section = "overview"

        select = discord.ui.Select(
            placeholder="Select a command or feature to configure...",
            min_values=1,
            max_values=1,
        )

        for cmd_name, desc, emoji in MANAGED_COMMANDS:
            select.add_option(
                label=f"/{cmd_name}",
                value=cmd_name,
                description=desc[:100],
                emoji=emoji,
            )

        select.add_option(
            label="Docker Server Mappings",
            value="containers",
            description="Manage friendly server aliases and hidden container names",
            emoji="🐳",
        )

        async def select_callback(interaction: discord.Interaction):
            chosen = select.values[0]
            if chosen == "containers":
                await self.show_containers(interaction)
            else:
                await self.show_command(interaction, chosen)

        select.callback = select_callback
        self.add_item(select)

    async def show_command(self, interaction: discord.Interaction, command_name: str):
        self.current_section = command_name
        self.clear_items()

        # 1. Role Select
        role_select = discord.ui.RoleSelect(
            placeholder=f"Toggle role access for /{command_name}...",
            min_values=1,
            max_values=5,
        )

        async def role_callback(it: discord.Interaction):
            db = self.bot.db
            perms = await db.get_command_permissions(self.guild.id, command_name)
            current_roles = set(perms.get("roles", []))

            for role in role_select.values:
                if role.id in current_roles:
                    await db.remove_command_permission(
                        self.guild.id, command_name, "role", role.id
                    )
                else:
                    await db.add_command_permission(
                        self.guild.id, command_name, "role", role.id
                    )

            embed = await self.build_command_embed(command_name)
            await it.response.edit_message(embed=embed, view=self)

        role_select.callback = role_callback
        self.add_item(role_select)

        # 2. User Select
        user_select = discord.ui.UserSelect(
            placeholder=f"Toggle user access for /{command_name}...",
            min_values=1,
            max_values=5,
        )

        async def user_callback(it: discord.Interaction):
            db = self.bot.db
            perms = await db.get_command_permissions(self.guild.id, command_name)
            current_users = set(perms.get("users", []))

            for user in user_select.values:
                if user.id in current_users:
                    await db.remove_command_permission(
                        self.guild.id, command_name, "user", user.id
                    )
                else:
                    await db.add_command_permission(
                        self.guild.id, command_name, "user", user.id
                    )

            embed = await self.build_command_embed(command_name)
            await it.response.edit_message(embed=embed, view=self)

        user_select.callback = user_callback
        self.add_item(user_select)

        # 3. Clear button
        clear_btn = discord.ui.Button(
            label="Reset to Defaults",
            style=discord.ButtonStyle.danger,
            emoji="🔄",
        )

        async def clear_callback(it: discord.Interaction):
            await self.bot.db.clear_command_permissions(self.guild.id, command_name)
            embed = await self.build_command_embed(command_name)
            await it.response.edit_message(embed=embed, view=self)

        clear_btn.callback = clear_callback
        self.add_item(clear_btn)

        # 4. Back button
        back_btn = discord.ui.Button(
            label="Back to Overview",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
        )

        async def back_callback(it: discord.Interaction):
            self.setup_overview_ui()
            embed = await self.build_overview_embed()
            await it.response.edit_message(embed=embed, view=self)

        back_btn.callback = back_callback
        self.add_item(back_btn)

        embed = await self.build_command_embed(command_name)
        await interaction.response.edit_message(embed=embed, view=self)

    def setup_containers_ui(self, guild_id: int, aliases: Dict[str, str]):
        self.clear_items()
        self.current_section = "containers"

        # Add Server Mapping button
        add_btn = discord.ui.Button(
            label="Add Server Mapping",
            style=discord.ButtonStyle.success,
            emoji="➕",
        )

        async def add_callback(it: discord.Interaction):
            await it.response.send_modal(AddServerAliasModal(self))

        add_btn.callback = add_callback
        self.add_item(add_btn)

        # If there are aliases, provide a remove select
        if aliases:
            remove_select = discord.ui.Select(
                placeholder="Select a server mapping to remove...",
                min_values=1,
                max_values=1,
            )
            for alias in list(aliases.keys())[:25]:
                remove_select.add_option(
                    label=alias,
                    value=alias,
                    description=f"Removes alias for {aliases[alias]}"[:100],
                    emoji="🗑️",
                )

            async def remove_callback(it: discord.Interaction):
                alias_chosen = remove_select.values[0]
                await self.bot.db.remove_container_alias(guild_id, alias_chosen)
                updated_aliases = await self.bot.db.get_container_aliases(
                    guild_id, DEFAULT_CONTAINER_ALIASES
                )
                embed = await self.build_containers_embed(guild_id)
                self.setup_containers_ui(guild_id, updated_aliases)
                await it.response.edit_message(embed=embed, view=self)

            remove_select.callback = remove_callback
            self.add_item(remove_select)

        # Reset button
        reset_btn = discord.ui.Button(
            label="Reset to Defaults",
            style=discord.ButtonStyle.danger,
            emoji="🔄",
        )

        async def reset_callback(it: discord.Interaction):
            await self.bot.db.reset_container_aliases(
                guild_id, DEFAULT_CONTAINER_ALIASES
            )
            embed = await self.build_containers_embed(guild_id)
            self.setup_containers_ui(guild_id, DEFAULT_CONTAINER_ALIASES)
            await it.response.edit_message(embed=embed, view=self)

        reset_btn.callback = reset_callback
        self.add_item(reset_btn)

        # Back button
        back_btn = discord.ui.Button(
            label="Back to Overview",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
        )

        async def back_callback(it: discord.Interaction):
            self.setup_overview_ui()
            embed = await self.build_overview_embed()
            await it.response.edit_message(embed=embed, view=self)

        back_btn.callback = back_callback
        self.add_item(back_btn)

    async def show_containers(self, interaction: discord.Interaction):
        guild_id = self.guild.id
        aliases = await self.bot.db.get_container_aliases(
            guild_id, DEFAULT_CONTAINER_ALIASES
        )
        self.setup_containers_ui(guild_id, aliases)
        embed = await self.build_containers_embed(guild_id)
        await interaction.response.edit_message(embed=embed, view=self)


class AdminConfig(commands.Cog):
    """Server administrator configuration cog for permissions and settings."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="config",
        description="Open the in-Discord settings panel to manage permissions and server mappings",
    )
    @app_commands.default_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        """Open the interactive in-Discord control panel."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )
            return

        if not (
            interaction.user.guild_permissions.administrator
            or interaction.user.id == interaction.guild.owner_id
        ):
            await interaction.response.send_message(
                "❌ You must be a server Administrator to access `/config`.",
                ephemeral=True,
            )
            return

        view = ConfigDashboardView(self.bot, interaction.guild, interaction.user)
        view.setup_overview_ui()
        embed = await view.build_overview_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminConfig(bot))
