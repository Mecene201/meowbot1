import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os

from db import get_db  # get_db() returns an sqlite3.Connection

# Function to determine how much XP is needed for the next level
def xp_for_next_level(level):
    if level <= 20:
        xp_table = {
            1: 200,
            2: 1000,
            3: 1100,
            4: 1200,
            5: 1300,
            6: 1400,
            7: 1500,
            8: 1600,
            9: 1700,
            10: 1800,
            11: 2100,
            12: 2400,
            13: 2700,
            14: 3000,
            15: 3300,
            16: 3600,
            17: 3900,
            18: 4200,
            19: 4500,
            20: 4800
        }
        return xp_table[level]
    else:
        return int(4800 + (level - 20) * 400)

class LevelingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_user_level_info(self, user_id: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT level, xp FROM leveling WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            level, xp = row
        else:
            level, xp = 1, 0
            cursor.execute("INSERT INTO leveling (user_id, level, xp) VALUES (?, ?, ?)", (user_id, level, xp))
            conn.commit()
        conn.close()
        return {'level': level, 'xp': xp}

    def save_user_level_info(self, user_id: str, level: int, xp: int):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO leveling (user_id, level, xp) VALUES (?, ?, ?)", (user_id, level, xp))
        conn.commit()
        conn.close()

    async def add_xp(self, user_id: str, xp_gained: int):
        info = self.get_user_level_info(user_id)
        level = info['level']
        xp = info['xp'] + xp_gained

        # Level up as needed
        while xp >= xp_for_next_level(level):
            xp -= xp_for_next_level(level)
            level += 1

        self.save_user_level_info(user_id, level, xp)

    @app_commands.command(name="level", description="Check your current level and XP progress")
    async def level(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        info = self.get_user_level_info(user_id)
        level = info['level']
        xp = info['xp']
        xp_needed = xp_for_next_level(level)
        embed = discord.Embed(
            title=f"📊 {interaction.user.name}'s Level Stats",
            description=(
                f"**Level**: {level} 🌟\n"
                f"**XP**: {xp} / {xp_needed} 🔋\n"
                f"You're {xp_needed - xp} XP away from leveling up!"
            ),
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))




