# Bouloumbele Bot v2

A modern, reworked Discord bot featuring dynamic in-Discord role and permission configuration, non-blocking Docker container management with internal name obfuscation, native timeouts, persistent interactive button role menus, and Discord Slash Commands (`/`).

---

## 🌟 Key Features

* **Slash Commands (`/`)**: Fully modernized Discord Application Commands with auto-completion, rich embeds, and validation.
* **On-The-Fly Permission Management (`/config`)**:
  * An interactive **in-Discord UI** built using Discord native `RoleSelect`, `UserSelect`, modals, and buttons.
  * Allows Server Administrators to grant or revoke access on the fly to commands (e.g. choose exactly which role or member can run `/restart` or `/timeout`) with **zero web hosting or OAuth setup**.
  * Backed by async SQLite (`aiosqlite`) persistent storage.
* **Secure Docker Management (`/restart`)**:
  * **Security & Container Obfuscation**: Users and chat never see real host Docker container names (e.g. `mc-modded`). Instead, friendly aliases (e.g. `Minecraft Modded`) are mapped in `/config` or via `.env`.
  * Non-blocking asynchronous restarts with autocomplete.
* **Persistent Button Role Menus (`/rolemenu`)**:
  * Interactive self-assignable role menus using native Discord buttons.
  * Click a button to toggle (add/remove) a role with ephemeral confirmation.
  * **Persistent across bot restarts** with zero database polling needed.
* **Extended Moderation Suite**:
  * `/timeout`: Put members in timeout for a given duration (`10m`, `2h`, `1d`, `7d`, up to `28d`) using Discord's native timeout system.
  * `/untimeout`: Remove an active timeout early.
  * `/purge`: Bulk delete between 1 and 100 messages with proper error handling and ephemeral feedback.
  * `/kick`: Kick members with hierarchy safety checks and audit log reason.
* **Utility**:
  * `/ping`: Displays gateway latency, API round-trip time, and bot uptime.
  * `/help`: Dynamic command list showing which commands you specifically have permission to execute.

---

## 📋 Slash Commands Overview

| Command | Description | Default Permission | Configurable via `/config`? |
| :--- | :--- | :--- | :--- |
| **`/ping`** | Check bot latency, API roundtrip, and uptime | Everyone | No |
| **`/help`** | View all commands and your permission status | Everyone | No |
| **`/restart [server]`** | Restart an allowed server (using friendly alias) | Administrators | **Yes** (Grant to any role or user) |
| **`/rolemenu`** | Build an interactive button role menu | Manage Roles / Admin | **Yes** (Grant to any role or user) |
| **`/timeout <member> <duration> [reason]`** | Timeout (mute) a member (e.g. `10m`, `2h`, `1d`) | Moderate Members / Admin | **Yes** (Grant to any role or user) |
| **`/untimeout <member> [reason]`** | Remove a timeout from a member early | Moderate Members / Admin | **Yes** (Grant to any role or user) |
| **`/purge <count>`** | Bulk delete 1 to 100 messages | Manage Messages / Admin | **Yes** (Grant to any role or user) |
| **`/kick <member> [reason]`** | Kick a member from the server | Kick Members / Admin | **Yes** (Grant to any role or user) |
| **`/config`** | Interactive settings panel for permissions & server mappings | Administrators only | Built-in security check |

---

## 🔒 Docker Security & Container Aliases

To keep host infrastructure secure:
1. Internal container names (such as `mc-modded` or `valheim-server`) are **hidden** from regular users and chat.
2. The bot exposes friendly aliases (like `Minecraft Modded`).
3. You can configure aliases in `/config` ➔ **Docker Server Mappings**, or via the `ALLOWED_CONTAINERS` environment variable:
   ```env
   ALLOWED_CONTAINERS="Minecraft:mc-modded,Valheim:valheim-server"
   ```
4. Autocomplete in `/restart` displays only friendly names, and command output only mentions the friendly alias.

---

## ⚙️ How On-The-Fly Permissions Work

1. A server Administrator runs **`/config`**.
2. An ephemeral control panel appears (invisible to other users):
   * Select a command from the dropdown (e.g. `🔄 /restart`, `⏱️ /timeout`, `🏷️ /rolemenu`).
   * Use the **Role Select** menu to toggle roles allowed to execute that command.
   * Use the **User Select** menu to toggle individual members.
   * Or click **Reset to Defaults** to return to standard Discord permissions.
3. To configure Server Mappings:
   * Select **🐳 Docker Server Mappings** from the menu.
   * Click **➕ Add Server Mapping** to input a Display Name and Internal Container Name via a modal.
   * Or select a mapping to remove it.
4. Changes are saved immediately to `bot.db` and take effect instantly.

---

## 🚀 Setup & Deployment

### Option A: Using Docker Compose (Recommended)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in your Discord Bot Token and server mappings:
   ```env
   TOKEN=your_discord_bot_token_here
   ALLOWED_CONTAINERS=Minecraft:mc-modded
   ```
3. Start the container:
   ```bash
   docker compose up -d --build
   ```
4. View logs:
   ```bash
   docker compose logs -f
   ```

### Option B: Running Locally

1. Create a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your token and run:
   ```bash
   export TOKEN="your_discord_bot_token_here"
   export ALLOWED_CONTAINERS="Minecraft:mc-modded"
   python app.py
   ```
