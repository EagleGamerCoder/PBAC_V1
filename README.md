# PBA Command

Discord bot for Polvito's British Army Roblox account verification and rank synchronisation.

## Installation

1. Use Python 3.11 or newer (the project is tested with Python 3.14-compatible dependencies).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in `DISCORD_BOT_TOKEN` and `GUILD_ID`.
4. Start the bot from the project root:
   ```bash
   python -m src.core.main
   ```
The bot creates missing database tables at startup. `create_all` does not alter existing tables; use a database migration if you change an existing model schema in a later release.

## Per-server setup

Roblox group IDs are **not** read from `.env`. Each Discord server configures its own group:

1. Give the bot the required channel and role permissions, including Manage Roles.
2. Run `/setup configure` as a server administrator.
3. Enter that server's Roblox group ID, verification channel ID and rules channel ID.
4. Optionally enter up to three information channel IDs in the final field, separated by commas.
5. The bot validates the group and channels, saves the configuration against the Discord server ID, and posts the panels.

Verification and rank synchronisation retrieve the group ID saved for the member's current Discord server. A server without a saved setup cannot verify or synchronise ranks.

`GUILD_ID` in `.env` is only the development guild used to register slash commands; it is not a Roblox group ID. The `data/verification/rank_mapping.json` role IDs are currently shared by all servers, so the mapped Discord roles must exist in each server where rank synchronisation is used.

## Version History
### v0.2.1
- Refined all details from v0.1.5
- Fixed bugs
- Added more to README
- Changed how the Roblox group ids are stored

### v0.1.5
- Added per-server configuration
- Removed temp banner & added banner
- Added README
- Fixed bugs
