import discord
from discord import app_commands


class CommandPermissionDenied(app_commands.AppCommandError):
    def __init__(self, command_name: str):
        self.command_name = command_name
        super().__init__(
            f"You do not have permission to run `/{command_name}` on this server."
        )


async def check_member_permission(
    guild: discord.Guild,
    member: discord.Member,
    command_name: str,
    db,
) -> bool:
    """Evaluate whether a member has permission to run a command."""
    # 1. Guild owner & server administrators always have permission
    if member.id == guild.owner_id or member.guild_permissions.administrator:
        return True

    # 2. Check dynamic database permissions
    perms = await db.get_command_permissions(guild.id, command_name)
    allowed_roles = set(perms.get("roles", []))
    allowed_users = set(perms.get("users", []))

    # If specific users or roles are configured for this command:
    if allowed_roles or allowed_users:
        if member.id in allowed_users:
            return True
        member_role_ids = {role.id for role in member.roles}
        if member_role_ids & allowed_roles:
            return True
        return False

    # 3. Default fallback if no custom roles/users are set
    if command_name == "purge":
        return member.guild_permissions.manage_messages
    elif command_name == "kick":
        return member.guild_permissions.kick_members
    elif command_name == "timeout":
        return member.guild_permissions.moderate_members
    elif command_name == "rolemenu":
        return member.guild_permissions.manage_roles
    elif command_name == "restart":
        # Docker restart defaults to administrator only
        return member.guild_permissions.administrator

    return False


def has_command_permission(command_name: str):
    """Slash command decorator enforcing command permission checks."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            raise app_commands.AppCommandError(
                "This command can only be used in a server."
            )

        db = getattr(interaction.client, "db", None)
        if not db:
            raise app_commands.AppCommandError("Database service is unavailable.")

        allowed = await check_member_permission(
            interaction.guild, interaction.user, command_name, db
        )
        if not allowed:
            raise CommandPermissionDenied(command_name)

        return True

    return app_commands.check(predicate)
