"""Verification challenge orchestration."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from src.database.models.verification_model import VerificationChallenge, VerifiedAccount
from src.database.repositories.server_setup_repository import ServerSetupRepository
from src.database.repositories.verification_repository import VerificationRepository
from src.services.roblox import RobloxService, RobloxAPIError


def _utcnow_naive() -> datetime:
    """Return UTC now as a naive value for the existing DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class VerificationError(RuntimeError):
    """An expected verification workflow error."""


class VerificationService:
    def __init__(
        self,
        database,
        roblox: RobloxService,
        *,
        expiry_minutes: int,
        max_attempts: int,
    ) -> None:
        self.database = database
        self.roblox = roblox
        self.expiry_minutes = expiry_minutes
        self.max_attempts = max_attempts

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    async def begin(self, discord_user_id: int, username: str) -> tuple[str, int, str]:
        username = username.strip()
        if not username or len(username) > 20:
            raise VerificationError("Enter a valid Roblox username.")

        try:
            profile = await self.roblox.find_user(username)
        except RobloxAPIError as exc:
            raise VerificationError(str(exc)) from exc

        roblox_id = int(profile["id"])
        canonical_name = str(profile["name"])
        code = f"PBAC-{secrets.token_hex(4).upper()}"

        async with self.database.session() as session:
            repo = VerificationRepository(session)
            existing = await repo.get_by_roblox_id(roblox_id)
            if existing and existing.discord_user_id != discord_user_id:
                raise VerificationError(
                    "That Roblox account is already linked to another Discord account."
                )

            challenge = VerificationChallenge(
                discord_user_id=discord_user_id,
                roblox_user_id=roblox_id,
                roblox_username=canonical_name,
                challenge_hash=self._hash(code),
                expires_at=_utcnow_naive() + timedelta(minutes=self.expiry_minutes),
                attempts=0,
            )
            await repo.put_challenge(challenge)
            await session.commit()

        return code, roblox_id, canonical_name

    async def confirm(
        self,
        guild_id: int,
        discord_user_id: int,
    ) -> tuple[int, str, int, str]:
        async with self.database.session() as session:
            # The group is selected by the Discord server's /setup configure data.
            server_config = await ServerSetupRepository(session).get_configuration(guild_id)
            if server_config is None or server_config.roblox_group_id <= 0:
                raise VerificationError("This Discord server has not been configured yet. Ask an administrator to run /setup configure.")

            repo = VerificationRepository(session)
            challenge = await repo.get_challenge(discord_user_id)
            if challenge is None:
                raise VerificationError("You don't have an active verification. Start again using the verification panel.")
            if challenge.expires_at < _utcnow_naive():
                await repo.delete_challenge(discord_user_id)
                await session.commit()
                raise VerificationError("Your verification code has expired. Please start again.")
            if challenge.attempts >= self.max_attempts:
                await repo.delete_challenge(discord_user_id)
                await session.commit()
                raise VerificationError("You have reached the verification attempt limit. Start again.")

            try:
                description = await self.roblox.get_profile_description(challenge.roblox_user_id)
                # Roblox may return an empty description while profile
                # changes are unavailable or have not propagated.
                if not description.strip():
                    raise VerificationError("Roblox returned an empty profile description.\nYour verification attempt has not been used.\nPlease check your Roblox profile and try again shortly.")

                # Compare verification codes as individual tokens.
                profile_tokens = {self._hash(token.strip().upper()) for token in description.split() if token.strip()}
                found = challenge.challenge_hash in profile_tokens

                if not found:
                    challenge.attempts += 1
                    await session.commit()

                    remaining = max(0, self.max_attempts - challenge.attempts)
                    raise VerificationError(f"Your verification code was not found in your\nRoblox profile description.\nAttempts remaining: {remaining}.")

                role_id, rank_name, _rank_number = await self.roblox.get_group_role(server_config.roblox_group_id, challenge.roblox_user_id)
            except RobloxAPIError as exc:
                raise VerificationError(str(exc)) from exc

            linked_elsewhere = await repo.get_by_roblox_id(challenge.roblox_user_id)
            if linked_elsewhere and linked_elsewhere.discord_user_id != discord_user_id:
                raise VerificationError("That Roblox account is already linked to another Discord account.")

            account = VerifiedAccount(
                discord_user_id=discord_user_id,
                roblox_user_id=challenge.roblox_user_id,
                roblox_username=challenge.roblox_username,
                # Store the Roblox role ID consistently (not the numerical rank).
                roblox_rank_id=role_id,
                roblox_rank_name=rank_name,
                verified_at=_utcnow_naive(),
                last_synced_at=_utcnow_naive(),
            )

            await repo.save_account(account)
            await repo.delete_challenge(discord_user_id)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise VerificationError("This Roblox account is already linked to another Discord account.") from exc

            return (challenge.roblox_user_id, challenge.roblox_username, role_id, rank_name)

    async def get_link(self, discord_user_id: int) -> VerifiedAccount | None:
        async with self.database.session() as session:
            return await VerificationRepository(session).get_by_discord_id(discord_user_id)

    async def unlink(self, discord_user_id: int) -> bool:
        async with self.database.session() as session:
            repo = VerificationRepository(session)
            account = await repo.get_by_discord_id(discord_user_id)
            if account is None:
                return False
            await repo.delete_account(discord_user_id)
            await session.commit()
            return True
