import discord
from discord.ext import commands

class StatusCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Set the bot's presence/status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="I am become death"
        )
        await self.bot.change_presence(status=discord.Status.online, activity=activity)
        print(f"[STATUS] Bot is online and status set!")

async def setup(bot):
    await bot.add_cog(StatusCog(bot))
