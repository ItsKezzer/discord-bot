import aiosqlite
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("discord.bot.database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS command_permissions (
    guild_id INTEGER NOT NULL,
    command_name TEXT NOT NULL,
    target_type TEXT NOT NULL, -- 'role' or 'user'
    target_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, command_name, target_type, target_id)
);

CREATE TABLE IF NOT EXISTS container_aliases (
    guild_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    container_name TEXT NOT NULL,
    PRIMARY KEY (guild_id, alias)
);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    # --- Command Permissions ---

    async def get_command_permissions(
        self, guild_id: int, command_name: str
    ) -> Dict[str, List[int]]:
        """Return dict with 'roles' and 'users' lists of IDs for the given command."""
        result: Dict[str, List[int]] = {"roles": [], "users": []}
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT target_type, target_id FROM command_permissions WHERE guild_id = ? AND command_name = ?",
                (guild_id, command_name),
            ) as cursor:
                async for row in cursor:
                    target_type, target_id = row[0], row[1]
                    if target_type == "role":
                        result["roles"].append(target_id)
                    elif target_type == "user":
                        result["users"].append(target_id)
        return result

    async def add_command_permission(
        self, guild_id: int, command_name: str, target_type: str, target_id: int
    ) -> bool:
        """Add a role or user permission. Returns True if newly added, False if already existed."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO command_permissions (guild_id, command_name, target_type, target_id) VALUES (?, ?, ?, ?)",
                    (guild_id, command_name, target_type, target_id),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_command_permission(
        self, guild_id: int, command_name: str, target_type: str, target_id: int
    ) -> bool:
        """Remove a role or user permission. Returns True if removed."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM command_permissions WHERE guild_id = ? AND command_name = ? AND target_type = ? AND target_id = ?",
                (guild_id, command_name, target_type, target_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def clear_command_permissions(
        self, guild_id: int, command_name: str
    ) -> int:
        """Remove all custom permissions for a command in a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM command_permissions WHERE guild_id = ? AND command_name = ?",
                (guild_id, command_name),
            )
            await db.commit()
            return cursor.rowcount

    # --- Container Aliases (Security & Friendly Naming) ---

    async def get_container_aliases(
        self, guild_id: int, default_aliases: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Return dict of {friendly_alias: real_container_name} for the guild."""
        if default_aliases is None:
            default_aliases = {"Minecraft": "mc-modded"}

        aliases: Dict[str, str] = {}
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT alias, container_name FROM container_aliases WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                async for row in cursor:
                    aliases[row[0]] = row[1]

        # If none have been saved yet for this guild, populate with default_aliases
        if not aliases:
            await self.reset_container_aliases(guild_id, default_aliases)
            return dict(default_aliases)

        return aliases

    async def set_container_alias(
        self, guild_id: int, alias: str, container_name: str
    ) -> None:
        """Insert or update a friendly alias for an internal container name."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO container_aliases (guild_id, alias, container_name)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, alias) DO UPDATE SET container_name = excluded.container_name
                """,
                (guild_id, alias.strip(), container_name.strip()),
            )
            await db.commit()

    async def remove_container_alias(self, guild_id: int, alias: str) -> bool:
        """Delete an alias by friendly name."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM container_aliases WHERE guild_id = ? AND alias = ?",
                (guild_id, alias.strip()),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def reset_container_aliases(
        self, guild_id: int, default_aliases: Dict[str, str]
    ) -> None:
        """Reset aliases to defaults."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM container_aliases WHERE guild_id = ?",
                (guild_id,),
            )
            for alias, container_name in default_aliases.items():
                await db.execute(
                    "INSERT INTO container_aliases (guild_id, alias, container_name) VALUES (?, ?, ?)",
                    (guild_id, alias, container_name),
                )
            await db.commit()
