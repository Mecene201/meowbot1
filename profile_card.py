import discord
from discord import app_commands, Interaction
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps
from io import BytesIO
import traceback
import os
import time
import requests

from db import get_db  # SQL helper
from leveling import xp_for_next_level  # For XP calculations

# Constants for fonts and fallback banner image.
FONT_PATH = "fonts/Roboto-Bold.ttf"
BANNER_PATH = "image-850x300.jpg"
TARGET_SIZE = (626, 346)  # Desired background size

# Helper functions for About Me using SQL.
def get_about(user_id: str) -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT about FROM about_me WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    else:
        return "No About Me set."

def set_about(user_id: str, text: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO about_me (user_id, about) VALUES (?, ?)", (user_id, text))
    conn.commit()
    conn.close()

class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.banner_path = BANNER_PATH
        self.cooldowns = {}  # Map user_id -> last command timestamp.
        print("✅ ProfileCog initialized")

    @app_commands.command(name="setabout", description="Set your About Me text")
    @app_commands.describe(text="What should your profile say?")
    async def setabout(self, interaction: Interaction, text: str):
        if len(text) > 25:
            await interaction.response.send_message("❌ Your About Me can only be up to 25 characters.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        set_about(user_id, text)
        await interaction.response.send_message("✅ About Me updated!", ephemeral=True)

    @app_commands.command(name="profile", description="View a visual profile card")
    @app_commands.describe(user="Pick a member or leave blank to view your own profile")
    async def profile(self, interaction: Interaction, user: discord.User = None):
        try:
            # Determine target user.
            user_obj = user or interaction.user
            user_id_str = str(user_obj.id)

            if not interaction.response.is_done():
                await interaction.response.defer()

            # Simple cooldown check.
            now = time.time()
            last_used = self.cooldowns.get(user_id_str, 0)
            if now - last_used < 3:
                await interaction.followup.send("⏳ Please wait a few seconds before using this again.", ephemeral=True)
                return
            self.cooldowns[user_id_str] = now

            # Retrieve leveling data.
            leveling_cog = self.bot.get_cog("LevelingCog")
            level_data = leveling_cog.get_user_level_info(user_id_str) if leveling_cog else {'level': 1, 'xp': 0}
            level = level_data['level']
            xp = level_data['xp']
            xp_needed = xp_for_next_level(level)

            # Retrieve hearts via the HeartsCog helper.
            hearts = 0
            hearts_cog = self.bot.get_cog("HeartsCog")
            if hearts_cog:
                user_hearts = hearts_cog.get_hearts_data(user_id_str)
                hearts = user_hearts.get("hearts", 0)

            # Retrieve About Me.
            about = get_about(user_id_str)

            # Load avatar.
            avatar_bytes = await user_obj.display_avatar.read()
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA")

            # Get background from Backgrounds cog.
            backgrounds_cog = self.bot.get_cog("Backgrounds")
            bg_source = backgrounds_cog.get_equipped_background_image(user_id_str) if backgrounds_cog else None

            # Load background image from URL (if starts with "http") or from file.
            if bg_source and bg_source.startswith("http"):
                response = requests.get(bg_source)
                response.raise_for_status()
                banner = Image.open(BytesIO(response.content)).convert("RGBA")
            else:
                banner_path = bg_source if bg_source and os.path.exists(bg_source) else self.banner_path
                banner = Image.open(banner_path).convert("RGBA")

            # Force resize background to TARGET_SIZE using LANCZOS filter.
            if banner.size != TARGET_SIZE:
                banner = banner.resize(TARGET_SIZE, resample=Image.LANCZOS)
            # Log the final size.
            print(f"Final background size: {banner.size}")

            # Create base image.
            base = banner.copy()
            draw = ImageDraw.Draw(base)

            # Load fonts.
            try:
                font_large = ImageFont.truetype(FONT_PATH, size=28)
                font_small = ImageFont.truetype(FONT_PATH, size=20)
            except Exception:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Draw avatar with circular mask.
            AVATAR_SIZE = 120
            avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))
            mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
            avatar.putalpha(mask)
            base.paste(avatar, (30, 36), avatar)

            # Draw username with overlay.
            username = f"{user_obj.name}"
            user_bbox = draw.textbbox((0, 0), username, font=font_large)
            overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
            ImageDraw.Draw(overlay).rectangle([180, 30, 180 + user_bbox[2], 30 + user_bbox[3]], fill=(50, 50, 50, 160))
            base = Image.alpha_composite(base, overlay)
            draw = ImageDraw.Draw(base)
            draw.text((180, 30), username, font=font_large, fill="white")

            # Draw XP progress bar.
            bar_x, bar_y, bar_width, bar_height = 180, 95, 400, 20
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], fill="gray")
            progress = xp / xp_needed if xp_needed > 0 else 0
            draw.rectangle([bar_x, bar_y, bar_x + int(bar_width * progress), bar_y + bar_height], fill="limegreen")
            level_text = f"Level {level} — XP: {xp}/{xp_needed}"
            level_text_x = bar_x + bar_width - draw.textlength(level_text, font=font_small)
            level_text_y = bar_y - 25
            level_bbox = draw.textbbox((0, 0), level_text, font=font_small)
            ImageDraw.Draw(base).rectangle(
                [level_text_x - 5, level_text_y - 2, level_text_x + level_bbox[2] + 5, level_text_y + level_bbox[3] + 2],
                fill=(50, 50, 50, 160)
            )
            draw.text((level_text_x, level_text_y), level_text, font=font_small, fill="white")

            # Draw hearts.
            hearts_text = f"{hearts} Hearts"
            hearts_bbox = draw.textbbox((0, 0), hearts_text, font=font_small)
            ImageDraw.Draw(base).rectangle(
                [180, 125, 180 + hearts_bbox[2] + 8, 125 + hearts_bbox[3] + 2],
                fill=(50, 50, 50, 160)
            )
            draw.text((180, 125), hearts_text, font=font_small, fill="white")

            # Draw About Me text with overlay.
            about_x, about_y, about_padding = 30, 230, 10
            about_bbox = draw.textbbox((0, 0), about, font=font_small)
            about_width = about_bbox[2] - about_bbox[0]
            about_height = about_bbox[3] - about_bbox[1]
            overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [about_x - about_padding, about_y - about_padding,
                 about_x + about_width + about_padding, about_y + about_height + about_padding],
                fill=(50, 50, 50, 160)
            )
            base = Image.alpha_composite(base, overlay)
            draw = ImageDraw.Draw(base)
            draw.text((about_x, about_y), about, font=font_small, fill="white")

            # Save the image to a buffer and send it as a file.
            buffer = BytesIO()
            base.save(buffer, format="PNG")
            buffer.seek(0)
            await interaction.followup.send(file=discord.File(fp=buffer, filename="profile.png"))

        except Exception:
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Failed to generate profile card.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))

