import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import time

from db import get_db  # Using our SQL helper

# Hard-coded image URLs.
BACKGROUND_DATA = {
    "default": {
        "name": "Default Background",
        "price": 0,
        "image": "https://mecene201.github.io/profilecards/default.jpg"
    },
    "bg1": {
        "name": "Sakura Street",
        "price": 1000,
        "image": "https://mecene201.github.io/profilecards/sakura_street.jpg"
    },
    "bg2": {
        "name": "Neon Racer",
        "price": 5000,
        "image": "https://mecene201.github.io/profilecards/racecar.jpg"
    },
    "bg3": {
        "name": "Hashira",
        "price": 10000,
        "image": "https://mecene201.github.io/profilecards/hashira.jpg"
    },
    "bg4": {
        "name": "Totoro",
        "price": 12000,
        "image": "https://mecene201.github.io/profilecards/totoro.jpg"
    }
}

BACKGROUNDS_PER_PAGE = 1  # Adjust as needed.

class Backgrounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # SQL Helper: Retrieve background data.
    def get_user_background_data(self, user_id: str) -> dict:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT backgrounds, equipped_bg FROM profile_backgrounds WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            backgrounds_str, equipped_bg = row
            try:
                backgrounds = json.loads(backgrounds_str)
            except Exception:
                backgrounds = ["default"]
            return {"backgrounds": backgrounds, "equipped_bg": equipped_bg}
        else:
            default_data = {"backgrounds": ["default"], "equipped_bg": "default"}
            self.update_user_background_data(user_id, default_data)
            return default_data

    # SQL Helper: Update background data.
    def update_user_background_data(self, user_id: str, data: dict):
        conn = get_db()
        cursor = conn.cursor()
        backgrounds_str = json.dumps(data.get("backgrounds", ["default"]))
        equipped_bg = data.get("equipped_bg", "default")
        cursor.execute(
            "INSERT OR REPLACE INTO profile_backgrounds (user_id, backgrounds, equipped_bg) VALUES (?, ?, ?)",
            (user_id, backgrounds_str, equipped_bg)
        )
        conn.commit()
        conn.close()

    # Get currently equipped image URL.
    def get_equipped_background_image(self, user_id: str) -> str:
        user_data = self.get_user_background_data(user_id)
        bg_id = user_data.get("equipped_bg", "default")
        bg_info = BACKGROUND_DATA.get(bg_id, BACKGROUND_DATA["default"])
        return bg_info.get("image", "")

    # Purchase a background.
    def try_purchase_background(self, user_id: str, item_id: str) -> tuple[bool, str]:
        if item_id not in BACKGROUND_DATA or item_id == "default":
            return False, "This item is not purchasable."
        user_data = self.get_user_background_data(user_id)
        if item_id in user_data["backgrounds"]:
            return False, "You already own this background."
        price = BACKGROUND_DATA[item_id]["price"]
        user_data["backgrounds"].append(item_id)
        self.update_user_background_data(user_id, user_data)
        return True, f"Successfully bought **{BACKGROUND_DATA[item_id]['name']}** for ${price}!"

    @app_commands.command(name="equip_background", description="Equip a profile background by ID.")
    @app_commands.describe(id="The background ID to equip")
    async def equip_background(self, interaction: discord.Interaction, id: str):
        user_id = str(interaction.user.id)
        user_data = self.get_user_background_data(user_id)
        if id not in user_data["backgrounds"]:
            return await interaction.response.send_message("You don't own this background.", ephemeral=True)
        user_data["equipped_bg"] = id
        self.update_user_background_data(user_id, user_data)
        temp_path = self.get_and_edit_background(user_id)
        file = discord.File(temp_path, filename="profile.png")
        await interaction.response.send_message(f"Equipped background: **{BACKGROUND_DATA[id]['name']}**", file=file)
        try:
            os.remove(temp_path)
        except Exception:
            pass

    @app_commands.command(name="backgroundshop", description="View available profile backgrounds for purchase")
    async def backgroundshop(self, interaction: discord.Interaction):
        try:
            await self.send_background_page(interaction, page=0)
        except Exception:
            await interaction.response.send_message("❌ Something went wrong!", ephemeral=True)

    @app_commands.command(name="buy_background", description="Buy a profile background by its ID.")
    @app_commands.describe(id="The background ID to buy")
    async def buy_background(self, interaction: discord.Interaction, id: str):
        user_id = str(interaction.user.id)
        result, message = self.try_purchase_background(user_id, id)
        if result:
            await interaction.response.send_message(f"✅ {message}")
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

    async def send_background_page(self, interaction: discord.Interaction, page: int):
        user_id = str(interaction.user.id)
        user_data = self.get_user_background_data(user_id)
        all_ids = list(BACKGROUND_DATA.keys())
        max_page = (len(all_ids) - 1) // BACKGROUNDS_PER_PAGE
        page = max(0, min(page, max_page))
        start = page * BACKGROUNDS_PER_PAGE
        end = start + BACKGROUNDS_PER_PAGE
        page_ids = all_ids[start:end]
        bg_id = page_ids[0]
        bg_data = BACKGROUND_DATA[bg_id]
        # Apply tax evasion discount: Get the EconomyCog and check if tax evasion is active.
        economy_cog = self.bot.get_cog("EconomyCog")
        if economy_cog and economy_cog.is_upgrade_active(user_id, "tax_evasion"):
            discounted_price = int(bg_data["price"] * 0.9)
        else:
            discounted_price = bg_data["price"]
        image_url = bg_data["image"]

        embed = discord.Embed(
            title=f"🎨 Background Shop (Page {page+1}/{max_page+1})",
            description="Use `/equip_background [id]` to equip it after buying.\nUse `/buy_background [id]` to purchase.",
            color=discord.Color.purple()
        )
        embed.add_field(name="🖼️ Name", value=bg_data["name"], inline=True)
        embed.add_field(name="💰 Price", value=f"${discounted_price}", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{bg_id}`", inline=True)

        if bg_id in user_data["backgrounds"]:
            embed.set_footer(text="✅ You already own this background.")
        elif bg_id == "default":
            embed.set_footer(text="🎁 This is the default background (automatically owned).")
        else:
            embed.set_footer(text="Use `/buy_background [id]` to purchase this background.")
        embed.set_image(url=image_url)

        view = BackgroundShopPagination(self.send_background_page, page, max_page)

        if interaction.type == discord.InteractionType.component:
            try:
                await interaction.message.delete()
            except Exception:
                pass
            try:
                await interaction.channel.send(embed=embed, view=view)
            except Exception:
                pass
        else:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, view=view)
                else:
                    await interaction.followup.send(embed=embed, view=view)
            except Exception:
                pass

    def get_and_edit_background(self, user_id: str):
        user_data = self.get_user_background_data(user_id)
        bg_id = user_data.get("equipped_bg", "default")
        image_url = BACKGROUND_DATA.get(bg_id, BACKGROUND_DATA["default"])["image"]
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            target_size = (626, 346)
            if img.size != target_size:
                img = img.resize(target_size)
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except Exception:
                font = ImageFont.load_default()
            text = "Profile Card"
            draw.text((10, 10), text, font=font, fill=(255, 255, 255, 255))
            temp_path = f"temp_bg_{user_id}_{int(time.time())}.png"
            img.save(temp_path)
            return temp_path
        except Exception:
            return "image-850x300.jpg"

class BackgroundShopPagination(discord.ui.View):
    def __init__(self, callback, page, max_page):
        super().__init__(timeout=60)
        self.callback = callback
        self.page = page
        self.max_page = max_page

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_page = self.page - 1
        await self.callback(interaction, new_page)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_page = self.page + 1
        await self.callback(interaction, new_page)

async def setup(bot: commands.Bot):
    await bot.add_cog(Backgrounds(bot))
