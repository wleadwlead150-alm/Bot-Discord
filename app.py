import discord
from discord import app_commands
import asyncio
import requests
import websocket
import threading
import os
import sqlite3
import random
from datetime import datetime
import http.server
import socketserver

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
API = "https://discord.com/api/v9"
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

db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY, 
                        password TEXT, 
                        token TEXT, 
                        message TEXT, 
                        speed REAL, 
                        max_tickets INTEGER, 
                        count INTEGER
                    )''')
        for uname, pwd in INITIAL_USERS.items():
            c.execute("SELECT username FROM users WHERE username=?", (uname,))
            if not c.fetchone():
                c.execute('''INSERT INTO users (username, password, token, message, speed, max_tickets, count) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                          (uname, pwd, "", f"أهلاً بك، معك {uname} الإدارة العليا. كيف يمكنني مساعدتك؟", 0.5, 10, 0))
        conn.commit()
        conn.close()

init_db()

def get_user_data(username):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT password, token, message, speed, max_tickets, count FROM users WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "password": row[0],
                "token": row[1] or "",
                "message": row[2] or f"أهلاً بك، معك {username} الإدارة العليا. كيف يمكنني مساعدتك؟",
                "speed": row[3] if row[3] is not None else 0.5,
                "max_tickets": row[4] or 10,
                "count": row[5] or 0,
                "status": "stopped",
                "logs": [],
                "active_tickets": set(),
                "lock": threading.Lock()
            }
        return None

def save_user_data(username, data):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''UPDATE users SET token=?, message=?, speed=?, max_tickets=?, count=? WHERE username=?''', 
                  (data["token"], data["message"], data["speed"], data["max_tickets"], data["count"], username))
        conn.commit()
        conn.close()

active_sessions = {}
logged_in_users = {}

class MRClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
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
            discord_uid = str(interaction.user.id)
            logged_in_users[discord_uid] = uname
            if uname not in active_sessions:
                active_sessions[uname] = get_user_data(uname)
            
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
        await show_main_panel(interaction, self.username, edit=True, custom_interaction=interaction)

class MessageModal(discord.ui.Modal, title="💬 تعديل رسالة استلام التكت"):
    msg_input = discord.ui.TextInput(label="نص الرد التلقائي", style=discord.TextStyle.paragraph, placeholder="اكتب الرسالة...", required=True)

    def __init__(self, username):
        super().__init__()
        self.username = username

    async def on_submit(self, interaction: discord.Interaction):
        active_sessions[self.username]["message"] = self.msg_input.value.strip()
        save_user_data(self.username, active_sessions[self.username])
        await interaction.response.send_message("✅ تم تحديث رسالة الاستلام!", ephemeral=True)
        await show_main_panel(interaction, self.username, edit=True, custom_interaction=interaction)

class SettingsModal(discord.ui.Modal, title="⚙️️ إعدادات السرعة والهدف"):
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
            await show_main_panel(interaction, self.username, edit=True, custom_interaction=interaction)
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
            await interaction.response.send_message("⚠️ يجب إدخال التوكن أولاً!", ephemeral=True)
            return
        d["status"] = "running"
        if d["count"] >= d["max_tickets"]: d["count"] = 0
        save_user_data(self.username, d)
        
        await show_main_panel(interaction, self.username, edit=True, custom_interaction=interaction)
        
        # تشغيل محرك الاتصال اللحظي WebSocket
        threading.Thread(target=run_discord_gateway, args=(self.username, interaction.client), daemon=True).start()

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

# --- محرك القنص اللحظي السريع عبر Gateway WebSocket ---
def process_ticket(username, ch_id, name, bot_client):
    session_data = active_sessions[username]
    with session_data["lock"]:
        if session_data["status"] != "running": return
        if session_data["count"] >= session_data["max_tickets"]:
            session_data["status"] = "stopped"
            return
        if ch_id in session_data["active_tickets"]: return
        session_data["active_tickets"].add(ch_id)
        session_data["count"] += 1
        current_count = session_data["count"]
        max_lim = session_data["max_tickets"]

    headers = {
        "Authorization": session_data["token"].strip(),
        "Content-Type": "application/json",
        "User-Agent": "Discord-iOS/241.0 (iPhone13,4; iOS 17.5)"
    }
    
    nonce = str(int(time.time() * 1000000)) + str(random.randint(10000, 99999))
    payload = {"content": session_data["message"], "nonce": nonce}

    res = None
    max_retries = 3
    attempts = 0
    
    try:
        if session_data["speed"] > 0: 
            time.sleep(session_data["speed"])
            
        while attempts < max_retries:
            res = requests.post(f"{API}/channels/{ch_id}/messages", json=payload, headers=headers, timeout=5)
            if res.status_code == 429:
                try:
                    data = res.json()
                    retry_after = float(data.get("retry_after", 1.0))
                except:
                    retry_after = 1.0
                time.sleep(retry_after + 0.1)
                attempts += 1
                continue
            elif res.status_code in [200, 201]:
                break
            else:
                break
    except:
        res = None

    with session_data["lock"]:
        if res and res.status_code in [200, 201]:
            session_data["logs"].insert(0, f"✨ تم قنص تكت جديد بنجاح: **#{name}** ({current_count}/{max_lim})")
            
            for d_uid, uname in logged_in_users.items():
                if uname == username:
                    ticket_link = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
                    asyncio.run_coroutine_threadsafe(send_user_dm(bot_client, int(d_uid), name, ticket_link), bot_client.loop)

            if username == "Saif":
                try: 
                    requests.post(f"{API}/channels/{SAIF_ALERT_CHANNEL}/messages", json={"content": f"💎 الإداري **{username}** استلم تذكرة ✅\n🎫 `#{name}`\n🔗 https://discord.com/channels/{SERVER_ID}/{ch_id}", "nonce": nonce}, headers=headers, timeout=3)
                except: pass
                
            save_user_data(username, session_data)
            if current_count >= max_lim:
                session_data["status"] = "stopped"
                session_data["logs"].insert(0, "🛑 تم بلوغ الحد الأقصى.")
        else:
            session_data["count"] -= 1
            err_code = res.status_code if res else "Connection Drop"
            session_data["logs"].insert(0, f"❌ تعذر استلام #{name} (خطأ: {err_code})")
            
        if ch_id in session_data["active_tickets"]: 
            session_data["active_tickets"].remove(ch_id)

async def send_user_dm(bot_client, uid, name, ticket_link):
    try:
        user_obj = await bot_client.fetch_user(uid)
        await user_obj.send(f"💎 **تم استلاستلام تذكرة بنجاح!**\n🎫 التكت: `#{name}`\n🔗 الرابط: {ticket_link}")
    except:
        pass

def run_discord_gateway(username, bot_client):
    d = active_sessions[username]
    token = d["token"]
    d["logs"].insert(0, "🚀 تم تفعيل محرك القنص اللحظي (Gateway)...")

    def on_message(ws, msg):
        if d["status"] == "stopped":
            ws.close()
            return
        try:
            raw = json.loads(msg)
            if raw.get("op") == 10:
                ws.send(json.dumps({"op": 1, "d": None}))
            
            # التقاط حدث إنشاء قناة جديدة في السيرفر المستهدف فوراً
            if raw.get("t") == "CHANNEL_CREATE":
                ch_data = raw.get("d", {})
                if str(ch_data.get("guild_id")) == SERVER_ID:
                    ch_id = str(ch_data["id"])
                    name = ch_data.get("name", "غير-معروف")
                    parent_id = str(ch_data.get("parent_id", ""))
                    
                    if parent_id in list(CATEGORY_IDS.values()):
                        created_ts = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                        if time.time() - created_ts < 15:
                            threading.Thread(target=process_ticket, args=(username, ch_id, name, bot_client), daemon=True).start()
        except:
            pass

    def on_open(ws):
        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": token,
                "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"},
                "intents": 1 | 512 | 1024 # تفعيل كامل الصلاحيات لقراءة القنوات
            }
        }))

    while d["status"] == "running":
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_open=on_open, on_message=on_message)
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except:
            time.sleep(2)

client.run(TOKEN_BOT)
