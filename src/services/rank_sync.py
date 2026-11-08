"""Synchronise verified Discord members with British Army Roblox group ranks.

The synchroniser always adds the four banner roles and Verified role. It manages
only the configured rank/category roles up to and including Leadership.
Administrative, logging, timezone, booster, developer and community roles below
Leadership are deliberately outside its scope and are never added or removed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import discord
from src.database.repositories.verification_repository import VerificationRepository

logger = logging.getLogger(__name__)

# Explicit allowlist: everything after "leadership" in the supplied role map is
# intentionally ignored by verification and rank synchronisation.
ALWAYS_ASSIGN_KEYS = ("verified", "banner1", "banner2", "banner3", "banner4")
MANAGED_RANK_KEYS = ("civilian", "recruit", "enlisted", "officer", "officer_perms", "genstaff", "senior_genstaff", "regimental_sergeant_major", "cos", "leadership")
MANAGED_ROLE_KEYS = set(ALWAYS_ASSIGN_KEYS) | set(MANAGED_RANK_KEYS)


class RankSyncService:
    """Apply verification, category roles and nickname prefixes."""

    def __init__(self, database, roblox, *, project_root: Path, nickname_format: str, bod_field_marshal_user_id: int = 0, bod_second_in_command_user_id: int = 0) -> None:
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
            raise ValueError(f"Configured Discord role(s) not found: {", ".join(map(str, sorted(missing)))}")

        current_ids = {role.id for role in member.roles}
        remove = [role for role in member.roles if role.id in managed_ids and role.id not in desired_id]
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
            role_id, rank_name, rank_number = await self.roblox.get_group_role(account.roblox_user_id)

            config = self.load_config()
            if not config:
                return False, "The rank mapping could not be loaded. No Discord roles or nickname were changed."
            global_roles = config.get("roles", {})
            rank_mapping = config.get("ranks", {})

            # Validate required base roles before attempting any Discord changes.
            desired_ids: set[int] = set()
            for key in ALWAYS_ASSIGN_KEYS:
                role_id = self._role_id(global_roles.get(key))
                if role_id is None:
                    return False, (f"Required role key '{key}' is missing or invalid in\ndata/verification/rank_mapping.json. No roles or nickname were changed.")
                desired_ids.add(role_id)

            """Only this explicit allowlist is managed. Roles below Leadership in
            the JSON file are neither read for assignment nor touched for removal."""
            managed_ids = {role_id for key in MANAGED_ROLE_KEYS if (role_id := self._role_id(global_roles.get(key))) is not None}

            entry = rank_mapping.get(str(role_id)) if role_id != 0 else None
            known_rank = role_id == 0 or isinstance(entry, dict)

            if not known_rank:
                """Still grant the base verification/banner roles, but do not guess
                a category, strip any existing category role, or change nickname.
                On an unmapped rank, manage only the base verification/banner
                roles. Existing rank/category roles are left untouched as well."""

                base_managed_ids = {self._role_id(global_roles.get(key)) for key in ALWAYS_ASSIGN_KEYS if self._role_id(global_roles.get(key)) is not None}
                await self._apply_roles(member, desired_ids, base_managed_ids)
                return True, (
                    f"Your account is verified and the four banner roles plus Verified role "
                    f"have been assigned. Your Roblox rank **{rank_name}** (`{role_id}`) "
                    "is not yet mapped, so existing rank roles and nickname were left unchanged. "
                    "Please contact an administrator."
                )

            if role_id == 0:
                civilian_id = self._role_id(global_roles.get("civilian"))
                if civilian_id is None:
                    return False, "The civilian role ID is missing or invalid. No rank roles or nickname were changed."
                desired_ids.add(civilian_id)
                abbreviation = "CIV"
                display_rank = "Civilian"
                result_text = "Not in the British Army group; assigned Verified, banner and Civilian roles."
            else:
                role_keys = entry.get("role_keys", [])
                if not isinstance(role_keys, list):
                    return False, f"Invalid role_keys for Roblox rank `{role_id}`. No rank roles or nickname were changed."

                unknown_keys = [key for key in role_keys if key not in MANAGED_RANK_KEYS]
                if unknown_keys:
                    return False, (
                        f"Rank mapping for **{rank_name}** contains unsupported role key(s): "
                        f"{', '.join(map(str, unknown_keys))}. No rank roles or nickname were changed."
                    )

                for role_key in role_keys:
                    role_id = self._role_id(global_roles.get(role_key))
                    if role_id is None:
                        return False, (
                            f"Role ID for '{role_key}' is missing or invalid. "
                            "No rank roles or nickname were changed."
                        )
                    desired_ids.add(role_id)

                abbreviation = str(entry.get("abbreviation") or rank_name)
                is_bod = (str(entry.get("abbreviation", "")).upper() == "BOD")
                if is_bod:
                    if (account.roblox_user_id == self.bod_field_marshal_user_id and self.bod_field_marshal_user_id):
                        abbreviation = "1IC"
                    elif (account.roblox_user_id == self.bod_second_in_command_user_id and self.bod_second_in_command_user_id):
                        abbreviation = "2IC"

                display_rank = str(entry.get("name") or rank_name)
                result_text = f"Synchronised **{rank_name}** (Roblox rank `{role_id}`); banner and Verified roles are present."

            # Resolve and validate every desired role before making any changes.
            roles_by_id = {role.id for role in member.guild.roles}
            missing_desired = desired_ids - roles_by_id
            if missing_desired:
                return False, (
                    "Configured Discord role(s) not found: "
                    + ", ".join(map(str, sorted(missing_desired)))
                    + ". No roles or nickname were changed."
                )

            try:
                await self._apply_roles(member, desired_ids, managed_ids)
                nickname = self.nickname_format.format(
                    rank=display_rank,
                    rank_abbr=abbreviation,
                    username=current_username,
                )
                await member.edit(nick=nickname[:32], reason="PBAC British Army rank synchronisation")
            except discord.Forbidden:
                return False, ("I lack permission to update this member's roles or nickname. \nCheck my Manage Roles permission and role hierarchy.")
            except (discord.HTTPException, ValueError, KeyError) as exc:
                logger.exception("Discord rank sync failed for member_id=%s", member.id)
                return False, f"Could not complete Discord synchronisation: {exc}"

            if update_record:
                account.roblox_username = current_username
                account.roblox_rank_id = rank_number
                account.roblox_rank_name = rank_name
                account.last_synced_at = datetime.utcnow()
                await session.commit()
            return True, result_text
