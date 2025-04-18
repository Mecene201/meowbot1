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

from db import get_db  # This function returns a sqlite3.Connection object
from upgrades import UPGRADES  # Contains upgrade data

# Import work logic from our separate module.
from worked import do_work, jobs as job_list

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# --- Constants ---
ITEMS = {
    'Fishing Rod': {'price': 500, 'emoji': '🎣', 'id': 1},
    'Pickaxe': {'price': 800, 'emoji': '⛏️', 'id': 2},
    'Rifle': {'price': 1200, 'emoji': '🔫', 'id': 3}
}

FISH_IDS = {'Goldfish': 101, 'Pufferfish': 102, 'Sturgeon': 103, 'Pupfish': 201}
ORE_IDS = {'Coal': 104, 'Iron': 105, 'Gold': 106, 'Rhodium': 202}
ANIMAL_IDS = {'Rabbit': 107, 'Deer': 108, 'Buffalo': 109, 'Griffin': 203}

STARTING_BALANCE = 500

XP_RANGES = {
    'common': (20, 50),
    'uncommon': (50, 70),
    'rare': (100, 150),
    'legendary': (500, 1000)
}

RARITY = {
    'common': {'emoji': '🟢', 'cash_range': (20, 50)},
    'uncommon': {'emoji': '🔵', 'cash_range': (100, 150)},
    'rare': {'emoji': '🟣', 'cash_range': (200, 250)},
    'legendary': {'emoji': '✨', 'cash_range': (1000, 1500)}
}

FISH_CATEGORIES = {
    'Goldfish': {'rarity': 'common', 'emoji': '🐟', 'chance': 60},
    'Pufferfish': {'rarity': 'uncommon', 'emoji': '🐡', 'chance': 30},
    'Sturgeon': {'rarity': 'rare', 'emoji': '🐠', 'chance': 10}
}

MINING_CATEGORIES = {
    'Coal': {'rarity': 'common', 'emoji': '🪨', 'chance': 60},
    'Iron': {'rarity': 'uncommon', 'emoji': '⛓️', 'chance': 30},
    'Gold': {'rarity': 'rare', 'emoji': '🪙', 'chance': 10}
}

HUNT_CATEGORIES = {
    'Rabbit': {'rarity': 'common', 'emoji': '🐇', 'chance': 60, 'cash_range': (25, 35)},
    'Deer': {'rarity': 'uncommon', 'emoji': '🦌', 'chance': 30, 'cash_range': (35, 45)},
    'Buffalo': {'rarity': 'rare', 'emoji': '🐃', 'chance': 10, 'cash_range': (45, 60)}
}

# --------------------------
# Shop Embed & Shop View
# --------------------------
class ShopView(View):
    def __init__(self, user_id, cog):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.cog = cog

    @discord.ui.button(label="Page 1: Tools", style=discord.ButtonStyle.primary)
    async def tools_page(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your shop!")
        embed = self.cog.create_shop_embed(self.user_id, page=1)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Page 2: Upgrades", style=discord.ButtonStyle.secondary)
    async def upgrades_page(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("This isn't your shop!")
        embed = self.cog.create_shop_embed(self.user_id, page=2)
        await interaction.response.edit_message(embed=embed, view=self)

# --------------------------
# Economy Cog
# --------------------------
class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Helper Method to Format Time ---
    def format_time(self, seconds: float) -> str:
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return " ".join(parts) if parts else f"{hours} hour{'s' if hours != 1 else ''}"

    # --- Database Helper Methods ---
    def init_user(self, user_id: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, STARTING_BALANCE))
            conn.commit()
        conn.close()

    def get_balance(self, user_id: str) -> int:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else STARTING_BALANCE

    def set_balance(self, user_id: str, new_balance: int):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (user_id, balance) VALUES (?, ?)", (user_id, new_balance))
        conn.commit()
        conn.close()

    def add_to_inventory(self, user_id: str, item_name: str, item_id: int, emoji: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT amount FROM inventory WHERE user_id = ? AND item = ? AND item_id = ?",
            (user_id, item_name, item_id)
        )
        row = cursor.fetchone()
        if row:
            new_amount = row[0] + 1
            cursor.execute(
                "UPDATE inventory SET amount = ? WHERE user_id = ? AND item = ? AND item_id = ?",
                (new_amount, user_id, item_name, item_id)
            )
        else:
            cursor.execute(
                "INSERT INTO inventory (user_id, item, item_id, emoji, amount) VALUES (?, ?, ?, ?, ?)",
                (user_id, item_name, item_id, emoji, 1)
            )
        conn.commit()
        conn.close()

    def get_inventory(self, user_id: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT item, emoji, item_id, amount FROM inventory WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"item": r[0], "emoji": r[1], "id": r[2], "amount": r[3]} for r in rows]

    def has_tool(self, user_id: str, tool_name: str) -> bool:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM inventory WHERE user_id = ? AND item = ? AND amount = 1",
            (user_id, tool_name)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_upgrade_level(self, user_id: str, key: str) -> int:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT level FROM upgrades WHERE user_id = ? AND upgrade_key = ?", (user_id, key))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

    def has_upgrade(self, user_id: str, key: str) -> bool:
        return self.get_upgrade_level(user_id, key) > 0

    def set_upgrade(self, user_id: str, key: str):
        conn = get_db()
        cursor = conn.cursor()
        if self.get_upgrade_level(user_id, key) == 0:
            cursor.execute("INSERT INTO upgrades (user_id, upgrade_key, level) VALUES (?, ?, ?)", (user_id, key, 1))
        conn.commit()
        conn.close()

    def get_cooldown(self, user_id: str, cd_type: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp FROM cooldowns WHERE user_id = ? AND type = ?", (user_id, cd_type))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

    def set_cooldown(self, user_id: str, cd_type: str, timestamp: float):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO cooldowns (user_id, type, timestamp) VALUES (?, ?, ?)",
                       (user_id, cd_type, timestamp))
        conn.commit()
        conn.close()

    # Helper to get owned upgrades so they can be displayed in inventory.
    def get_user_upgrades(self, user_id: str):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT upgrade_key, level FROM upgrades WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"upgrade_key": r[0], "level": r[1]} for r in rows]

    # Updated: Inventory Space Now Counts Upgrades.
    def inventory_is_full(self, user_id: str) -> bool:
        inventory = self.get_inventory(user_id)
        # Tools (items in ITEMS) do not count
        item_space_used = sum(item['amount'] for item in inventory if item['item'] not in ITEMS)
        # Each owned upgrade takes 1 slot
        upgrades = self.get_user_upgrades(user_id)
        upgrades_space_used = len(upgrades)
        total_space_used = item_space_used + upgrades_space_used

        backpack_1 = self.get_upgrade_level(user_id, "backpack_1")
        backpack_2 = self.get_upgrade_level(user_id, "backpack_2")
        inventory_limit = 10 + 5 * backpack_1 + 5 * backpack_2
        return total_space_used >= inventory_limit

    def upgrade_on_cooldown(self, user_id: str, upgrade_key: str):
        last_used = self.get_cooldown(user_id, upgrade_key)
        upgrade = next((u for u in UPGRADES.values() if u['key'] == upgrade_key), None)
        if not upgrade or 'cooldown' not in upgrade:
            return False, 0
        now = time.time()
        remaining = int(upgrade["cooldown"] - (now - last_used))
        return remaining > 0, max(0, remaining)

    def is_upgrade_active(self, user_id: str, upgrade_key: str) -> bool:
        active_start = self.get_cooldown(user_id, f"{upgrade_key}_active")
        if active_start:
            upgrade = next((u for u in UPGRADES.values() if u["key"] == upgrade_key), None)
            if upgrade and (time.time() - active_start) < upgrade.get("active_duration", 0):
                return True
        return False

    def can_activate_upgrade(self, user_id: str, upgrade_key: str) -> tuple[bool, int]:
        last_activation = self.get_cooldown(user_id, f"{upgrade_key}_last")
        upgrade = next((u for u in UPGRADES.values() if u["key"] == upgrade_key), None)
        if upgrade is None:
            return (False, 0)
        cycle_cooldown = upgrade.get("cycle_cooldown", 0)
        now = time.time()
        if last_activation and (now - last_activation) < cycle_cooldown:
            remaining = int(cycle_cooldown - (now - last_activation))
            return (False, remaining)
        return (True, 0)

    def activate_upgrade_effect(self, user_id: str, upgrade_key: str):
        now = time.time()
        self.set_cooldown(user_id, f"{upgrade_key}_active", now)
        self.set_cooldown(user_id, f"{upgrade_key}_last", now)

    def select_fish(self):
        x = random.random()
        if x < 0.01:
            return "Pupfish", {"rarity": "legendary", "emoji": "🐶🐟", "chance": 1, "cash_range": (1000, 1500)}
        else:
            y = random.uniform(0, 100)
            if y <= 60:
                return "Goldfish", FISH_CATEGORIES["Goldfish"]
            elif y <= 90:
                return "Pufferfish", FISH_CATEGORIES["Pufferfish"]
            else:
                return "Sturgeon", FISH_CATEGORIES["Sturgeon"]

    def select_mine(self):
        x = random.random()
        if x < 0.01:
            return "Rhodium", {"rarity": "legendary", "emoji": "⚙️", "chance": 1, "cash_range": (1000, 1500)}
        else:
            y = random.uniform(0, 100)
            if y <= 60:
                return "Coal", MINING_CATEGORIES["Coal"]
            elif y <= 90:
                return "Iron", MINING_CATEGORIES["Iron"]
            else:
                return "Gold", MINING_CATEGORIES["Gold"]

    def select_hunt(self):
        x = random.random()
        if x < 0.01:
            return "Griffin", {"rarity": "legendary", "emoji": "🦅", "chance": 1, "cash_range": (1000, 1500)}
        else:
            y = random.uniform(0, 100)
            if y <= 60:
                return "Rabbit", HUNT_CATEGORIES["Rabbit"]
            elif y <= 90:
                return "Deer", HUNT_CATEGORIES["Deer"]
            else:
                return "Buffalo", HUNT_CATEGORIES["Buffalo"]

    def create_shop_embed(self, user_id: str, page=1):
        embed = discord.Embed(title="🛒 Shop", color=discord.Color.gold())
        # Page 1: Tools
        if page == 1:
            embed.description = "Tool Items:"
            for item, details in ITEMS.items():
                price = details['price']
                if self.has_upgrade(user_id, 'tax_evasion') and self.is_upgrade_active(user_id, "tax_evasion"):
                    price = int(price * 0.9)
                embed.add_field(
                    name=f"{details['emoji']} {item}",
                    value=f"💰 ${price}\nID: `{details['id']}`",
                    inline=False
                )
        # Page 2: Upgrades
        elif page == 2:
            embed.description = "Upgrades:"
            for upgrade_id, upgrade in UPGRADES.items():
                level = self.get_upgrade_level(user_id, upgrade["key"])
                price = upgrade['price']
                if self.has_upgrade(user_id, 'tax_evasion') and self.is_upgrade_active(user_id, "tax_evasion"):
                    price = int(price * 0.9)
                embed.add_field(
                    name=f"{upgrade['emoji']} {upgrade['name']} (ID: {upgrade_id})",
                    value=f"{upgrade['description']}\n💰 ${price}\nOwned: {level}",
                    inline=False
                )
        embed.set_footer(text="Use /buy [ID] to purchase.")
        return embed

    # --------------------------
    # Slash Commands
    # --------------------------
    @app_commands.command(name="activity", description="Fish, mine or hunt to earn XP")
    @app_commands.choices(activity=[
        app_commands.Choice(name="Fish", value="fish"),
        app_commands.Choice(name="Mine", value="mine"),
        app_commands.Choice(name="Hunt", value="hunt")
    ])
    async def activity(self, interaction: discord.Interaction, activity: app_commands.Choice[str]):
        activity = activity.value
        user_id = str(interaction.user.id)
        self.init_user(user_id)
        if self.inventory_is_full(user_id):
            await interaction.response.send_message("🧳 Your inventory is full! Buy a 🎒 Backpack Expansion to store more.")
            return
        required_tool = {"fish": "Fishing Rod", "mine": "Pickaxe", "hunt": "Rifle"}[activity]
        if not self.has_tool(user_id, required_tool):
            emoji = ITEMS[required_tool]['emoji']
            await interaction.response.send_message(f"{emoji} You need a {required_tool} to {activity}.")
            return
        if not await self.check_and_set_cooldown(user_id, activity, interaction):
            return
        if activity == "fish":
            item, data = self.select_fish()
            xp_range = XP_RANGES.get(data['rarity'], (75, 75))
            base_xp = random.randint(*xp_range)
            item_id = FISH_IDS.get(item, 999)
            self.add_to_inventory(user_id, item, item_id, data['emoji'])
        elif activity == "mine":
            item, data = self.select_mine()
            xp_range = XP_RANGES.get(data['rarity'], (75, 75))
            base_xp = random.randint(*xp_range)
            item_id = ORE_IDS.get(item, 999)
            self.add_to_inventory(user_id, item, item_id, data['emoji'])
        elif activity == "hunt":
            item, data = self.select_hunt()
            xp_range = XP_RANGES.get(data['rarity'], (75, 75))
            base_xp = random.randint(*xp_range)
            item_id = ANIMAL_IDS.get(item, 999)
            self.add_to_inventory(user_id, item, item_id, data['emoji'])
        bonus_xp = 0
        if self.has_upgrade(user_id, "xp_boost") and self.is_upgrade_active(user_id, "xp_boost"):
            bonus_xp = int(base_xp * 0.05)
        total_xp = base_xp + bonus_xp
        level = "?"
        leveling_cog = self.bot.get_cog("LevelingCog")
        try:
            if leveling_cog:
                await leveling_cog.add_xp(user_id, total_xp)
                level = leveling_cog.get_user_level_info(user_id)['level']
        except Exception:
            await interaction.response.send_message("There was an issue updating your level.")
            return
        embed = discord.Embed(
            title=f"You did {activity.title()}!",
            description=(f"You got a {data['emoji']} **{item}**!\n"
                         f"Rarity: {RARITY.get(data['rarity'], {}).get('emoji', '✨')} {data['rarity'].title()}\n"
                         f"Base XP: {base_xp}\n"
                         f"Bonus XP: {bonus_xp}\n"
                         f"Total XP: {total_xp}"),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    async def check_and_set_cooldown(self, user_id: str, activity: str, interaction: discord.Interaction):
        cooldown_times = {'fish': 10, 'mine': 15, 'hunt': 15}
        last_used = self.get_cooldown(user_id, activity)
        now = time.time()
        if last_used and (now - last_used) < cooldown_times[activity]:
            remaining = cooldown_times[activity] - (now - last_used)
            await interaction.response.send_message(f"❌ This activity is on cooldown. Try again in {self.format_time(remaining)}.")
            return False
        self.set_cooldown(user_id, activity, now)
        return True

    @app_commands.command(name="buy", description="Buy an item or upgrade from the shop")
    @app_commands.describe(item_id="The ID of the item or upgrade to buy")
    async def buy(self, interaction: discord.Interaction, item_id: int):
        user_id = str(interaction.user.id)
        self.init_user(user_id)
        selected_item = None
        for name, details in ITEMS.items():
            if details['id'] == item_id:
                selected_item = {
                    'type': 'tool',
                    'name': name,
                    'emoji': details['emoji'],
                    'price': details['price'],
                    'id': item_id
                }
                break
        if not selected_item and item_id in UPGRADES:
            upgrade = UPGRADES[item_id]
            selected_item = {
                'type': 'upgrade',
                'name': upgrade['name'],
                'emoji': upgrade['emoji'],
                'price': upgrade['price'],
                'id': item_id,
                'key': upgrade['key']
            }
        if not selected_item:
            await interaction.response.send_message("❌ Invalid item ID.")
            return
        price = selected_item['price']
        if selected_item['type'] == 'tool' and self.has_upgrade(user_id, 'tax_evasion') and self.is_upgrade_active(user_id, "tax_evasion"):
            price = int(price * 0.9)
        if selected_item['type'] == 'upgrade' and self.has_upgrade(user_id, 'tax_evasion') and self.is_upgrade_active(user_id, "tax_evasion"):
            price = int(price * 0.9)
        current_balance = self.get_balance(user_id)
        if current_balance < price:
            await interaction.response.send_message("❌ You don’t have enough money.")
            return
        if selected_item['type'] == 'tool':
            if self.has_tool(user_id, selected_item['name']):
                await interaction.response.send_message(f"❌ You already own {selected_item['emoji']} {selected_item['name']}.")
                return
            self.add_to_inventory(user_id, selected_item['name'], selected_item['id'], selected_item['emoji'])
        elif selected_item['type'] == 'upgrade':
            upgrade_key = selected_item['key']
            if self.inventory_is_full(user_id):
                await interaction.response.send_message("❌ Your inventory is full. You cannot buy more upgrades.")
                return
            if upgrade_key == "backpack_2" and self.get_upgrade_level(user_id, "backpack_1") == 0:
                await interaction.response.send_message("🎒 You must buy Backpack Expansion I before Expansion II.")
                return
            if self.has_upgrade(user_id, upgrade_key):
                await interaction.response.send_message("❌ You already own this upgrade.")
                return
            self.set_upgrade(user_id, upgrade_key)
            if upgrade_key == "tax_evasion":
                self.set_cooldown(user_id, "tax_evasion", time.time())
        self.set_balance(user_id, current_balance - price)
        await interaction.response.send_message(
            f"✅ You bought {selected_item['emoji']} **{selected_item['name']}** for 💰${price}!\nNew Balance: 💰${self.get_balance(user_id)}"
        )

    # Updated inventory command:
    # Filters out active temporary upgrades (like tax evasion and xp boost) so they no longer show as owned once activated.
    @app_commands.command(name="inventory", description="Check your inventory")
    async def inventory(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        self.init_user(user_id)
        inventory = self.get_inventory(user_id)
        def get_upgrade_detail(upgrade_key):
            for upgrade_id, upgrade in UPGRADES.items():
                if upgrade["key"] == upgrade_key:
                    return upgrade_id, upgrade
            return None, None

        # Define which upgrades are consumable temporary upgrades.
        consumable_upgrades = {"tax_evasion", "xp_boost"}
        all_upgrades = self.get_user_upgrades(user_id)
        filtered_upgrades = []
        for up in all_upgrades:
            if up["upgrade_key"] in consumable_upgrades and self.is_upgrade_active(user_id, up["upgrade_key"]):
                continue
            filtered_upgrades.append(up)

        upgrade_items = []
        for up in filtered_upgrades:
            upgrade_id, detail = get_upgrade_detail(up["upgrade_key"])
            if detail:
                upgrade_items.append({
                    "item": detail["name"],
                    "emoji": detail["emoji"],
                    "id": upgrade_id,
                    "amount": 1
                })

        item_space_used = sum(item['amount'] for item in inventory if item['item'] not in ITEMS)
        upgrades_space_used = len(upgrade_items)
        total_space_used = item_space_used + upgrades_space_used

        backpack_1 = self.get_upgrade_level(user_id, "backpack_1")
        backpack_2 = self.get_upgrade_level(user_id, "backpack_2")
        inventory_limit = 10 + 5 * backpack_1 + 5 * backpack_2

        tools = [i for i in inventory if i['item'] in ITEMS]
        items = [i for i in inventory if i['item'] not in ITEMS]

        description = f"🎒 Inventory Space: {total_space_used} / {inventory_limit}\n\n"
        if tools:
            description += "**Tools (do not consume space):**\n" + "\n".join(f"{i['emoji']} {i['item']} (ID: {i['id']})" for i in tools) + "\n\n"
        if items:
            description += "**Items:**\n" + "\n".join(f"{i['emoji']} {i['item']} (ID: {i['id']}) x{i['amount']}" for i in items) + "\n\n"
        if upgrade_items:
            description += "**Upgrades:**\n" + "\n".join(f"{u['emoji']} {u['item']} (ID: {u['id']})" for u in upgrade_items)
        if not tools and not items and not upgrade_items:
            description += "You don't have any items yet."
        embed = discord.Embed(
            title=f"{interaction.user.name}'s Inventory",
            description=description,
            color=discord.Color.blue()
        )
        await interaction.response.defer()
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="balance", description="View your current cash or another user's balance")
    @app_commands.describe(member="The member whose balance you want to view (optional)")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member if member is not None else interaction.user
        user_id = str(target.id)
        self.init_user(user_id)
        balance = self.get_balance(user_id)
        embed = discord.Embed(
            title=f"{target.name}'s Balance",
            description=f"💰 ${balance}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sell", description="Sell your fish, ores, or animals by ID and amount")
    @app_commands.describe(item_id="The ID of the item you want to sell", amount="How many you want to sell")
    async def sell(self, interaction: discord.Interaction, item_id: int, amount: int):
        user_id = str(interaction.user.id)
        self.init_user(user_id)
        if amount <= 0:
            await interaction.response.send_message("Amount must be at least 1.")
            return
        await interaction.response.defer()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT amount, emoji, item FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            await interaction.followup.send("This item can't be sold or is not in your inventory.")
            return
        current_amount, emoji, item_name = row
        if item_name in ITEMS:
            conn.close()
            await interaction.followup.send("❌ Tools cannot be sold.")
            return
        if amount > current_amount:
            conn.close()
            await interaction.followup.send(f"You only have {current_amount} of that item.")
            return
        rarity = (FISH_CATEGORIES.get(item_name, {}).get('rarity') or
                  MINING_CATEGORIES.get(item_name, {}).get('rarity') or
                  HUNT_CATEGORIES.get(item_name, {}).get('rarity'))
        if item_name in HUNT_CATEGORIES:
            min_price, max_price = HUNT_CATEGORIES[item_name]['cash_range']
        elif rarity:
            min_price, max_price = RARITY[rarity]['cash_range']
        else:
            conn.close()
            await interaction.followup.send("This item cannot be sold.")
            return
        total_earned = sum(random.randint(min_price, max_price) for _ in range(amount))
        new_amount = current_amount - amount
        if new_amount == 0:
            cursor.execute("DELETE FROM inventory WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        else:
            cursor.execute("UPDATE inventory SET amount = ? WHERE user_id = ? AND item_id = ?", (new_amount, user_id, item_id))
        conn.commit()
        conn.close()
        current_balance = self.get_balance(user_id)
        self.set_balance(user_id, current_balance + total_earned)
        await interaction.followup.send(f"💰 {interaction.user.name} sold {amount}x {emoji} {item_name} for ${total_earned}!")

    @app_commands.command(name="shop", description="Browse the shop for tools and upgrades")
    async def shop(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        self.init_user(user_id)
        embed = self.create_shop_embed(user_id, page=1)
        view = ShopView(user_id, self)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="activate", description="Activate a temporary upgrade effect using its ID.")
    @app_commands.describe(upgrade_id="The numeric ID of the upgrade to activate (e.g., 403 for XP Booster, 404 for Tax Evasion)")
    async def activate(self, interaction: discord.Interaction, upgrade_id: int):
        user_id = str(interaction.user.id)
        upgrade = UPGRADES.get(upgrade_id)
        if not upgrade:
            await interaction.response.send_message("❌ Invalid upgrade ID.")
            return

        upgrade_key = upgrade.get("key")
        if not self.has_upgrade(user_id, upgrade_key):
            await interaction.response.send_message("❌ You don't own this upgrade.")
            return

        can_activate, remaining = self.can_activate_upgrade(user_id, upgrade_key)
        if not can_activate:
            await interaction.response.send_message(f"❌ This upgrade is still in cooldown. Try again in {self.format_time(remaining)}.")
            return

        self.activate_upgrade_effect(user_id, upgrade_key)

        # Define which upgrades are consumable:
        CONSUMABLE_UPGRADES = {"tax_evasion", "xp_boost"}
        if upgrade_key in CONSUMABLE_UPGRADES:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM upgrades WHERE user_id = ? AND upgrade_key = ?", (user_id, upgrade_key))
            conn.commit()
            conn.close()

        duration = upgrade.get("active_duration", 0)
        await interaction.response.send_message(
            f"✅ {upgrade.get('emoji', '')} {upgrade.get('name', upgrade_key)} activated and consumed! It will last for {self.format_time(duration)}."
        )

    @app_commands.command(name="work", description="Choose a job to work and earn coins and XP!")
    @app_commands.describe(job="Enter a job abbreviation or name (e.g., ffw, bar, fw, dev, bo)")
    async def work(self, interaction: discord.Interaction, job: str):
        user_id = str(interaction.user.id)
        self.init_user(user_id)
        
        aliases = {
            "ffw": "fast_food_worker",
            "fastfood": "fast_food_worker",
            "fast_food_worker": "fast_food_worker",
            "bar": "barista",
            "barista": "barista",
            "fw": "freelance_writer",
            "writer": "freelance_writer",
            "freelance": "freelance_writer",
            "freelance_writer": "freelance_writer",
            "dev": "software_developer",
            "software": "software_developer",
            "software_developer": "software_developer",
            "bo": "business_owner",
            "owner": "business_owner",
            "business": "business_owner",
            "business_owner": "business_owner"
        }
        job_abbrevs = {
            "fast_food_worker": "FFW",
            "barista": "Bar",
            "freelance_writer": "FW",
            "software_developer": "Dev",
            "business_owner": "BO"
        }
        job_cooldowns = {
            "fast_food_worker": 30,
            "barista": 60,
            "freelance_writer": 120,
            "software_developer": 120,
            "business_owner": 150
        }
        job_emojis = {
            "fast_food_worker": "🍔",
            "barista": "☕",
            "freelance_writer": "📝",
            "software_developer": "💻",
            "business_owner": "📈"
        }
        work_descriptions = {
            "fast_food_worker": "you flipped a burger and served up smiles!",
            "barista": "you brewed the perfect cup of joe and warmed hearts!",
            "freelance_writer": "your words captivated readers and sparked imaginations!",
            "software_developer": "you squashed bugs and built a flawless app!",
            "business_owner": "you closed a deal and expanded your empire!"
        }
        
        job_input = job.lower().replace(" ", "")
        if job_input not in aliases:
            embed = discord.Embed(
                title="Available Jobs",
                description=(
                    "**Please choose one of the following jobs using their abbreviation:**\n"
                    f"**{job_abbrevs['fast_food_worker']}** - Fast Food Worker (Unlocks at Level 1, Cooldown: 30s) {job_emojis['fast_food_worker']}\n"
                    f"**{job_abbrevs['barista']}** - Barista (Unlocks at Level 5, Cooldown: 1m) {job_emojis['barista']}\n"
                    f"**{job_abbrevs['freelance_writer']}** - Freelance Writer (Unlocks at Level 10, Cooldown: 2m) {job_emojis['freelance_writer']}\n"
                    f"**{job_abbrevs['software_developer']}** - Software Developer (Unlocks at Level 15, Cooldown: 2m) {job_emojis['software_developer']}\n"
                    f"**{job_abbrevs['business_owner']}** - Business Owner (Unlocks at Level 20, Cooldown: 2m 30s) {job_emojis['business_owner']}\n\n"
                    "To work, use the command: `/work <job>`\nFor example: `/work ffw`"
                ),
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        job_key = aliases[job_input]
        
        leveling_cog = self.bot.get_cog("LevelingCog")
        user_level = 1
        if leveling_cog:
            level_info = leveling_cog.get_user_level_info(user_id)
            user_level = level_info.get("level", 1)
        
        if job_key not in job_list:
            await interaction.response.send_message("This job is not available.")
            return
        
        required_level = job_list[job_key]["level_requirement"]
        if user_level < required_level:
            embed = discord.Embed(
                title=f"{job_key.replace('_',' ').title()} Locked 🔒",
                description=(
                    f"**You need to be at least level {required_level} to work as a {job_key.replace('_',' ').title()}!**\n"
                    f"Your current level: {user_level}"
                ),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        cooldown_key = f"work_{job_key}"
        last_used = self.get_cooldown(user_id, cooldown_key)
        now = time.time()
        job_cooldown = job_cooldowns.get(job_key, 30)
        if last_used and (now - last_used) < job_cooldowns[job_key]:
            remaining = job_cooldowns[job_key] - (now - last_used)
            await interaction.response.send_message(f"❌ {job_key.replace('_', ' ').title()} work is on cooldown. Try again in {self.format_time(remaining)}.")
            return
        
        self.set_cooldown(user_id, cooldown_key, now)
        
        result, error = do_work(job_key, user_level)
        if error:
            await interaction.response.send_message(error)
            return
        coins_earned, xp_gained = result
        
        bonus_xp = 0
        if self.has_upgrade(user_id, "xp_boost") and self.is_upgrade_active(user_id, "xp_boost"):
            bonus_xp = int(xp_gained * 0.05)
        total_xp = xp_gained + bonus_xp
        
        current_balance = self.get_balance(user_id)
        self.set_balance(user_id, current_balance + coins_earned)
        
        if leveling_cog:
            try:
                await leveling_cog.add_xp(user_id, total_xp)
            except Exception as e:
                await interaction.response.send_message(f"Error updating XP: {e}")
                return
            level_info = leveling_cog.get_user_level_info(user_id)
            new_level = level_info.get("level", user_level)
        else:
            new_level = user_level
        
        embed = discord.Embed(
            title=f"{job_emojis.get(job_key, '')} {job_key.replace('_',' ').title()}",
            description=(
                f"{work_descriptions.get(job_key, 'You worked hard!')}\n\n"
                f"💰 You earned **${coins_earned}**\n"
                f"📈 You gained **{total_xp}** XP"
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    # New command to show active temporary upgrades with remaining durations.
    @app_commands.command(name="active_upgrades", description="Show your active temporary upgrades and their remaining durations.")
    async def active_upgrades(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        self.init_user(user_id)
        now = time.time()
        active_list = []
        # Loop through upgrades with an active_duration; exclude non-temporary upgrades (like backpacks)
        for upgrade_id, upgrade in UPGRADES.items():
            if upgrade["key"] in ["backpack_1", "backpack_2"]:
                continue
            duration = upgrade.get("active_duration", 0)
            if duration > 0:
                active_start = self.get_cooldown(user_id, f"{upgrade['key']}_active")
                if active_start and (now - active_start) < duration:
                    remaining = duration - (now - active_start)
                    active_list.append(f"{upgrade['emoji']} **{upgrade['name']}**: {self.format_time(remaining)} remaining")
        if active_list:
            description = "\n".join(active_list)
        else:
            description = "You have no active temporary upgrades at the moment."
        embed = discord.Embed(
            title="Active Temporary Upgrades",
            description=description,
            color=discord.Color.purple()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
    await bot.tree.sync()


