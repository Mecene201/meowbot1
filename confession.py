import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import json
import sqlite3
from datetime import datetime

from db import get_db  # Using our SQL helper

def get_confession_config() -> dict:
    """
    Queries the SQL database for confession configurations.
    Returns a dict mapping guild IDs (as strings) to confession channel IDs.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id, channel_id FROM confession_config")
    rows = cursor.fetchall()
    conn.close()
    config = {str(guild_id): str(channel_id) for guild_id, channel_id in rows}
    return config

def update_confession_config(guild_id: str, channel_id: str):
    """
    Inserts or updates the confession configuration for the given guild_id.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO confession_config (guild_id, channel_id) VALUES (?, ?)",
        (guild_id, channel_id)
    )
    conn.commit()
    conn.close()

def next_confession_number(guild_id: str) -> int:
    """
    Uses a table 'confession_counter' to get the next confession number for the guild.
    If no record exists for the guild, creates one starting at 1.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS confession_counter (guild_id TEXT PRIMARY KEY, count INTEGER NOT NULL)")
    cursor.execute("SELECT count FROM confession_counter WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    if row:
        count = row[0] + 1
        cursor.execute("UPDATE confession_counter SET count = ? WHERE guild_id = ?", (count, guild_id))
    else:
        count = 1
        cursor.execute("INSERT INTO confession_counter (guild_id, count) VALUES (?, ?)", (guild_id, count))
    conn.commit()
    conn.close()
    return count

class ConfessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_confessions = {}  # Track active confession sessions per user.

    @app_commands.command(name="setconfession", description="Set the confession channel for this server.")
    @app_commands.describe(channel="The channel where confessions should be sent")
    async def set_confession(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "You do not have permission to configure the confession channel.", ephemeral=True
            )
        guild_id = str(interaction.guild.id)
        channel_id = str(channel.id)
        update_confession_config(guild_id, channel_id)
        await interaction.response.send_message(
            f"Confession channel set to {channel.mention} for this server.", ephemeral=True
        )

    @app_commands.command(name="confess", description="Send your anonymous confession via DM.")
    async def confess(self, interaction: discord.Interaction):
        try:
            dm_channel = await interaction.user.create_dm()
            await dm_channel.send(
                "Hi! Please reply with your anonymous confession. Your confession will be sent to a server with a configured confession channel."
            )
            await interaction.response.send_message("I've sent you a DM. Check your DMs to continue.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("I couldn't send you a DM. Check your DM settings.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Process only direct messages (DMs) from non-bots.
        if message.author.bot or message.guild is not None:
            return

        user_id = message.author.id
        if user_id in self.active_confessions:
            return
        self.active_confessions[user_id] = True

        try:
            await message.channel.send("Would you like to send an anonymous confession? (Reply with `yes` or `no`)")
            def check(m: discord.Message):
                return m.author == message.author and m.channel == message.channel

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                await message.channel.send("Timed out. Please try again later.")
                return

            if reply.content.lower() not in ("yes", "y"):
                await message.channel.send("Okay, not sending a confession.")
                return

            config = get_confession_config()
            eligible = []
            for guild in self.bot.guilds:
                if guild.get_member(user_id) and str(guild.id) in config:
                    eligible.append(guild)

            if not eligible:
                await message.channel.send(
                    "You are not in any server with a confession channel configured. Ask an admin to run `/setconfession`."
                )
                return

            list_msg = "Choose a server for your confession by typing its number:\n"
            for idx, guild in enumerate(eligible, start=1):
                list_msg += f"{idx}. {guild.name}\n"
            await message.channel.send(list_msg)

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=60)
                selection = int(reply.content.strip())
                if not (1 <= selection <= len(eligible)):
                    await message.channel.send("Invalid selection number.")
                    return
            except asyncio.TimeoutError:
                await message.channel.send("Response timed out. Please try again later.")
                return
            except ValueError:
                await message.channel.send("Invalid input; please enter a number.")
                return

            selected_guild = eligible[selection - 1]
            await message.channel.send(f"You selected **{selected_guild.name}**. Now type your confession:")
            try:
                confession_reply = await self.bot.wait_for("message", check=check, timeout=120)
            except asyncio.TimeoutError:
                await message.channel.send("Time expired. Please try again later.")
                return

            channel_id = config.get(str(selected_guild.id))
            if not channel_id:
                await message.channel.send("The confession channel is not configured for that server.")
                return
            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                await message.channel.send("Could not locate the confession channel. Contact an admin.")
                return

            # Get the next confession number and set the current timestamp in the embed.
            number = next_confession_number(str(selected_guild.id))
            embed = discord.Embed(
                title=f"Anonymous Confession #{number}",
                description=confession_reply.content,
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow()
            )
            await channel.send(embed=embed)
            await message.channel.send("Your confession has been sent anonymously!")
        finally:
            if user_id in self.active_confessions:
                del self.active_confessions[user_id]

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfessionCog(bot))


