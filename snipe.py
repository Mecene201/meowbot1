import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import asyncio

class SnipeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sniped_messages = {}  # Dictionary to store deleted messages

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Stores the last deleted message for each channel (for 10 seconds)."""
        if message.author.bot:
            return

        channel_id = message.channel.id
        self.sniped_messages[channel_id] = {
            "author": message.author,
            "content": message.content,
            "timestamp": datetime.now(timezone.utc)
        }

        # Wait 10 seconds and then delete the snipe
        await asyncio.sleep(10)
        # Only delete if it hasn’t been overwritten with a newer snipe
        if channel_id in self.sniped_messages and self.sniped_messages[channel_id]["content"] == message.content:
            del self.sniped_messages[channel_id]

    @app_commands.command(name="snipe", description="Retrieve the last deleted message in this channel.")
    async def snipe(self, interaction: discord.Interaction):
        channel_id = interaction.channel.id
        sniped = self.sniped_messages.get(channel_id)

        if not sniped:
            await interaction.response.send_message("No messages have been deleted recently!", ephemeral=True)
            return

        embed = discord.Embed(
            description=sniped["content"],
            color=discord.Color.red(),
            timestamp=sniped["timestamp"]
        )
        embed.set_footer(text=f"Sniped by {interaction.user.name}")
        embed.set_author(name=sniped["author"].name, icon_url=sniped["author"].display_avatar.url)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SnipeCog(bot))


