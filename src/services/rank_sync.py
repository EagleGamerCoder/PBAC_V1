"""Synchronise verified Discord members with British Army Roblox group ranks.

Only broad category roles are managed here. Exact Roblox ranks are represented
in nicknames, never as individual Discord roles.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import discord
from src.database.repositories.verification_repository import VerificationRepository

logger = logging.getLogger(__name__)


class RankSyncService:
    """Apply configured category roles and nickname prefixes."""

    def __init__(
        self, database, roblox, *, project_root: Path, nickname_format: str,
        bod_field_marshal_user_id: int = 0, bod_second_in_command_user_id: int = 0,
    ) -> None:
        self.database = database
        self.roblox = roblox
        self.mapping_path = project_root / "data" / "verification" / "rank_mapping.json"
        self.nickname_format = nickname_format
        self.bod_field_marshal_user_id = bod_field_marshal_user_id
        self.bod_second_in_command_user_id = bod_second_in_command_user_id

    def load_config(self) -> dict:
        try:
            data = json.loads(self.mapping_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Could not load rank mapping %s: %s", self.mapping_path, exc)
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _role_id(value) -> int | None:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else None
        except (TypeError, ValueError):
            return None

    async def _apply_roles(self, member: discord.Member, desired_ids: set[int], managed_ids: set[int]) -> None:
        roles_by_id = {role.id: role for role in member.guild.roles}
        missing = desired_ids - roles_by_id.keys()
        if missing:
            raise ValueError("Configured Discord role(s) not found: " + ", ".join(map(str, sorted(missing))))

        current_ids = {role.id for role in member.roles}
        remove = [role for role in member.roles if role.id in managed_ids and role.id not in desired_ids]
        add = [roles_by_id[role_id] for role_id in desired_ids if role_id not in current_ids]
        if remove:
            await member.remove_roles(*remove, reason="PBAC British Army verification/rank synchronisation")
        if add:
            await member.add_roles(*add, reason="PBAC British Army verification/rank synchronisation")

    async def sync_member(self, member: discord.Member, *, update_record: bool = True) -> tuple[bool, str]:
        async with self.database.session() as session:
            repo = VerificationRepository(session)
            account = await repo.get_by_discord_id(member.id)
            if account is None:
                return False, "This Discord member does not have a linked Roblox account."

            profile = await self.roblox.get_user(account.roblox_user_id)
            current_username = str(profile.get("name") or account.roblox_username)
            rank_id, rank_name = await self.roblox.get_group_rank(account.roblox_user_id)
            config = self.load_config()
            global_roles = config.get("roles", {})
            rank_mapping = config.get("ranks", {})

            # Only these broad roles are managed by this feature. No individual
            # Roblox-rank roles are read, assigned, or removed.
            managed_ids = {
                role_id
                for role_id in (self._role_id(value) for value in global_roles.values())
                if role_id is not None
            }
            desired_ids: set[int] = set()
            verified_id = self._role_id(global_roles.get("verified"))
            if verified_id:
                desired_ids.add(verified_id)

            if rank_id == 0:
                civilian_id = self._role_id(global_roles.get("civilian"))
                if civilian_id:
                    desired_ids.add(civilian_id)
                abbreviation = "CIV"
                display_rank = "Civilian"
                result_text = "Not in the British Army group; assigned Verified and Civilian roles."
            else:
                entry = rank_mapping.get(str(rank_id))
                if not isinstance(entry, dict):
                    return False, (
                        f"Roblox rank **{rank_name}** (ID `{rank_id}`) has no mapping configured. "
                        "No roles or nickname were changed."
                    )

                for role_key in entry.get("role_keys", []):
                    role_id = self._role_id(global_roles.get(role_key))
                    if role_id:
                        desired_ids.add(role_id)
                abbreviation = str(entry.get("abbreviation") or rank_name)
                # The two BOD members share one Roblox group rank. Their Roblox
                # user IDs distinguish the server owner from the 2IC.
                if entry.get("name") == "Board of Directors" or str(rank_id) == str(config.get("bod_rank_id", "")):
                    if account.roblox_user_id == self.bod_field_marshal_user_id and self.bod_field_marshal_user_id:
                        abbreviation = "FM"
                    elif account.roblox_user_id == self.bod_second_in_command_user_id and self.bod_second_in_command_user_id:
                        abbreviation = "2IC"
                display_rank = rank_name
                result_text = f"Synchronised **{rank_name}** (Roblox rank `{rank_id}`)."

            try:
                await self._apply_roles(member, desired_ids, managed_ids)
                nickname = self.nickname_format.format(
                    rank=display_rank,
                    rank_abbr=abbreviation,
                    username=current_username,
                )
                await member.edit(nick=nickname[:32], reason="PBAC British Army rank synchronisation")
            except discord.Forbidden:
                return False, "I lack permission to update this member's roles or nickname. Check my role hierarchy and permissions."
            except (discord.HTTPException, ValueError) as exc:
                logger.exception("Discord rank sync failed for member_id=%s", member.id)
                return False, f"Could not complete Discord synchronisation: {exc}"

            if update_record:
                account.roblox_username = current_username
                account.roblox_rank_id = rank_id
                account.roblox_rank_name = rank_name
                account.last_synced_at = datetime.utcnow()
                await session.commit()
            return True, result_text
