from datetime import datetime, timezone
from pathlib import Path

import discord

from src.core import __version__
from src.utils.constants import PBAC_RED, PBAC_YELLOW, PBAC_GREY
from src.utils.json_loader import load_json_object

# Project root:
PROJECT_ROOT = Path(__file__).resolve().parents[2]

BRANDING_DIR = PROJECT_ROOT / "assets" / "branding"
BADGE_PATH = BRANDING_DIR / "badge.png" 
BANNER_PATH = BRANDING_DIR / "anner.png"


def create_pbac_embed(*, title: str, description: str | None = None, colour: discord.Colour | None = None) -> tuple[discord.Embed, list[discord.File]]:
    """Create a consistently branded PBAC embed and its image attachments."""

    # Fail clearly if an expected graphic is missing.
    if not BADGE_PATH.is_file():
        raise FileNotFoundError(f"PBAC badge image was not found: {BADGE_PATH}")
    if not BANNER_PATH.is_file():
        raise FileNotFoundError(f"PBAC banner image was not found: {BANNER_PATH}")

    embed = discord.Embed(
        title=title,
        description=description,
        colour=colour or discord.Colour(PBAC_GREY)
    )
    
    # <<<< Removal to see UI Changes in 0.1.5
    # Department identity in the author area.
    #embed.set_author(
    #    name="POLVITO'S BRITISH ARMY COMMAND",
    #)
    
    # Wide image displayed beneath the embed's main content.
    embed.set_image(
        url="attachment://banner.png"
    )
    # A consistent footer on all SFD embeds.
    embed.set_footer(
        text=f"PBA Command • v{__version__} • {datetime.now(timezone.utc)}"
    )

    files = [
        discord.File(BADGE_PATH, filename="badge.png"),
        discord.File(BANNER_PATH, filename="banner.png"),
    ]

    return embed, files

def create_verification_panel() -> tuple[discord.Embed, list[discord.File]]:
    """Build the public PBAC account-verification panel from its JSON definition."""
    panel_path = PROJECT_ROOT / "data" / "panels" / "verification.json"
    panel = load_json_object(panel_path)

    title = str(panel.get("title", "Roblox Account Verification"))
    description = str(
        panel.get(
            "description",
            "Link your Roblox account to access the appropriate PBAC Discord channels.",
        )
    )
    embed, files = create_pbac_embed(
        title=title,
        description=description,
        colour=discord.Colour(PBAC_GREY)
    )

    instructions = panel.get("instructions", [])
    if isinstance(instructions, list) and instructions:
        instruction_text = "\n".join(
            f"{index}. {str(instruction)}"
            for index, instruction in enumerate(instructions, start=1)
        )
        embed.add_field(name="How it works", value=instruction_text, inline=False)

    privacy_notice = panel.get("privacy_notice")
    if privacy_notice:
        embed.add_field(name="Privacy", value=str(privacy_notice), inline=False)

    return embed, files
