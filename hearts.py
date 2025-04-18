import discord
from discord.ext import commands
from discord import app_commands, Interaction
import sqlite3
from datetime import datetime, timedelta

from db import get_db  # get_db() returns the database connection

class HeartsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ HeartsCog initialized")

    # Helper: Fetch hearts data for a user from the database.
    def get_hearts_data(self, user_id: str) -> dict:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT hearts, last_given FROM hearts WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"hearts": row[0], "last_given": row[1] if row[1] else None}
        else:
            return {"hearts": 0, "last_given": None}

    # Helper: Update hearts data for a user in the database.
    def update_hearts_data(self, user_id: str, hearts: int, last_given: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO hearts (user_id, hearts, last_given) VALUES (?, ?, ?)
        """, (user_id, hearts, last_given))
        conn.commit()
        conn.close()

    @app_commands.command(name="hearts", description="Give 1 heart to another user (once every 24 hours)")
    @app_commands.describe(user="The user you want to give a heart to")
    async def hearts(self, interaction: Interaction, user: discord.User):
        giver_id = str(interaction.user.id)
        receiver_id = str(user.id)

        # Prevent giving a heart to yourself.
        if giver_id == receiver_id:
            await interaction.response.send_message("❌ You can't give a heart to yourself.", ephemeral=True)
            return

        now = datetime.utcnow()
        giver_data = self.get_hearts_data(giver_id)
        last_given_str = giver_data.get("last_given")
        if last_given_str:
            last_given = datetime.fromisoformat(last_given_str)
            if now - last_given < timedelta(hours=24):
                remaining = timedelta(hours=24) - (now - last_given)
                hours, remainder = divmod(remaining.seconds, 3600)
                minutes = remainder // 60
                await interaction.response.send_message(
                    f"🕒 You can give another heart in **{remaining.days}d {hours}h {minutes}m**.",
                    ephemeral=True
                )
                return

        # Update receiver's hearts.
        receiver_data = self.get_hearts_data(receiver_id)
        new_hearts = receiver_data["hearts"] + 1
        self.update_hearts_data(receiver_id, new_hearts, receiver_data.get("last_given") or '')

        # Update giver's last_given timestamp.
        self.update_hearts_data(giver_id, giver_data["hearts"], now.isoformat())

        # Add 10 XP to receiver using leveling cog.
        leveling_cog = self.bot.get_cog("LevelingCog")
        if leveling_cog:
            await leveling_cog.add_xp(receiver_id, 10)

        embed = discord.Embed(
            title="💖 Heart Given!",
            description=(
                f"{interaction.user.mention} gave a heart to {user.mention}!\n\n"
                "They also gained **+10 XP** 📈"
            ),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(HeartsCog(bot))

