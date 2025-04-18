import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Load environment variables from a .env file (if using dotenv)
load_dotenv()

# Bot invite link and support server link stored in environment variables.
INVITE_URL = os.getenv("BOT_INVITE_URL")
SUPPORT_SERVER_URL = os.getenv("SUPPORT_SERVER_URL")

# Define your commands grouped by category.
COMMAND_CATEGORIES = {
    "🔧 Utilities": {
        "snipe": "Retrieve the last deleted message."
    },
    "😊 Social Interactions": {
        "hearts": "Send hearts to someone special.",
        "hug": "Send a hug to another user.",
        "kiss": "Send a kiss to another user.",
        "slap": "Slap another user playfully.",
        "punch": "Punch another user (playful, use with caution)."
    },
    "🎲 Gambling": {
        "coinflip_single": "Flip a coin once.",
        "coinflip_multi": "Flip coins multiple times.",
        "blackjack": "Play a game of blackjack."
    },
    "🎨 Customization & Profile": {
        "equip_background": "Equip a background from your collection.",
        "backgroundshop": "Browse available backgrounds in the shop.",
        "buy_background": "Purchase a new background.",
        "setabout": "Set your 'about' section in your profile.",
        "profile": "View your profile information."
    },
    "💌 Confessions": {
        "setconfession": "Set your confession status.",
        "confess": "Submit your confession anonymously."
    },
    "💰 Economy": {
        "activity": "View your current activity statistics.",
        "buy": "Buy an item from the shop.",
        "inventory": "Check your current inventory.",
        "balance": "Display your current balance.",
        "sell": "Sell an item from your inventory.",
        "shop": "Browse available items in the shop.",
        "activate": "Activate an item or feature.",
        "level": "Display your current level and progress."
    }
}

class LinkView(discord.ui.View):
    def __init__(self, invite_url: str, support_url: str):
        super().__init__()
        # Create a button that redirects to your bot invite link.
        self.add_item(discord.ui.Button(label="Invite Bot", url=invite_url))
        # Create a second button that redirects users to your support server.
        self.add_item(discord.ui.Button(label="Support Server", url=support_url))

class HelpList(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Shows the help menu for the bot.")
    async def help(self, interaction: discord.Interaction):
        """
        Sends an embedded help message that shows available commands organized by category,
        and includes buttons for both the bot invite and support server.
        """
        embed = discord.Embed(
            title="Bot Commands Help",
            description="Below is a list of all available commands organized by category:",
            color=discord.Color.blue()
        )
        
        # Iterate through each command category and add its commands to the embed.
        for category, commands_dict in COMMAND_CATEGORIES.items():
            command_lines = []
            for command, description in commands_dict.items():
                command_lines.append(f"**/{command}**: {description}")
            embed.add_field(name=category, value="\n".join(command_lines), inline=False)
        
        # Create a view containing buttons for bot invite and support server.
        view = LinkView(INVITE_URL, SUPPORT_SERVER_URL)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpList(bot))
