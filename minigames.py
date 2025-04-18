import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import random
import time
import sqlite3
import json
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import logging
import asyncio

# Configure logging for detailed debugging.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

MAX_COINFLIP_PLAYERS = 4

###########################################
# COINFLIP MULTIPLAYER CLASSES
###########################################

class CoinflipSession:
    def __init__(self, initiator: discord.User, bet: int, initiator_choice: str):
        self.initiator = initiator
        self.bet = bet
        # List of dictionaries: {"user": discord.User, "side": "heads" or "tails"}
        self.players = []
        self.message = None  # Will store the coinflip game message
        # Add initiator with chosen side.
        self.add_player(initiator, initiator_choice)

    def add_player(self, user: discord.User, side: str) -> bool:
        if any(p["user"].id == user.id for p in self.players):
            logging.debug(f"User {user.id} already joined the coinflip session.")
            return False
        if len(self.players) >= MAX_COINFLIP_PLAYERS:
            logging.debug("Coinflip session is full.")
            return False
        self.players.append({"user": user, "side": side})
        logging.debug(f"Added {user.display_name} with choice {side}.")
        return True

    def has_both_sides(self) -> bool:
        sides = {p["side"] for p in self.players}
        return len(sides) >= 2

    def total_pot(self) -> int:
        pot = self.bet * len(self.players)
        logging.debug(f"Total pot calculated: {pot}")
        return pot

    def winners(self, outcome: str):
        winners_list = [p for p in self.players if p["side"] == outcome]
        logging.debug(f"Found winners: {[(p['user'].display_name, p['side']) for p in winners_list]}")
        return winners_list

def create_coinflip_embed(session: CoinflipSession) -> discord.Embed:
    embed = discord.Embed(
        title="🎲 Multiplayer Coinflip Game",
        description=f"Bet per player: {session.bet}$ | Players: {len(session.players)}/{MAX_COINFLIP_PLAYERS}",
        color=discord.Color.gold()
    )
    if session.players:
        players_text = ""
        for p in session.players:
            players_text += f"{p['user'].display_name} – **{p['side'].title()}**\n"
        embed.add_field(name="Players", value=players_text, inline=False)
    embed.set_footer(text=f"Initiated by {session.initiator.display_name}")
    logging.debug("Created coinflip embed.")
    return embed

class CoinflipView(discord.ui.View):
    def __init__(self, session: CoinflipSession, economy_cog):
        super().__init__(timeout=120)
        self.session = session
        self.economy_cog = economy_cog

    @discord.ui.button(label="Join Heads", style=discord.ButtonStyle.primary)
    async def join_heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        econ = self.economy_cog
        current_balance = econ.get_balance(uid)
        if current_balance < self.session.bet:
            await interaction.response.send_message("🚫 Insufficient funds to join.", ephemeral=True)
            return
        econ.set_balance(uid, current_balance - self.session.bet)
        logging.debug(f"Deducted bet from {interaction.user.display_name}. New balance: {econ.get_balance(uid)}")
        if self.session.add_player(interaction.user, "heads"):
            embed = create_coinflip_embed(self.session)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ You have already joined or the game is full.", ephemeral=True)

    @discord.ui.button(label="Join Tails", style=discord.ButtonStyle.primary)
    async def join_tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        econ = self.economy_cog
        current_balance = econ.get_balance(uid)
        if current_balance < self.session.bet:
            await interaction.response.send_message("🚫 Insufficient funds to join.", ephemeral=True)
            return
        econ.set_balance(uid, current_balance - self.session.bet)
        logging.debug(f"Deducted bet from {interaction.user.display_name}. New balance: {econ.get_balance(uid)}")
        if self.session.add_player(interaction.user, "tails"):
            embed = create_coinflip_embed(self.session)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ You have already joined or the game is full.", ephemeral=True)

    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.success)
    async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.initiator.id:
            await interaction.response.send_message("🚫 Only the game initiator can start the game.", ephemeral=True)
            return

        if len(self.session.players) < 2:
            await interaction.response.send_message("🚫 At least two players must join.", ephemeral=True)
            return

        if not self.session.has_both_sides():
            for p in self.session.players:
                uid = str(p["user"].id)
                econ = self.economy_cog
                econ.set_balance(uid, econ.get_balance(uid) + self.session.bet)
            embed = discord.Embed(
                title="🔄 Game Canceled",
                description="All players chose the same side. Bets have been refunded.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            self.stop()
            return

        outcome = random.choice(["heads", "tails"])
        winners = self.session.winners(outcome)
        total_pot = self.session.total_pot()
        result_text = f"🪙 The coin landed **{outcome.title()}**!\n"
        if winners:
            share = total_pot // len(winners)
            result_text += "🎉 **Winners:**\n"
            for w in winners:
                result_text += f"• {w['user'].display_name} wins {share}$ and earns 20 xp.\n"
                uid = str(w["user"].id)
                econ = self.economy_cog
                econ.set_balance(uid, econ.get_balance(uid) + share)
            # XP update left to your leveling cog if applicable.
        else:
            result_text += "😢 No winners."
        embed = discord.Embed(title="🎲 Coinflip Result", description=result_text, color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

###########################################
# BLACKJACK SINGLE-PLAYER CLASSES
###########################################

def deal_card():
    cards = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
    card = random.choice(cards)
    logging.debug(f"Dealt card: {card}")
    return card

def calculate_hand(hand: list) -> int:
    total = sum(hand)
    aces = hand.count(11)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

class BlackjackSession:
    def __init__(self, player: discord.User, bet: int):
        self.player = player
        self.bet = bet
        self.player_hand = [deal_card(), deal_card()]
        self.dealer_hand = [deal_card(), deal_card()]
        self.message = None

    def player_total(self) -> int:
        total = calculate_hand(self.player_hand)
        logging.debug(f"Player total: {total}")
        return total

    def dealer_total(self) -> int:
        total = calculate_hand(self.dealer_hand)
        logging.debug(f"Dealer total: {total}")
        return total

    def is_player_bust(self) -> bool:
        return self.player_total() > 21

    def dealer_play(self):
        while self.dealer_total() < 17:
            self.dealer_hand.append(deal_card())

    def game_result(self) -> str:
        player_score = self.player_total()
        dealer_score = self.dealer_total()
        if player_score > 21:
            return "lose"
        if dealer_score > 21 or player_score > dealer_score:
            return "win"
        if player_score == dealer_score:
            return "tie"
        return "lose"

    def create_status_embed(self, reveal_dealer=False) -> discord.Embed:
        embed = discord.Embed(title="Blackjack", color=discord.Color.blue())
        embed.add_field(name="Your Hand", value=f"{self.player_hand} (Total: {self.player_total()})", inline=False)
        if reveal_dealer:
            embed.add_field(name="Dealer's Hand", value=f"{self.dealer_hand} (Total: {self.dealer_total()})", inline=False)
        else:
            embed.add_field(name="Dealer's Hand", value=f"[{self.dealer_hand[0]}, ?]", inline=False)
        embed.set_footer(text="Choose to Hit or Stand.")
        return embed

class BlackjackView(discord.ui.View):
    def __init__(self, session: BlackjackSession, economy_cog):
        super().__init__(timeout=120)
        self.session = session
        self.economy_cog = economy_cog

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.player.id:
            await interaction.response.send_message("🚫 It's not your game.", ephemeral=True)
            return
        self.session.player_hand.append(deal_card())
        if self.session.is_player_bust():
            embed = self.session.create_status_embed(reveal_dealer=True)
            embed.add_field(name="Result", value="💥 Bust! You lose.", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
        else:
            embed = self.session.create_status_embed(reveal_dealer=False)
            await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.success)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.player.id:
            await interaction.response.send_message("🚫 It's not your game.", ephemeral=True)
            return
        self.session.dealer_play()
        result = self.session.game_result()
        uid = str(self.session.player.id)
        econ = self.economy_cog
        if result == "win":
            payout = self.session.bet * 2
            outcome_text = f"🎉 You win {payout}$ and earn 20 xp!"
            econ.set_balance(uid, econ.get_balance(uid) + payout)
        elif result == "tie":
            payout = self.session.bet
            outcome_text = f"🤝 It's a tie! Your bet of {payout}$ is returned."
            econ.set_balance(uid, econ.get_balance(uid) + payout)
        else:
            outcome_text = f"😢 You lose your bet of {self.session.bet}$."
        embed = self.session.create_status_embed(reveal_dealer=True)
        embed.add_field(name="Result", value=outcome_text, inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

###########################################
# MINI GAMES COG: Integrates Coinflip & Blackjack
###########################################

class MiniGamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_economy(self):
        return self.bot.get_cog("EconomyCog")

    def normalize_choice(self, choice: str) -> str:
        c = choice.lower()
        if c in ("h", "heads"):
            return "heads"
        elif c in ("t", "tails"):
            return "tails"
        else:
            return None

    #########################
    # Coinflip Single-Player
    #########################
    @app_commands.command(name="coinflip_single", description="Play a single-player coinflip game.")
    @app_commands.describe(bet="Amount to bet", choice="Your choice: H, T, heads, or tails")
    async def coinflip_single(self, interaction: discord.Interaction, bet: int, choice: str):
        econ = self.get_economy()
        uid = str(interaction.user.id)
        if econ.get_balance(uid) < bet:
            embed = discord.Embed(
                title="Insufficient Funds",
                description="🚫 You don't have enough funds to place this bet!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return

        normalized = self.normalize_choice(choice)
        if not normalized:
            embed = discord.Embed(
                title="Invalid Choice",
                description="❓ Your choice must be H, T, heads, or tails.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            return

        new_balance = econ.get_balance(uid) - bet
        econ.set_balance(uid, new_balance)
        logging.debug(f"New balance for {interaction.user.display_name}: {econ.get_balance(uid)}")

        result = random.choice(["heads", "tails"])
        if result == normalized:
            payout = bet * 2
            econ.set_balance(uid, econ.get_balance(uid) + payout)
            embed = discord.Embed(
                title="🎉 Coinflip Victory!",
                description=f"🪙 The coin landed **{result.title()}**! You win {payout}$ and earn 20 xp.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="😢 Coinflip Loss",
                description=f"🪙 The coin landed **{result.title()}**. You lost {bet}$. Better luck next time!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)

    #########################
    # Coinflip Multiplayer
    #########################
    @app_commands.command(name="coinflip_multi", description="Play a multiplayer coinflip game!")
    @app_commands.describe(bet="Amount each player must bet", choice="Your choice: H, T, heads, or tails")
    async def coinflip_multi(self, interaction: discord.Interaction, bet: int, choice: str):
        econ = self.get_economy()
        uid = str(interaction.user.id)
        if econ.get_balance(uid) < bet:
            await interaction.response.send_message("🚫 Insufficient funds to start this game.", ephemeral=True)
            return

        normalized = self.normalize_choice(choice)
        if not normalized:
            embed = discord.Embed(
                title="Invalid Choice",
                description="❓ Your choice must be H, T, heads, or tails.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            return

        econ.set_balance(uid, econ.get_balance(uid) - bet)
        session = CoinflipSession(interaction.user, bet, normalized)
        embed = create_coinflip_embed(session)
        view = CoinflipView(session, econ)
        await interaction.response.send_message(embed=embed, view=view)

    #########################
    # Blackjack Single-Player
    #########################
    @app_commands.command(name="blackjack", description="Play a round of blackjack!")
    @app_commands.describe(bet="Amount to bet")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        econ = self.get_economy()
        uid = str(interaction.user.id)
        if econ.get_balance(uid) < bet:
            await interaction.response.send_message("🚫 Insufficient funds.", ephemeral=True)
            return

        econ.set_balance(uid, econ.get_balance(uid) - bet)
        session = BlackjackSession(interaction.user, bet)
        embed = session.create_status_embed(reveal_dealer=False)
        view = BlackjackView(session, econ)
        msg = await interaction.response.send_message(embed=embed, view=view)
        session.message = await msg.original_response()

async def setup(bot: commands.Bot):
    await bot.add_cog(MiniGamesCog(bot))
