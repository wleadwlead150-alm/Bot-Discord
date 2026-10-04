import discord
from discord import app_commands
import asyncio
import aiohttp
import time
import random
import json
import os
import sqlite3
import base64
from datetime import datetime

TOKEN_BOT = os.environ.get("DISCORD_BOT_TOKEN", "ضع_توكن_بوتك_هنا")

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
SAIF_ALERT_CHANNEL = "1545711547169513483"

CATEGORY_IDS = {
    "administrative": "1353444395575414844",
    "players": "1353444390387060736",
    "factions": "1353444400679747665"
}

def init_db():
    conn = sqlite3.connect('bot_users.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    token TEXT,
                    message TEXT,
                    speed REAL,
                    max_tickets INTEGER,
                    count INTEGER,
                    status TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

def get_user_data(user_id):
    conn = sqlite3.connect('bot_users.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT token, message, speed, max_tickets, count, status FROM user_settings WHERE user_id=?", (str(user_id),))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "token": base64.b64decode(row[0].encode()).decode() if row[0] else "",
            "message": row[1] or "أهلاً بك، معك الإدارة العليا. كيف يمكنني مساعدتك؟",
            "speed": row[2] if row[2] is not None else 0.5,
            "max_tickets": row[3] or 10,
            "count": row[4] or 0,
            "status": row[5] or "stopped",
            "logs": [],
            "active_tickets": set()
        }
    return {"token": "", "message": "أهلاً بك، معك الإدارة العليا. كيف يمكنني مساعدتك؟", "speed": 0.5, "max_tickets": 10, "count": 0, "status": "stopped", "logs": [], "active_tickets": set()}

def save_user_data(user_id, data):
    conn = sqlite3.connect('bot_users.db', check_same_thread=False)
    c = conn.cursor()
    enc_token = base64.b64encode(data["token"].encode()).decode() if data["token"] else ""
    c.execute('''INSERT OR REPLACE INTO user_settings (user_id, token, message, speed, max_tickets, count, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
              (str(user_id), enc_token, data["message"], data["speed"], data["max_tickets"], data["count"], data["status"]))
    conn.commit()
    conn.close()

active_sessions = {}

class MRClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Logged in as {self.user} (ID: {self.user.id})")

client = MRClient()

class TokenModal(discord.ui.Modal, title="🔒 إدخال توكن الحساب الأساسي"):
    token_input = discord.ui.TextInput(label="User Token", style=discord.TextStyle.paragraph, placeholder="الصق توكن حسابك هنا...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid not in active_sessions:
            active_sessions[uid] = get_user_data(uid)
        
        active_sessions[uid]["token"] = self.token_input.value.strip()
        save_user_data(uid, active_sessions[uid])
        await interaction.response.send_message("✅ تم حفظ التوكن بنجاح!", ephemeral=True)
        await update_main_panel(interaction)

class MessageModal(discord.ui.Modal, title="💬 تعديل رسالة استلام التكت"):
    msg_input = discord.ui.TextInput(label="نص الرد التلقائي", style=discord.TextStyle.paragraph, placeholder="اكتب الرسالة التي ستنزل في التكت...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid not in active_sessions:
            active_sessions[uid] = get_user_data(uid)
        
        active_sessions[uid]["message"] = self.msg_input.value.strip()
        save_user_data(uid, active_sessions[uid])
        await interaction.response.send_message("✅ تم تحديث رسالة الاستلام بنجاح!", ephemeral=True)
        await update_main_panel(interaction)

class SettingsModal(discord.ui.Modal, title="⚙️ إعدادات السرعة والحد الأقصى"):
    speed_input = discord.ui.TextInput(label="السرعة بالثواني (مثال: 0.5)", placeholder="0.5", required=True)
    max_input = discord.ui.TextInput(label="الحد الأقصى للتكتات", placeholder="10", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid not in active_sessions:
            active_sessions[uid] = get_user_data(uid)
        
        try:
            active_sessions[uid]["speed"] = float(self.speed_input.value)
            active_sessions[uid]["max_tickets"] = int(self.max_input.value)
            save_user_data(uid, active_sessions[uid])
            await interaction.response.send_message("✅ تم حفظ الإعدادات بنجاح!", ephemeral=True)
            await update_main_panel(interaction)
        except ValueError:
            await interaction.response.send_message("❌ خطأ: يجب إدخال أرقام صحيحة.", ephemeral=True)

class MRView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = str(user_id)

    @discord.ui.button(label="🔑 إدخال التوكن", style=discord.ButtonStyle.secondary, row=0)
    async def token_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TokenModal())

    @discord.ui.button(label="🚀 تشغيل / استئناف", style=discord.ButtonStyle.success, row=1)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = self.user_id
        if uid not in active_sessions:
            active_sessions[uid] = get_user_data(uid)
        
        d = active_sessions[uid]
        if not d["token"]:
            await interaction.response.send_message("⚠️ يجب إدخال التوكن أولاً!", ephemeral=True)
            return
        
        d["status"] = "running"
        if d["count"] >= d["max_tickets"]:
            d["count"] = 0
            
        save_user_data(uid, d)
        asyncio.create_task(run_gateway_sniper(self.user_id, interaction.client))
        await interaction.response.send_message("🚀 تم تفعيل محرك القنص بنجاح!", ephemeral=True)
        await update_main_panel(interaction)

    @discord.ui.button(label="🛑 إيقاف النظام", style=discord.ButtonStyle.danger, row=1)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = self.user_id
        if uid not in active_sessions:
            active_sessions[uid] = get_user_data(uid)
        
        active_sessions[uid]["status"] = "stopped"
        save_user_data(uid, active_sessions[uid])
        await interaction.response.send_message("🛑 تم إيقاف النظام.", ephemeral=True)
        await update_main_panel(interaction)

    @discord.ui.button(label="⚙️ تعديل السرعة والحد", style=discord.ButtonStyle.primary, row=2)
    async def settings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SettingsModal())

    @discord.ui.button(label="💬 تعديل رسالة الاستلام", style=discord.ButtonStyle.primary, row=2)
    async def msg_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MessageModal())

async def update_main_panel(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if uid not in active_sessions:
        active_sessions[uid] = get_user_data(uid)
    d = active_sessions[uid]

    status_text = "نشط 🚀" if d["status"] == "running" else "متوقف 🛑"
    status_color = discord.Color.green() if d["status"] == "running" else discord.Color.red()

    embed = discord.Embed(title="💎 M.R COMMAND CENTER (Discord Edition)", color=status_color)
    embed.add_field(name="🎯 الهدف المستلم", value=f"`{d['count']} / {d['max_tickets']}`", inline=True)
    embed.add_field(name="⚡ السرعة", value=f"`{d['speed']}s`", inline=True)
    embed.add_field(name="📌 الحالة", value=f"`{status_text}`", inline=False)
    embed.add_field(name="💬 رسالة الاستلام الحالية", value=f"```{d['message']}```", inline=False)
    
    logs_str = "\n".join(d["logs"][:5]) if d["logs"] else "• النظام جاهز..."
    embed.add_field(name="📜 سجل العمليات (LOGS)", value=f"```{logs_str}```", inline=False)

    try:
        await interaction.message.edit(embed=embed, view=MRView(uid))
    except:
        pass

@client.tree.command(name="mr", description="فتح لوحة التحكم الخاصة بقنص التذاكر")
async def mr_command(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if uid not in active_sessions:
        active_sessions[uid] = get_user_data(uid)
    d = active_sessions[uid]

    embed = discord.Embed(title="💎 M.R COMMAND CENTER (Discord Edition)", color=discord.Color.dark_embed())
    embed.add_field(name="🎯 الهدف المستلم", value=f"`{d['count']} / {d['max_tickets']}`", inline=True)
    embed.add_field(name="⚡ السرعة", value=f"`{d['speed']}s`", inline=True)
    embed.add_field(name="📌 الحالة", value="`متوقف 🛑`", inline=False)
    embed.add_field(name="💬 رسالة الاستلام الحالية", value=f"```{d['message']}```", inline=False)
    embed.add_field(name="📜 سجل العمليات (LOGS)", value="```• النظام جاهز...```", inline=False)

    await interaction.response.send_message(embed=embed, view=MRView(uid), ephemeral=True)

async def run_gateway_sniper(user_id, bot_client):
    uid = str(user_id)
    d = active_sessions[uid]
    token = d["token"]
    
    d["logs"].insert(0, "🚀 بدأ تشغيل الاتصال الذكي...")
    
    headers = {
        "Authorization": token.strip(),
        "Content-Type": "application/json",
        "User-Agent": "Discord-iOS/241.0 (iPhone13,4; iOS 17.5)"
    }

    gateway_url = "wss://gateway.discord.gg/?v=9&encoding=json"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(gateway_url) as ws:
                async for msg in ws:
                    if d["status"] == "stopped":
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        
                        if data.get("op") == 10:
                            payload = {
                                "op": 2,
                                "d": {
                                    "token": token,
                                    "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"},
                                    "intents": 1 | 512
                                }
                            }
                            await ws.send_json(payload)
                        
                        if data.get("t") == "CHANNEL_CREATE" and data.get("d", {}).get("guild_id") == SERVER_ID:
                            ch_data = data["d"]
                            ch_id = str(ch_data["id"])
                            name = ch_data.get("name", "غير-معروف")
                            parent_id = str(ch_data.get("parent_id", ""))
                            
                            if parent_id in list(CATEGORY_IDS.values()):
                                created_ts = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                                if time.time() - created_ts < 15:
                                    asyncio.create_task(execute_ticket_claim(uid, ch_id, name, headers, bot_client))
        except Exception as e:
            d["logs"].insert(0, f"❌ خطأ في الاتصال: {str(e)}")

async def execute_ticket_claim(uid, ch_id, name, headers, bot_client):
    d = active_sessions[uid]
    if d["status"] != "running": return
    if d["count"] >= d["max_tickets"]:
        d["status"] = "stopped"
        return
    if ch_id in d["active_tickets"]: return
    
    d["active_tickets"].add(ch_id)
    d["count"] += 1
    current_count = d["count"]
    max_lim = d["max_tickets"]

    if d["speed"] > 0:
        await asyncio.sleep(d["speed"])

    nonce = str(int(time.time() * 1000000)) + str(random.randint(10000, 99999))
    payload = {"content": d["message"], "nonce": nonce}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{API}/{ch_id}/messages", json=payload, headers=headers) as resp:
                if resp.status in [200, 201]:
                    t_time = datetime.now().strftime("%I:%M %p")
                    d["logs"].insert(0, f"✨ تم قنص تكت: **#{name}** ({current_count}/{max_lim})")
                    
                    try:
                        user_obj = await bot_client.fetch_user(int(uid))
                        ticket_link = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
                        await user_obj.send(f"💎 **تم استلام تذكرة بنجاح!**\n🎫 التكت: `#{name}`\n🔗 الرابط: {ticket_link}")
                    except Exception as e:
                        print(f"Could not DM user: {e}")

                    if uid == "Saif":
                        try:
                            await session.post(f"{API}/{SAIF_ALERT_CHANNEL}/messages", json={"content": f"💎 الإداري استلم تذكرة ✅\n🎫 `#{name}`\n🔗 https://discord.com/channels/{SERVER_ID}/{ch_id}", "nonce": nonce}, headers=headers)
                        except: pass

                    save_user_data(uid, d)
                    if current_count >= max_lim:
                        d["status"] = "stopped"
                        d["logs"].insert(0, "🛑 تم بلوغ الحد الأقصى.")
                else:
                    d["count"] -= 1
                    d["logs"].insert(0, f"❌ تعذر استلام #{name}")
        except:
            d["count"] -= 1
            d["logs"].insert(0, f"❌ خطأ اتصال أثناء القنص.")

        if ch_id in d["active_tickets"]:
            d["active_tickets"].remove(ch_id)

client.run(TOKEN_BOT)
