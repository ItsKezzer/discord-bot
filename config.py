import os
from pathlib import Path
from typing import Dict

# Discord bot token
TOKEN = os.getenv("TOKEN", "")

# Default allowed containers and user-friendly aliases
# Format can be: "Minecraft:mc-modded,Valheim:valheim-server" or simply "mc-modded"
ALLOWED_CONTAINERS_RAW = os.getenv("ALLOWED_CONTAINERS", "Minecraft:mc-modded")


def parse_default_aliases(raw: str) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            alias, container = item.split(":", 1)
            aliases[alias.strip()] = container.strip()
        else:
            # If no alias provided, title-case the container name
            aliases[item.replace("-", " ").title()] = item
    return aliases if aliases else {"Minecraft": "mc-modded"}


DEFAULT_CONTAINER_ALIASES = parse_default_aliases(ALLOWED_CONTAINERS_RAW)

# Database configuration
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
if not DATA_DIR.exists():
    # Fallback to local data directory if /data is not mounted
    DATA_DIR = Path(__file__).parent / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = str(DATA_DIR / "bot.db")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
