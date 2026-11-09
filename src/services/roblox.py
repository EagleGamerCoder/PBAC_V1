"""Small asynchronous client for Roblox's public endpoints."""
from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class RobloxAPIError(RuntimeError):
    """Raised when a Roblox API request fails or returns invalid data."""


class RobloxService:
    BASE_USERS = "https://users.roblox.com"
    BASE_GROUPS = "https://groups.roblox.com"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            headers={
                "User-Agent": "PBAC-Verification/1.0",
                "Accept": "application/json",
            },
        )

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        for attempt in range(2):
            try:
                response = await self._client.request(
                    method, url, params=params, json=json_body
                )
                if response.status_code == 429:
                    if attempt == 0:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            delay = min(max(float(retry_after), 0.5), 3.0) if retry_after else 1.5
                        except ValueError:
                            delay = 1.5
                        logger.warning(
                            "Roblox rate limited %s %s; retrying once after %.1fs",
                            method,
                            url,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise RobloxAPIError(
                        "Roblox is temporarily rate-limiting requests. Wait a minute and try again."
                    )

                response.raise_for_status()
                data = response.json()
            except RobloxAPIError:
                raise
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (500, 502, 503, 504):
                    raise RobloxAPIError(
                        "Roblox is temporarily unavailable. Please try again shortly."
                    ) from exc
                raise RobloxAPIError(
                    f"Roblox rejected the request (HTTP {status}). Please try again later."
                ) from exc
            except (httpx.HTTPError, ValueError) as exc:
                raise RobloxAPIError(
                    "Roblox could not be reached or returned invalid data. Please try again shortly."
                ) from exc

            if not isinstance(data, dict):
                raise RobloxAPIError("Roblox returned an unexpected response.")
            return data

        raise RobloxAPIError(
            "Roblox is temporarily rate-limiting requests. Wait a minute and try again."
        )

    async def _get_json(self, url: str, *, params: dict | None = None) -> dict:
        return await self._request_json("GET", url, params=params)

    async def find_user(self, username: str) -> dict:
        """Resolve an exact Roblox username, not a fuzzy search result."""
        requested = username.strip()
        if not requested:
            raise RobloxAPIError("Enter your Roblox username.")

        data = await self._request_json(
            "POST",
            f"{self.BASE_USERS}/v1/usernames/users",
            json_body={"usernames": [requested], "excludeBannedUsers": False},
        )
        matches = [
            item
            for item in data.get("data", [])
            if isinstance(item, dict)
            and str(item.get("name", "")).casefold() == requested.casefold()
            and item.get("id") is not None
        ]
        if len(matches) != 1:
            if not matches:
                raise RobloxAPIError(
                    f"Roblox did not return an exact match for '{requested}'. "
                    "Check that you entered your current Roblox username, not your display name."
                )
            raise RobloxAPIError("Roblox returned an ambiguous username result. Please try again later.")

        user_id = int(matches[0]["id"])
        profile = await self.get_user(user_id)
        if int(profile.get("id", 0)) != user_id:
            raise RobloxAPIError("Roblox returned a mismatched profile. Please try again.")
        if str(profile.get("name", "")).casefold() != requested.casefold():
            raise RobloxAPIError("The Roblox username changed during lookup. Please start verification again.")
        return profile

    async def get_user(self, user_id: int) -> dict:
        if user_id <= 0:
            raise RobloxAPIError("A valid Roblox user ID is required.")
        return await self._get_json(f"{self.BASE_USERS}/v1/users/{user_id}")

    async def get_group_role(self, group_id: int, user_id: int) -> tuple[int, str, int]:
        """Return (Roblox role ID, role name, numerical group rank) for this group."""
        if group_id <= 0 or user_id <= 0:
            raise RobloxAPIError("A valid Roblox group ID and user ID are required.")

        data = await self._get_json(
            f"{self.BASE_GROUPS}/v2/users/{user_id}/groups/roles"
        )
        memberships = data.get("data", [])
        if not isinstance(memberships, list):
            raise RobloxAPIError("Roblox returned an unexpected group-membership response.")

        for membership in memberships:
            if not isinstance(membership, dict):
                continue
            group = membership.get("group")
            role = membership.get("role")
            if not isinstance(group, dict) or not isinstance(role, dict):
                continue
            try:
                membership_group_id = int(group.get("id", 0))
            except (TypeError, ValueError):
                continue
            if membership_group_id != group_id:
                continue

            try:
                role_id = int(role.get("id", 0))
                rank_number = int(role.get("rank", 0))
            except (TypeError, ValueError) as exc:
                raise RobloxAPIError("Roblox returned invalid group-rank information.") from exc
            if role_id <= 0:
                raise RobloxAPIError("Roblox returned an invalid group role ID.")
            return role_id, str(role.get("name") or "Unknown"), rank_number

        return 0, "Guest", 0

    async def check_group(self, group_id: int) -> bool:
        """Return whether the supplied Roblox group ID identifies a public group."""
        if group_id <= 0:
            return False
        try:
            data = await self._get_json(f"{self.BASE_GROUPS}/v1/groups/{group_id}")
        except RobloxAPIError as exc:
            if "HTTP 404" in str(exc):
                return False
            raise
        return bool(data.get("id")) and int(data.get("id", 0)) == group_id

    async def get_profile_description(self, user_id: int) -> str:
        profile = await self.get_user(user_id)
        return str(profile.get("description") or "")
