import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

# Import the database initialization function
from db import init_db

from snipe import SnipeCog
from interactions import InteractionCog
from economy import EconomyCog
from leveling import LevelingCog  # ✅ Import the leveling cog

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")

if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN not found in .env file")
if not APPLICATION_ID:
    raise ValueError("❌ APPLICATION_ID not found in .env file")

try:
    APPLICATION_ID = int(APPLICATION_ID)
except ValueError:
    raise ValueError("❌ APPLICATION_ID must be an integer")

# Set up bot intents. Note that enabling members intent is important for features like confessions.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # This ensures you can use guild.get_member

# Initialize the bot with a valid prefix.
bot = commands.Bot(
    command_prefix="!", 
    intents=intents, 
    help_command=None, 
    application_id=APPLICATION_ID
)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()  # 🌐 Sync globally
        print(f"✅ Synced {len(synced)} global slash command(s).")
    except Exception as e:
        print(f"❌ Error syncing slash commands: {e}")

    # Print all registered commands
    print("Registered slash commands:")
    for command in bot.tree.walk_commands():
        print(f" - /{command.name}")

async def main():
    # Initialize the SQL database
    init_db()
    
    async with bot:
        await bot.load_extension("helplist")         # Load the help command extension (helplist.py)
        await bot.load_extension("minigames")          # Load minigames
        await bot.load_extension("confession")
        await bot.load_extension("backgrounds")
        await bot.load_extension("profile_card")       # Profile card cog
        await bot.load_extension("hearts")
        await bot.load_extension("status")
        await bot.add_cog(SnipeCog(bot))
        await bot.add_cog(InteractionCog(bot))
        await bot.add_cog(EconomyCog(bot))
        await bot.add_cog(LevelingCog(bot))  # Load LevelingCog
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot is stopping...")
        asyncio.run(bot.close())
        print("Bot stopped gracefully.")
