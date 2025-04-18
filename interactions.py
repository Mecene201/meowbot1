import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import random
from dotenv import load_dotenv

load_dotenv()
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY")

# Predefined messages for each interaction
INTERACTION_MESSAGES = {
    "hug": [
        "{user} gave {target} a warm hug! 🤗",
        "{user} hugged {target} tightly. Aww! 💖",
        "{user} pulled {target} into a comfy hug! ✨"
    ],
    "kiss": [
        "{user} gave {target} a sweet kiss! 😘",
        "{user} kissed {target} softly. 💋",
        "{user} planted a kiss on {target}! 🌸"
    ],
    "slap": [
        "{user} slapped {target}! That looked like it hurt! 😬",
        "{user} gave {target} a dramatic slap! 💥",
        "{user} slaps {target} with style and sass. 😤"
    ],
    "punch": [
        "{user} punched {target} like Goku! 👊",
        "{user} delivered a knockout punch to {target}! 🥊",
        "{user} punched {target} into the next scene! 💢"
    ]
}

class InteractionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_gif(self, action):
        async with aiohttp.ClientSession() as session:
            params = {
                "api_key": GIPHY_API_KEY,
                "q": f"anime {action}",
                "limit": 10,
                "rating": "pg-13"
            }
            async with session.get("https://api.giphy.com/v1/gifs/search", params=params) as resp:
                data = await resp.json()
                results = data.get("data", [])
                if not results:
                    return None
                return random.choice(results)["images"]["original"]["url"]

    async def interaction_response(self, interaction, action: str, target: discord.Member):
        if interaction.user.id == target.id:
            await interaction.response.send_message("You can't interact with yourself... that's kinda sad 😢")
            return

        gif_url = await self.fetch_gif(action)
        if not gif_url:
            await interaction.response.send_message("Couldn't fetch a GIF. Try again later!", ephemeral=True)
            return

        # Pick a fun message format with user mentions
        message = random.choice(INTERACTION_MESSAGES[action]).format(
            user=interaction.user.mention,
            target=target.mention
        )

        embed = discord.Embed(
            description=message,
            color=discord.Color.pink()
        )
        embed.set_image(url=gif_url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hug", description="Hug someone!")
    async def hug(self, interaction: discord.Interaction, member: discord.Member):
        await self.interaction_response(interaction, "hug", member)

    @app_commands.command(name="kiss", description="Kiss someone!")
    async def kiss(self, interaction: discord.Interaction, member: discord.Member):
        await self.interaction_response(interaction, "kiss", member)

    @app_commands.command(name="slap", description="Slap someone!")
    async def slap(self, interaction: discord.Interaction, member: discord.Member):
        await self.interaction_response(interaction, "slap", member)

    @app_commands.command(name="punch", description="Punch someone!")
    async def punch(self, interaction: discord.Interaction, member: discord.Member):
        await self.interaction_response(interaction, "punch", member)

async def setup(bot):
    await bot.add_cog(InteractionCog(bot))

