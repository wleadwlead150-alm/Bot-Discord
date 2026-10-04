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
import http.server
import socketserver
import threading

PORT = int(os.environ.get("PORT", 10000))

class DummyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("M.R Sniper Bot is Alive and Running".encode('utf-8'))

def run_web_server():
    handler = DummyHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        httpd.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

TOKEN_BOT = os.environ.get("DISCORD_BOT_TOKEN", "ضع_توكن_بوتك_هنا")

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
SAIF_ALERT_CHANNEL = "1545711547169513483"

CATEGORY_IDS = {
    "administrative": "1353444395575414844",
    "players": "1353444390387060736",
    "factions": "1353444400679747665"
}

INITIAL_USERS = {
    "Saif": "12345678", "Marshall": "oopp0099", "Youssef": "oopp009987",
    "Kara": "oopp00998", "isso": "12345678", "Azmy": "12345678", "Dark": "123456789"
}

def init_db():
    conn = sqlite3.connect('bot_users.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    token TEXT,
                    message TEXT,
                    speed REAL,
                    max_tickets INTEGER,
                    count INTEGER,
                    status TEXT
                )''')
    for uname, pwd in INITIAL_USERS.items():
        c.execute("SELECT username FROM user_settings WHERE username=?", (uname,))
        if not c.fetchone():
            c.execute('''INSERT INTO user_settings (username, password, token, message, speed, max_tickets, count, status) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (uname, pwd, "", "أهلاً بك، معك الإدارة العليا. كيف يمكنني مساعدتك؟", 0.5, 10, 0, "stopped"))
    conn.commit()
    conn.close()

init_db()

def get_user_data(username):
    conn = sqlite3.connect('bot_users.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT password, token, message, speed, max_tickets, count, status FROM user_settings WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "password": row[0],
            "token": base64.b64decode(row[1].encode()).decode() if row[1] else "",
            "message": row[2] or "أهلاً بك، معك الإدارة العليا. كيف يمكنني مساعدتك؟",
            "speed": row[3] if row[3] is not None else 0.5,
            "max_tickets": row[4] or 10,
            "count": row[5] or 0,
            "status": row[6] or "stopped",
            "logs": [],
            "active_tickets": set()
        }
    return None

def save_user_data(username, data):
    conn = sqlite3.connect('bot_users.db', check_same_thread=False)
    c = conn.cursor()
    enc_token = base64.b64encode(data["token"].encode()).decode() if data["token"] else ""
    c.execute('''UPDATE user_settings SET token=?, message=?, speed=?, max_tickets=?, count=?, status=? WHERE username=?''', 
              (enc_token, data["message"], data["speed"], data["max_tickets"], data["count"], data["status"], username))
    conn.commit()
    conn.close()

active_sessions = {}
logged_in_users = {}

class MRClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = MRClient()

class RestrictedLoginModal(discord.ui.Modal, title="🔐 تسجيل دخول القدماء الحصري"):
    username_input = discord.ui.TextInput(label="اسم المستخدم", placeholder="اكتب اسمك المعتمد...", required=True)
    password_input = discord.ui.TextInput(label="كلمة المرور", style=discord.TextStyle.short, placeholder="رمز المرور...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        uname = self.username_input.value.strip()
        pwd = self.password_input.value.strip()
        
        if uname in INITIAL_USERS and INITIAL_USERS[uname] == pwd:
            data = get_user_data(uname)
            discord_uid = str(interaction.user.id)
            logged_in_users[discord_uid] = uname
            if uname not in active_sessions:
                active_sessions[uname] = data
            
            await interaction.response.send_message(f"✅ تم التحقق وتسجيل الدخول بنجاح كـ **{uname}**!", ephemeral=True)
            await show_main_panel(interaction, uname)
        else:
            await interaction.response.send_message("❌ عذراً، اسم المستخدم غير مسموح به أو كلمة المرور غير صحيحة!", ephemeral=True)

class LoginView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تسجيل الدخول الحصري 🔑", style=discord.ButtonStyle.primary)
    async def login_button_cb(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RestrictedLoginModal())

class TokenModal(discord.ui.Modal, title="🔒 إدخال توكن الحساب الأساسي"):
    token_input = discord.ui.TextInput(label="User Token", style=discord.TextStyle.paragraph, placeholder="الصق توكن حسابك هنا...", required=True)

    def __init__(self, username):
        super().__init__()
        self.username = username

    async def on_submit(self, interaction: discord.Interaction):
        active_sessions[self.username]["token"] = self.token_input.value.strip()
        save_user_data(self.username, active_sessions[self.username])
        await interaction.response.send_message("✅ تم حفظ التوكن بنجاح!", ephemeral=True)
        await show_main_panel(interaction, self.username, edit=True)

class MessageModal(discord.ui.Modal, title="💬 تعديل رسالة استلام التكت"):
    msg_input = discord.ui.TextInput(label="نص الرد التلقائي", style=discord.TextStyle.paragraph, placeholder="اكتب الرسالة...", required=True)

    def __init__(self, username):
        super().__init__()
        self.username = username

    async def on_submit(self, interaction: discord.Interaction):
        active_sessions[self.username]["message"] = self.msg_input.value.strip()
        save_user_data(self.username, active_sessions[self.username])
        await interaction.response.send_message("✅ تم تحديث رسالة الاستلام!", ephemeral=True)
        await show_main_panel(interaction, self.username, edit=True)

class SettingsModal(discord.ui.Modal, title="⚙️ إعدادات السرعة والهدف"):
    speed_input = discord.ui.TextInput(label="السرعة بالثواني", placeholder="0.5", required=True)
    max_input = discord.ui.TextInput(label="الهدف (الحد الأقصى)", placeholder="10", required=True)

    def __init__(self, username):
        super().__init__()
        self.username = username

    async def on_submit(self, interaction: discord.Interaction):
        try:
            active_sessions[self.username]["speed"] = float(self.speed_input.value)
            active_sessions[self.username]["max_tickets"] = int(self.max_input.value)
            save_user_data(self.username, active_sessions[self.username])
            await interaction.response.send_message("✅ تم تحديث الهدف والسرعة بنجاح!", ephemeral=True)
            await show_main_panel(interaction, self.username, edit=True)
        except ValueError:
            await interaction.response.send_message("❌ خطأ في القيم المدخلة.", ephemeral=True)

class MRView(discord.ui.View):
    def __init__(self, username):
        super().__init__(timeout=None)
        self.username = username

    @discord.ui.button(label="🔑 إدخال التوكن", style=discord.ButtonStyle.secondary, row=0)
    async def token_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TokenModal(self.username))

    @discord.ui.button(label="🚀 تشغيل", style=discord.ButtonStyle.success, row=1)
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        d = active_sessions[self.username]
        if not d["token"]:
            await interaction.response.send_message("⚠️️ يجب إدخال التوكن أولاً!", ephemeral=True)
            return
        d["status"] = "running"
        if d["count"] >= d["max_tickets"]: d["count"] = 0
        save_user_data(self.username, d)
        
        # تحديث اللوحة فوراً لتتحول إلى نشط
        await show_main_panel(interaction, self.username, edit=True, custom_interaction=interaction)
        
        # تشغيل محرك القنص في الخلفية
        asyncio.create_task(run_gateway_sniper(self.username, interaction.client))

    @discord.ui.button(label="🛑 إيقاف", style=discord.ButtonStyle.danger, row=1)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        active_sessions[self.username]["status"] = "stopped"
        save_user_data(self.username, active_sessions[self.username])
        await show_main_panel(interaction, self.username, edit=True, custom_interaction=interaction)

    @discord.ui.button(label="⚙️ تعديل السرعة والهدف", style=discord.ButtonStyle.primary, row=2)
    async def settings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SettingsModal(self.username))

    @discord.ui.button(label="💬 تعديل الرسالة", style=discord.ButtonStyle.primary, row=2)
    async def msg_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MessageModal(self.username))

async def show_main_panel(interaction: discord.Interaction, username, edit=False, custom_interaction=None):
    d = active_sessions[username]
    status_text = "نشط 🚀" if d["status"] == "running" else "متوقف 🛑"
    status_color = discord.Color.green() if d["status"] == "running" else discord.Color.red()

    embed = discord.Embed(title=f"💎 M.R Command Center - [{username}]", color=status_color)
    embed.add_field(name="🎯 الهدف", value=f"`{d['count']} / {d['max_tickets']}`", inline=True)
    embed.add_field(name="⚡ السرعة", value=f"`{d['speed']}s`", inline=True)
    embed.add_field(name="📌 الحالة", value=f"`{status_text}`", inline=False)
    embed.add_field(name="💬 رسالة الاستلام", value=f"```{d['message']}```", inline=False)
    logs_str = "\n".join(d["logs"][:5]) if d["logs"] else "• النظام جاهز..."
    embed.add_field(name="📜 السجلات (LOGS)", value=f"```{logs_str}```", inline=False)

    target_interaction = custom_interaction or interaction
    if edit:
        try: 
            if not target_interaction.response.is_done():
                await target_interaction.response.edit_message(embed=embed, view=MRView(username))
            else:
                await target_interaction.message.edit(embed=embed, view=MRView(username))
        except: 
            try:
                await interaction.message.edit(embed=embed, view=MRView(username))
            except:
                pass
    else:
        try:
            await interaction.followup.send(embed=embed, view=MRView(username), ephemeral=True)
        except:
            await interaction.response.send_message(embed=embed, view=MRView(username), ephemeral=True)

@client.tree.command(name="mr", description="فتح لوحة التحكم الخاصة بالقدماء فقط")
async def mr_command(interaction: discord.Interaction):
    discord_uid = str(interaction.user.id)
    if discord_uid in logged_in_users:
        uname = logged_in_users[discord_uid]
        if uname not in active_sessions:
            active_sessions[uname] = get_user_data(uname)
        await interaction.response.send_message("✨ أهلاً بك مجدداً، إليك لوحة التحكم الخاصة بك:", ephemeral=True)
        await show_main_panel(interaction, uname)
    else:
        embed = discord.Embed(title="🔐 بوابة القدماء الحصرية", description="هذا النظام مخصص للقدماء فقط. اضغط أدناه لإدخال اسمك وكلمة المرور المعتمدة:", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=embed, view=LoginView(), ephemeral=True)

async def run_gateway_sniper(username, bot_client):
    d = active_sessions[username]
    token = d["token"]
    d["logs"].insert(0, "🚀 بدأ تشغيل الاتصال الذكي...")
    
    headers = {
        "Authorization": token.strip(),
        "Content-Type": "application/json",
        "User-Agent": "Discord-iOS/241.0 (iPhone13,4; iOS 17.5)"
    }
    gateway_url = "wss://gateway.discord.gg/?v=9&encoding=json"
    
    while d["status"] == "running":
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(gateway_url) as ws:
                    async for msg in ws:
                        if d["status"] == "stopped": break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("op") == 10:
                                await ws.send_json({
                                    "op": 2,
                                    "d": {
                                        "token": token,
                                        "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"},
                                        "intents": 1 | 512
                                    }
                                })
                            if data.get("t") == "CHANNEL_CREATE" and data.get("d", {}).get("guild_id") == SERVER_ID:
                                ch_data = data["d"]
                                ch_id = str(ch_data["id"])
                                name = ch_data.get("name", "غير-معروف")
                                parent_id = str(ch_data.get("parent_id", ""))
                                if parent_id in list(CATEGORY_IDS.values()):
                                    created_ts = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                                    if time.time() - created_ts < 15:
                                        asyncio.create_task(execute_ticket_claim(username, ch_id, name, headers, bot_client))
        except Exception as e:
            d["logs"].insert(0, f"❌ خطأ اتصال، إعادة محاولة...")
            await asyncio.sleep(2)

async def execute_ticket_claim(username, ch_id, name, headers, bot_client):
    d = active_sessions[username]
    if d["status"] != "running": return
    if d["count"] >= d["max_tickets"]:
        d["status"] = "stopped"
        return
    if ch_id in d["active_tickets"]: return
    
    d["active_tickets"].add(ch_id)
    d["count"] += 1
    current_count = d["count"]
    max_lim = d["max_tickets"]

    if d["speed"] > 0: await asyncio.sleep(d["speed"])

    nonce = str(int(time.time() * 1000000)) + str(random.randint(10000, 99999))
    payload = {"content": d["message"], "nonce": nonce}

    max_retries = 3
    attempts = 0
    res = None

    async with aiohttp.ClientSession() as session:
        while attempts < max_retries:
            try:
                async with session.post(f"{API}/{ch_id}/messages", json=payload, headers=headers) as resp:
                    res = resp
                    if resp.status == 429:
                        try:
                            err_data = await resp.json()
                            retry_after = float(err_data.get("retry_after", 1.0))
                        except:
                            retry_after = 1.0
                        await asyncio.sleep(retry_after + 0.1)
                        attempts += 1
                        continue
                    elif resp.status in [200, 201]:
                        break
                    else:
                        break
            except:
                break

        if res and res.status in [200, 201]:
            d["logs"].insert(0, f"✨ تم قنص تكت بنجاح: **#{name}** ({current_count}/{max_lim})")
            
            for d_uid, uname in logged_in_users.items():
                if uname == username:
                    try:
                        user_obj = await bot_client.fetch_user(int(d_uid))
                        ticket_link = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
                        await user_obj.send(f"💎 **تم استلام تذكرة بنجاح!**\n🎫 التكت: `#{name}`\n🔗 الرابط: {ticket_link}")
                    except: pass

            if username == "Saif":
                try:
                    await session.post(f"{API}/{SAIF_ALERT_CHANNEL}/messages", json={"content": f"💎 الإداري استلم تذكرة ✅\n🎫 `#{name}`\n🔗 https://discord.com/channels/{SERVER_ID}/{ch_id}", "nonce": nonce}, headers=headers)
                except: pass

            save_user_data(username, d)
            if current_count >= max_lim:
                d["status"] = "stopped"
                d["logs"].insert(0, "🛑 تم بلوغ الهدف الأقصى.")
        else:
            d["count"] -= 1
            err_code = res.status if res else "Drop"
            d["logs"].insert(0, f"❌ تعذر استلام #{name} (خطأ: {err_code})")

        if ch_id in d["active_tickets"]: d["active_tickets"].remove(ch_id)

client.run(TOKEN_BOT)
