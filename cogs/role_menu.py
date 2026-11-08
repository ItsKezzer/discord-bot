import logging
from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands

from utils.checks import has_command_permission

logger = logging.getLogger("discord.bot.rolemenu")


class RoleMenuBuilderView(discord.ui.View):
    """Temporary builder view for an admin to select roles before posting the menu."""

    def __init__(
        self,
        bot: commands.Bot,
        target_channel: discord.TextChannel,
        title: str,
        description: str,
        author: discord.Member,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.target_channel = target_channel
        self.title = title
        self.description = description
        self.author = author
        self.selected_roles: List[discord.Role] = []

        # Role selector
        self.role_select = discord.ui.RoleSelect(
            placeholder="Select roles for this role menu (1-15)...",
            min_values=1,
            max_values=15,
        )
        self.role_select.callback = self.role_select_callback
        self.add_item(self.role_select)

        # Post button
        self.post_btn = discord.ui.Button(
            label="Post Role Menu",
            style=discord.ButtonStyle.success,
            emoji="🚀",
            disabled=True,
        )
        self.post_btn.callback = self.post_callback
        self.add_item(self.post_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Only the administrator who created this setup can use it.",
                ephemeral=True,
            )
            return False
        return True

    async def role_select_callback(self, interaction: discord.Interaction):
        self.selected_roles = list(self.role_select.values)
        self.post_btn.disabled = len(self.selected_roles) == 0

        roles_list = "\n".join(f"• {r.mention}" for r in self.selected_roles)
        embed = discord.Embed(
            title="🛠️ Role Menu Preview",
            description=f"**Target Channel:** {self.target_channel.mention}\n\n**Selected Roles:**\n{roles_list}",
            color=0x3498DB,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def post_callback(self, interaction: discord.Interaction):
        if not self.selected_roles:
            await interaction.response.send_message("❌ No roles selected.", ephemeral=True)
            return

        # Build public embed
        menu_embed = discord.Embed(
            title=self.title,
            description=self.description,
            color=0x2ECC71,
        )
        menu_embed.set_footer(text="Click a button below to claim or remove a role.")

        # Build persistent view
        menu_view = discord.ui.View(timeout=None)
        for role in self.selected_roles:
            btn = discord.ui.Button(
                label=role.name,
                style=discord.ButtonStyle.primary,
                custom_id=f"rolemenu:toggle:{role.id}",
                emoji="🏷️",
            )
            menu_view.add_item(btn)

        try:
            await self.target_channel.send(embed=menu_embed, view=menu_view)
            await interaction.response.edit_message(
                content=f"✅ Role menu successfully posted in {self.target_channel.mention}!",
                embed=None,
                view=None,
            )
        except Exception as e:
            logger.exception(f"Failed to post role menu: {e}")
            await interaction.response.send_message(
                f"❌ Failed to post role menu: `{e}`", ephemeral=True
            )


class RoleMenu(commands.Cog):
    """Self-assignable role menus using persistent interactive Discord buttons."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="rolemenu",
        description="Create an interactive button-based role menu for members to self-assign roles",
    )
    @app_commands.describe(
        title="Title of the role menu embed",
        description="Instructions or description in the embed",
        channel="Channel to post the role menu in (defaults to current channel)",
    )
    @has_command_permission("rolemenu")
    async def create_rolemenu(
        self,
        interaction: discord.Interaction,
        title: str = "🏷️ Self-Assignable Roles",
        description: str = "Click any button below to toggle that role on or off.",
        channel: Optional[discord.TextChannel] = None,
    ):
        """Interactive builder for self-assignable role menus."""
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Role menus can only be posted in text channels.", ephemeral=True
            )
            return

        # Check bot permissions in target channel
        perms = target_channel.permissions_for(interaction.guild.me)
        if not (perms.send_messages and perms.embed_links):
            await interaction.response.send_message(
                f"❌ I lack permission to send messages and embeds in {target_channel.mention}.",
                ephemeral=True,
            )
            return

        author = interaction.user if isinstance(interaction.user, discord.Member) else None
        view = RoleMenuBuilderView(self.bot, target_channel, title, description, author)
        embed = discord.Embed(
            title="🛠️ Role Menu Builder",
            description=(
                f"Select the roles you want to add to this menu using the dropdown below.\n"
                f"They will be posted to {target_channel.mention}."
            ),
            color=0x3498DB,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Persistent listener for role menu buttons across all channels and bot restarts."""
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("rolemenu:toggle:"):
            return

        role_id_str = custom_id.split("rolemenu:toggle:", 1)[1]
        try:
            role_id = int(role_id_str)
        except ValueError:
            return

        guild = interaction.guild
        member = interaction.user

        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ Role menus can only be used in servers.", ephemeral=True
            )
            return

        role = guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                "❌ This role no longer exists in the server.", ephemeral=True
            )
            return

        # Hierarchy check
        if role >= guild.me.top_role:
            await interaction.response.send_message(
                f"❌ My highest role is lower than {role.mention}, so I cannot assign or remove it.",
                ephemeral=True,
            )
            return

        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Self-assigned via Role Menu")
                await interaction.response.send_message(
                    f"❌ Removed role **{role.name}** from your profile.", ephemeral=True
                )
            else:
                await member.add_roles(role, reason="Self-assigned via Role Menu")
                await interaction.response.send_message(
                    f"✅ Added role **{role.name}** to your profile!", ephemeral=True
                )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Failed to update your roles: Missing permissions.", ephemeral=True
            )
        except Exception as e:
            logger.exception(f"Error toggling role {role.id} for user {member.id}: {e}")
            await interaction.response.send_message(
                f"❌ Failed to update role: `{e}`", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleMenu(bot))
