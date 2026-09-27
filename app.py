import json
import re
import time
import requests
import websocket
import threading
import random
import os
import base64
import sqlite3
import csv
from datetime import datetime
from io import StringIO
from flask import Flask, render_template_string, request, redirect, url_for, session, make_response, jsonify

app = Flask(__name__)
app.secret_key = "MR_ELITE_SECRET_CORE_V99_FIXED"

# الحسابات الافتراضية
INITIAL_USERS = {
    "Saif": "12345678", "Marshall": "oopp0099", "Youssef": "oopp009987",
    "Kara": "oopp00998", "isso": "12345678", "Azmy": "12345678", "Dark": "123456789"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
SAIF_ALERT_CHANNEL = "1545711547169513483"
MASTER_PASSWORD = "MR_EAGLE_99"

CATEGORY_IDS = {
    "administrative": "1353444395575414844",
    "players": "1353444390387060736",
    "factions": "1353444400679747665"
}

THEMES = {
    "cyber_red": {"name": "أحمر Cyberpunk", "prim": "#dc2626", "sec": "#7f1d1d", "bg": "#170505"},
    "lynwood": {"name": "أزرق Lynwood Police", "prim": "#2563eb", "sec": "#1e3a8a", "bg": "#0a0f1d"},
    "neon_purple": {"name": "بنفسجي Neon", "prim": "#9333ea", "sec": "#4c1d95", "bg": "#0f0518"},
    "stealth_dark": {"name": "أسود شبحي Stealth", "prim": "#475569", "sec": "#1e293b", "bg": "#020617"}
}

user_sessions = {}
db_lock = threading.Lock()

def cipher(text, encrypt=True):
    if not text: return ""
    key = app.secret_key
    if not encrypt:
        try: text = base64.b64decode(text.encode()).decode()
        except: return text
    res = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))
    if encrypt: return base64.b64encode(res.encode()).decode()
    return res

def create_default_session_data(uname, pwd):
    return {
        "password": pwd, "status": "stopped", "thread": None, "token": "",
        "message": f"أهلاً بك، معك {uname} الإدارة العليا. كيف يمكنني مساعدتك؟",
        "ticket_filter": "all", "speed": 1.1, "max_tickets": 10, "count": 0, "total_lifetime": 0,
        "logs": [], "banned_secure": False, "last_sent_text": "", "last_sent_time": 0,
        "active_tickets": set(), "lock": threading.Lock(), "theme": "cyber_red", "claimed_history": []
    }

def init_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY, password TEXT, token TEXT, message TEXT, 
                      ticket_filter TEXT, speed REAL, max_tickets INTEGER,
                      count INTEGER, total_lifetime INTEGER, theme TEXT)''')
        
        c.execute("PRAGMA table_info(users)")
        existing_cols = [col[1] for col in c.fetchall()]
        if "password" not in existing_cols:
            try: c.execute("ALTER TABLE users ADD COLUMN password TEXT DEFAULT '12345678'")
            except: pass

        for uname, pwd in INITIAL_USERS.items():
            c.execute("SELECT username FROM users WHERE username=?", (uname,))
            if not c.fetchone():
                c.execute('''INSERT INTO users (username, password, token, message, ticket_filter, speed, max_tickets, count, total_lifetime, theme)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                             (uname, pwd, "", f"أهلاً بك، معك {uname} الإدارة العليا. كيف يمكنني مساعدتك؟", "all", 1.1, 10, 0, 0, "cyber_red"))
        conn.commit()
        conn.close()

def load_db():
    global user_sessions
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        rows = c.fetchall()
        col_names = [description[0] for description in c.description]
        conn.close()
        
        for r in rows:
            row_dict = dict(zip(col_names, r))
            uname = row_dict["username"]
            if uname not in user_sessions:
                user_sessions[uname] = create_default_session_data(uname, row_dict.get("password", "12345678"))
            
            user_sessions[uname]["password"] = row_dict.get("password", "12345678")
            user_sessions[uname]["token"] = cipher(row_dict.get("token", ""), False)
            user_sessions[uname]["message"] = row_dict.get("message", "")
            user_sessions[uname]["ticket_filter"] = row_dict.get("ticket_filter", "all")
            user_sessions[uname]["speed"] = row_dict.get("speed", 1.1)
            user_sessions[uname]["max_tickets"] = row_dict.get("max_tickets", 10)
            user_sessions[uname]["count"] = row_dict.get("count", 0)
            user_sessions[uname]["total_lifetime"] = row_dict.get("total_lifetime", 0)
            user_sessions[uname]["theme"] = row_dict.get("theme", "cyber_red")

def save_db(uname):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        d = user_sessions[uname]
        enc_token = cipher(d["token"], True)
        
        c.execute("SELECT username FROM users WHERE username=?", (uname,))
        if not c.fetchone():
            c.execute('''INSERT INTO users (username, password, token, message, ticket_filter, speed, max_tickets, count, total_lifetime, theme)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (uname, d["password"], enc_token, d["message"], d["ticket_filter"], d["speed"], d["max_tickets"], d["count"], d["total_lifetime"], d.get("theme","cyber_red")))
        else:
            c.execute('''UPDATE users SET password=?, token=?, message=?, ticket_filter=?, 
                         speed=?, max_tickets=?, count=?, total_lifetime=?, theme=? WHERE username=?''',
                      (d["password"], enc_token, d["message"], d["ticket_filter"],
                       d["speed"], d["max_tickets"], d["count"], d["total_lifetime"], d.get("theme","cyber_red"), uname))
        conn.commit()
        conn.close()

init_db()
load_db()

# ✅ تحديث حماية ديسكورد الجديدة (Shadow Ban Bypass)
def get_secure_headers(token):
    props = {"os": "iOS", "browser": "Discord Client", "device": "iPhone 13, pro, max", "system_version": "17.5", "client_build_number": 335000, "client_version": "245.0"}
    b64_props = base64.b64encode(json.dumps(props).encode()).decode()
    return {
        "Authorization": token.strip(), "Content-Type": "application/json",
        "User-Agent": "Discord/245.0 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": b64_props, "X-Discord-Locale": "ar", "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
    }

def safe_post(username, url, payload, current_speed, is_claim=False):
    d = user_sessions[username]
    token = d["token"]
    headers = get_secure_headers(token)
    try:
        if current_speed > 0: time.sleep(current_speed)
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        remaining = int(res.headers.get('X-RateLimit-Remaining', 5))
        if remaining <= 0: 
            reset_after = float(res.headers.get('X-RateLimit-Reset-After', 0.5))
            time.sleep(reset_after + 0.05)
        if res.status_code == 429:
            retry_after = res.json().get("retry_after", 1.0)
            time.sleep(retry_after + 0.1)
            return safe_post(username, url, payload, 0)
        return res
    except: return None

def process_ticket(username, ch_id, name, parent_id):
    session_data = user_sessions[username]
    with session_data["lock"]:
        if session_data["status"] != "running" or session_data.get("banned_secure"): return
        if session_data["count"] >= session_data["max_tickets"]:
            session_data["status"] = "stopped"
            return

        filter_mode = session_data.get("ticket_filter", "all")
        if filter_mode != "all":
            expected_category = CATEGORY_IDS.get(filter_mode)
            if expected_category and str(parent_id) != str(expected_category):
                return
            
        if ch_id in session_data["active_tickets"]: return
        session_data["active_tickets"].add(ch_id)
        
        session_data["count"] += 1
        session_data["total_lifetime"] += 1
        current_count = session_data["count"]
        max_lim = session_data["max_tickets"]

    current_speed = session_data["speed"]
    custom_msg = session_data["message"]
    
    now_ts = time.time()
    if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 2.0):
        custom_msg += "᠎" * random.randint(1, 2)
    session_data["last_sent_text"] = custom_msg
    session_data["last_sent_time"] = now_ts

    # ✅ توليد Nonce زمني لمنع ديسكورد من حظر الرسالة بصمت
    nonce = str((int(time.time()) * 1000 - 1420070400000) << 22)
    payload = {"content": custom_msg, "nonce": nonce}

    res = safe_post(username, f"{API}/{ch_id}/messages", payload, current_speed, is_claim=True)
    
    with session_data["lock"]:
        if res and res.status_code in [200, 201]:
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"✨ استلمت **#{name}** | <a href='{ticket_url}' target='_blank'>الرابط</a>"
            
            t_time = datetime.now().strftime("%I:%M %p")
            session_data["claimed_history"].append({"id": ch_id, "name": name, "time": t_time})
            if len(session_data["claimed_history"]) > 20: session_data["claimed_history"].pop(0)

            if username == "Saif":
                alert_payload = {
                    "content": f"💎 **إشعار الإدارة** 💎\nالإداري **{username}** استلم تذكرة ✅\n🎫 `#{name}`\n🔗 {ticket_url}",
                    "nonce": str((int(time.time()) * 1000 - 1420070400000) << 22)
                }
                threading.Thread(target=safe_post, args=(username, f"{API}/{SAIF_ALERT_CHANNEL}/messages", alert_payload, 0)).start()

            session_data["logs"].insert(0, f"{log_text} ({current_count}/{max_lim})")
            if len(session_data["logs"]) > 20: session_data["logs"].pop()
            save_db(username)

            if current_count >= max_lim:
                session_data["status"] = "stopped"
                session_data["logs"].insert(0, "🛑 تم بلوغ الحد الأقصى، توقف النظام.")
        else:
            err_code = res.status_code if res else "Unknown"
            session_data["count"] = max(0, session_data["count"] - 1)
            session_data["total_lifetime"] = max(0, session_data["total_lifetime"] - 1)
            session_data["logs"].insert(0, f"<span style='color: #ef4444;'>❌ تعذر استلام #{name} (Code: {err_code})</span>")
            
        if ch_id in session_data["active_tickets"]: session_data["active_tickets"].remove(ch_id)

def run_discord_bot(username):
    d = user_sessions[username]
    token = d["token"]
    d["logs"].insert(0, "🚀 تم تفعيل النظام الكلاسيكي السريع جداً...")
    
    def on_message(ws, msg):
        if d["status"] == "stopped" or d["banned_secure"]:
            ws.close(); return
        if d["status"] == "paused":
            return
        
        try:
            raw = json.loads(msg)
            t = raw.get("t")
            evt_data = raw.get("d", {})
            
            if raw.get("op") == 10: ws.send(json.dumps({"op": 1, "d": None}))
            
            if t == "CHANNEL_CREATE":
                if evt_data.get("guild_id") == SERVER_ID and evt_data.get("type") == 0:
                    ch_id = evt_data.get("id")
                    name = evt_data.get("name", "").lower()
                    parent_id = evt_data.get("parent_id", "")
                    
                    created_timestamp = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                    if time.time() - created_timestamp > 15: return 

                    with d["lock"]:
                        if d["count"] >= d["max_tickets"] or d["status"] != "running": return
                    
                    threading.Thread(target=process_ticket, args=(username, ch_id, name, parent_id)).start()
        except: pass

    def on_open(ws):
        ws.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"}, "intents": 1 | 512}}))

    while d["status"] in ["running", "paused"] and not d["banned_secure"]:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_open=on_open, on_message=on_message)
            ws.run_forever()
        except: time.sleep(2)

# ================= واجهات HTML =================

MANIFEST_JSON = """
{
  "name": "M.R Sniper Pro",
  "short_name": "M.R Sniper",
  "start_url": "/login",
  "display": "standalone",
  "background_color": "#030712",
  "theme_color": "#ef4444",
  "icons": [
    {"src": "https://cdn-icons-png.flaticon.com/512/2202/2202112.png", "sizes": "512x512", "type": "image/png"}
  ]
}
"""

LANDING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="manifest" href="/manifest.json">
    <title>M.R COMMAND CENTER</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap');
        body { background: #030712; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: 'Orbitron', sans-serif; overflow: hidden; }
        .glitch-wrapper { position: relative; text-align: center; }
        h1 { font-size: 3.5rem; margin: 0; letter-spacing: 4px; color: #f8fafc; text-shadow: 0 0 20px rgba(255,255,255,0.2); }
        h3 { font-size: 1.2rem; color: #94a3b8; margin-top: 10px; letter-spacing: 12px; font-weight: 400; text-transform: uppercase;}
        .red-btn { margin-top: 50px; padding: 18px 50px; background: transparent; border: 2px solid #ef4444; color: #ef4444; font-size: 1.2rem; font-weight: 700; text-transform: uppercase; letter-spacing: 3px; text-decoration: none; border-radius: 8px; transition: all 0.3s ease; cursor: pointer; }
        .red-btn:hover { background: #ef4444; color: #fff; box-shadow: 0 0 40px rgba(239,68,68,0.8); transform: scale(1.05); }
    </style>
</head>
<body>
    <div class="glitch-wrapper">
        <h1>DISCORD TICKET</h1>
        <h3>Developer M.R</h3>
    </div>
    <a href="/login" class="red-btn">ENTER SYSTEM</a>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="manifest" href="/manifest.json">
    <title>بوابة الخزنة السحرية</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;800&display=swap');
        body { background: #030712; color: #fff; font-family: 'Cairo', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(15px); padding: 40px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.2); box-shadow: 0 20px 50px rgba(0,0,0,0.8); width: 320px; text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: rgba(0,0,0,0.6); border: 1px solid #1e293b; color: #fff; border-radius: 8px; text-align: center; outline: none; transition: 0.3s; box-sizing: border-box; font-size: 16px;}
        input:focus { border-color: #3b82f6; box-shadow: 0 0 10px rgba(59,130,246,0.3); }
        button { width: 100%; padding: 12px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-weight: 800; font-family: 'Cairo'; font-size: 16px; cursor: pointer; transition: 0.3s; margin-top: 15px;}
        button:hover { background: #2563eb; box-shadow: 0 0 20px rgba(59,130,246,0.5); }
        .avatar { width: 90px; height: 90px; border-radius: 50%; border: 3px solid #3b82f6; margin-bottom: 10px; background: #1e293b; display: inline-flex; align-items: center; justify-content: center; font-size: 30px; font-weight: bold;}
        #pin-input { font-size: 24px; letter-spacing: 15px; font-family: monospace;}
        .error-msg { color: #ef4444; font-size: 12px; margin-top: 10px; display: none; }
    </style>
</head>
<body>
    <div class="card" id="login-container">
        <div id="vault-view" style="display:none;">
            <div class="avatar" id="vault-avatar">M</div>
            <h2 id="vault-name" style="margin:5px 0 20px 0; color:#cbd5e1;">مرحباً مجدداً</h2>
            <p style="font-size:12px; color:#94a3b8; margin-bottom:15px;">أدخل رمز PIN السري للوصول السريع</p>
            <input type="password" id="pin-input" maxlength="4" pattern="[0-9]*" inputmode="numeric" placeholder="••••">
            <div id="pin-error" class="error-msg">الرمز غير صحيح، حاول مجدداً</div>
            <button onclick="unlockVault()">فتح الخزنة 🔓</button>
            <a href="#" onclick="resetVault()" style="color:#ef4444; text-decoration:none; font-size:12px; display:block; margin-top:20px;">تسجيل الدخول بحساب آخر</a>
        </div>
        <div id="normal-view" style="display:none;">
            <h2 style="margin-top:0;">إعداد الحساب لأول مرة</h2>
            <input type="text" id="username" placeholder="اسم المستخدم" required>
            <input type="password" id="password" placeholder="كلمة المرور" required>
            <hr style="border: 1px solid #1e293b; margin: 15px 0;">
            <p style="font-size:11px; color:#94a3b8; margin-bottom:5px;">أنشئ رمز PIN لسهولة الدخول لاحقاً</p>
            <input type="password" id="new-pin" placeholder="رمز PIN من 4 أرقام" maxlength="4" pattern="[0-9]*" inputmode="numeric" required>
            <button onclick="saveAndLogin()">دخول وحفظ 💾</button>
            {% if error %}<p style="color:#ef4444; font-size:12px; margin-top:10px;">{{ error }}</p>{% endif %}
        </div>
        <form id="hidden-form" method="POST" style="display:none;">
            <input type="hidden" name="username" id="hidden-user">
            <input type="hidden" name="password" id="hidden-pass">
        </form>
    </div>
    <script>
        let vaultData = localStorage.getItem("mr_vault_v99");
        if (vaultData) {
            let data = JSON.parse(vaultData);
            document.getElementById("vault-name").innerText = "مرحباً " + data.u;
            document.getElementById("vault-avatar").innerText = data.u.charAt(0).toUpperCase();
            document.getElementById("vault-view").style.display = "block";
        } else {
            document.getElementById("normal-view").style.display = "block";
        }
        function saveAndLogin() {
            let u = document.getElementById("username").value;
            let p = document.getElementById("password").value;
            let pin = document.getElementById("new-pin").value;
            if(!u || !p || pin.length !== 4) { alert("يرجى تعبئة جميع الحقول وتأكد أن الرمز 4 أرقام."); return; }
            localStorage.setItem("mr_vault_v99", JSON.stringify({u: u, p: btoa(p), pin: pin}));
            document.getElementById("hidden-user").value = u;
            document.getElementById("hidden-pass").value = p;
            document.getElementById("hidden-form").submit();
        }
        function unlockVault() {
            let data = JSON.parse(localStorage.getItem("mr_vault_v99"));
            let inputPin = document.getElementById("pin-input").value;
            if (inputPin === data.pin) {
                document.getElementById("hidden-user").value = data.u;
                document.getElementById("hidden-pass").value = atob(data.p);
                document.getElementById("hidden-form").submit();
            } else {
                document.getElementById("pin-error").style.display = "block";
                document.getElementById("pin-input").value = "";
            }
        }
        function resetVault() {
            localStorage.removeItem("mr_vault_v99");
            document.getElementById("vault-view").style.display = "none";
            document.getElementById("normal-view").style.display = "block";
        }
    </script>
</body>
</html>
"""

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="manifest" href="/manifest.json">
    <title>M.R Elite Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=gg+sans:wght@400;600&display=swap'); 
        
        :root { --prim: {{ theme_data.prim }}; --sec: {{ theme_data.sec }}; --bg: {{ theme_data.bg }}; }
        body { background: var(--bg); color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 15px; padding-bottom: 60px; min-height: 100vh;}
        
        .openbtn { font-size: 26px; cursor: pointer; background: rgba(0,0,0,0.6); color: white; border: 1px solid var(--prim); border-radius: 50%; width: 50px; height: 50px; position: fixed; top: 15px; left: 15px; z-index: 900; box-shadow: 0 0 10px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;}
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; right: 0; background-color: rgba(10, 15, 29, 0.98); backdrop-filter: blur(15px); overflow-x: hidden; transition: 0.4s; padding-top: 60px; text-align: right; border-left: 1px solid rgba(255,255,255,0.1); box-shadow: -10px 0 30px rgba(0,0,0,0.8);}
        .sidebar-content { padding: 8px 25px; }
        .sidebar .closebtn { position: absolute; top: 10px; right: 25px; font-size: 36px; padding: 0; color: #ef4444; text-decoration: none;}
        
        .glass-card { background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(20px); max-width: 440px; width: 100%; padding: 26px; border-radius: 20px; border: 1px solid rgba(255,255,255, 0.1); box-shadow: 0 25px 50px rgba(0,0,0,0.9), inset 0 0 20px var(--sec); margin: 10px auto;}
        h1 { color: #fff; font-size: 20px; margin-bottom: 5px; font-weight: 900; }
        .user-tag { color: var(--prim); font-size: 13px; background: rgba(0,0,0,0.5); padding: 5px 15px; border-radius: 20px; border: 1px solid var(--prim); display: inline-block; margin-bottom: 15px;}
        
        .badge-container { display: flex; gap: 5px; margin-bottom: 15px; }
        .glass-badge { flex: 1; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.05); padding: 8px; border-radius: 12px; font-size: 11px; }
        .glass-badge b { color: var(--prim); font-size: 13px; display: block; margin-top: 3px; }
        .chart-container { background: rgba(0,0,0,0.4); border-radius: 14px; padding: 10px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 15px; height: 130px; }

        .action-row { display: flex; gap: 8px; margin-bottom: 15px; }
        .btn { flex: 1; padding: 12px; font-size: 14px; font-weight: 800; border: none; border-radius: 12px; cursor: pointer; transition: 0.3s; font-family: 'Cairo'; color: #fff;}
        .btn-start { background: linear-gradient(135deg, #059669, #047857); }
        .btn-pause { background: linear-gradient(135deg, #fbbf24, #d97706); color: #000;}
        .btn-stop { background: linear-gradient(135deg, #dc2626, #991b1b); }
        .btn-secondary { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); width: 100%; margin-top: 5px;}
        .btn-notify { background: linear-gradient(135deg, #8b5cf6, #6d28d9); margin-top: 15px; box-shadow: 0 0 15px rgba(139,92,246,0.3);}

        .config-title { color: var(--prim); font-size: 12px; margin-bottom: 4px; font-weight: 700; text-align: right;}
        input, select, textarea { width: 100%; padding: 12px; background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 10px; box-sizing: border-box; font-size: 12px; margin-bottom: 10px; font-family: 'Cairo'; outline: none;}
        textarea { height: 60px; resize: none; }
        .log-box { background: #000; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 10px; height: 90px; overflow-y: auto; text-align: right; font-size: 11px; color: #94a3b8; margin-top: 10px; }

        .ghost-panel { display: none; background: #313338; max-width: 440px; width: 100%; padding: 0; border-radius: 15px; border: 1px solid #1e1f22; box-shadow: 0 25px 50px rgba(0,0,0,0.9); margin: 20px auto; flex-direction: column; height: 600px; overflow: hidden; font-family: 'gg sans', 'Segoe UI', sans-serif;}
        .ghost-header { background: #2b2d31; color: #f2f3f5; font-weight: bold; padding: 15px; font-size: 15px; text-align: right; border-bottom: 1px solid #1e1f22;}
        .ticket-list { display: flex; padding: 10px; gap: 5px; background: #2b2d31; overflow-x: auto; border-bottom: 1px solid #1e1f22;}
        .tkt-btn { background: #2b2d31; border: none; color: #949ba4; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 600; white-space: nowrap; transition: 0.2s;}
        .tkt-btn.active { background: #404249; color: #f2f3f5; }
        .chat-box { flex: 1; background: #313338; padding: 15px 0; overflow-y: auto; display: flex; flex-direction: column; gap: 2px;}
        .discord-msg { display: flex; padding: 8px 15px; margin-top: 5px; flex-direction: row-reverse; text-align: right;}
        .discord-avatar { width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; margin-left: 0; background: #5865F2; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 16px; flex-shrink: 0;}
        .discord-msg-content { flex: 1; }
        .discord-msg-header { margin-bottom: 2px; display: flex; align-items: baseline; flex-direction: row-reverse; gap: 8px;}
        .discord-username { color: #f2f3f5; font-weight: 600; font-size: 15px;}
        .discord-text { color: #dbdee1; font-size: 15px; line-height: 1.375; word-break: break-word;}
    </style>
</head>
<body>
    <button class="openbtn" onclick="openNav()">=</button>

    <div id="mySidebar" class="sidebar">
        <a href="javascript:void(0)" class="closebtn" onclick="closeNav()">&times;</a>
        <h2 style="color:var(--prim); text-align:center; margin-bottom:20px;">الإعدادات المتقدمة</h2>
        <div class="sidebar-content">
            <form action="/update_sidebar" method="post">
                <div class="config-title">تخصيص المظهر:</div>
                <select name="theme">
                    {% for k, v in themes.items() %}<option value="{{ k }}" {% if theme == k %}selected{% endif %}>{{ v.name }}</option>{% endfor %}
                </select>
                <div class="config-title">نوع الشكاوي:</div>
                <select name="ticket_filter">
                    <option value="all" {% if ticket_filter == 'all' %}selected{% endif %}>🌐 جميع التكتات</option>
                    <option value="administrative" {% if ticket_filter == 'administrative' %}selected{% endif %}>🛡️ شكاوى إدارية</option>
                </select>
                <button type="submit" class="btn btn-secondary" style="background: var(--prim); color:#fff;">حفظ التغييرات</button>
            </form>
            <button onclick="toggleGhost()" class="btn btn-secondary">👁️ إظهار/إخفاء شاشة ديسكورد</button>
            <form action="/token" method="get"><button class="btn btn-secondary">🔑 تحديث التوكن</button></form>
            <form action="/reset_all" method="post" onsubmit="return confirm('هل أنت متأكد؟');"><button class="btn btn-secondary" style="color:#ef4444;">🗑️ تصفير العداد</button></form>
            <button onclick="requestNotificationPermission()" class="btn btn-notify">🔔 إشعارات الجوال (Push)</button>
            <a href="/logout" style="color:#ef4444; text-align:center; font-weight:bold; margin-top:20px; display:block; text-decoration:none;">تسجيل خروج</a>
        </div>
    </div>

    <div class="glass-card">
        <h1>M.R COMMAND CENTER</h1>
        <div class="user-tag">👤 {{ username }}</div>
        
        <div class="badge-container">
            <div class="glass-badge">الهدف <b id="count_disp">{{ count }}/{{ max_tickets }}</b></div>
            <div class="glass-badge">السرعة <b id="speed_disp">{{ speed }}s</b></div>
            <div class="glass-badge">الوضع <b id="status_disp" style="color: {% if status == 'running' %}#10b981{% elif status == 'paused' %}#fbbf24{% else %}#ef4444{% endif %};">
                {% if status == 'running' %}نشط 🚀{% elif status == 'paused' %}استراحة ⏸️{% else %}متوقف 🛑{% endif %}
            </b></div>
        </div>

        <div class="chart-container"><canvas id="progressChart"></canvas></div>
        
        <form action="/set_status" method="post" class="action-row">
            {% if status == 'stopped' %}
                <button type="submit" name="new_status" value="running" class="btn btn-start">تشغيل النظام 🚀</button>
            {% else %}
                {% if status == 'running' %}<button type="submit" name="new_status" value="paused" class="btn btn-pause">استراحة ⏸️</button>
                {% else %}<button type="submit" name="new_status" value="running" class="btn btn-start">استئناف ▶️</button>{% endif %}
                <button type="submit" name="new_status" value="stopped" class="btn btn-stop" style="flex: 0.5;">إيقاف 🛑</button>
            {% endif %}
        </form>

        <form action="/update_main" method="post">
            <div style="display:flex; gap:8px;">
                <div style="flex:1;"><div class="config-title">الحد الأقصى:</div><input type="number" name="max_tickets" value="{{ max_tickets }}" min="1"></div>
                <div style="flex:1;"><div class="config-title">السرعة:</div><input type="number" step="0.01" name="custom_speed" value="{{ speed }}"></div>
            </div>
            <div class="config-title">نص الرد المباشر:</div>
            <textarea name="custom_msg">{{ message }}</textarea>
            <button type="submit" class="btn btn-secondary">حفظ التغييرات السريعة 💾</button>
        </form>

        <div class="log-box" id="log_box">{% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div>النظام جاهز...</div>{% endfor %}</div>
    </div>

    <div class="ghost-panel" id="ghost_panel">
        <div class="ghost-header"><span style="font-size:20px; color:#80848e;">#</span> المراقبة الحية - Discord</div>
        <div class="ticket-list" id="ticket_list"></div>
        <div class="chat-box" id="chat_box"><div style="color:#949ba4; text-align:center; margin-top:50%; font-weight:600;">يرجى تحديد تذكرة للمراقبة...</div></div>
    </div>

    <script>
        function openNav() { document.getElementById("mySidebar").style.width = "300px"; }
        function closeNav() { document.getElementById("mySidebar").style.width = "0"; }
        function toggleGhost() { 
            var p = document.getElementById("ghost_panel");
            p.style.display = (p.style.display === "flex") ? "none" : "flex";
            closeNav();
        }

        function requestNotificationPermission() {
            if ("Notification" in window) {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") alert("✅ تم تفعيل إشعارات الجوال بنجاح!");
                    else alert("❌ الرجاء السماح للإشعارات من إعدادات جهازك.");
                });
            } else { alert("جهازك لا يدعم الإشعارات."); }
        }

        var ctx = document.getElementById('progressChart').getContext('2d');
        var myChart = new Chart(ctx, { type: 'doughnut', data: { labels: ['المنجز', 'المتبقي'], datasets: [{ data: [{{ count }}, {{ max_tickets - count if max_tickets - count > 0 else 0 }}], backgroundColor: ['{{ theme_data.prim }}', 'rgba(255,255,255,0.05)'], borderWidth: 0 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, cutout: '75%' } });

        let currentActiveTicket = null;
        let lastCount = {{ count }};

        function loadChat(ch_id) {
            currentActiveTicket = ch_id;
            document.querySelectorAll('.tkt-btn').forEach(b => b.classList.remove('active'));
            let btn = document.getElementById('btn_' + ch_id);
            if(btn) btn.classList.add('active');
            document.getElementById('chat_box').innerHTML = '<div style="color:#949ba4; text-align:center; margin-top:50%; font-weight:600;">جاري مزامنة الرسائل...</div>';
            fetchChat();
        }

        async function fetchChat() {
            if(!currentActiveTicket) return;
            try {
                let res = await fetch('/api/chat/' + currentActiveTicket);
                let msgs = await res.json();
                if(msgs.error) return;
                let chatHtml = '';
                msgs.forEach(m => {
                    let initial = m.author.charAt(0).toUpperCase();
                    chatHtml += `
                    <div class="discord-msg">
                        <div class="discord-avatar">${initial}</div>
                        <div class="discord-msg-content">
                            <div class="discord-msg-header"><span class="discord-username">${m.author}</span></div>
                            <div class="discord-text">${m.content}</div>
                        </div>
                    </div>`;
                });
                document.getElementById('chat_box').innerHTML = chatHtml || '<div style="color:#949ba4; text-align:center; margin-top:50%; font-weight:600;">لا توجد رسائل جديدة</div>';
            } catch(e) {}
        }

        setInterval(async () => {
            try {
                let res = await fetch('/api/status');
                let data = await res.json();
                
                if (data.count > lastCount) {
                    let newTicket = data.history[data.history.length - 1];
                    if ("Notification" in window && Notification.permission === "granted") {
                        new Notification("M.R Command Center 🚀", { body: "تم قنص تكت جديد بنجاح: #" + (newTicket ? newTicket.name : ""), icon: "https://cdn-icons-png.flaticon.com/512/2202/2202112.png" });
                    }
                    lastCount = data.count;
                } else if (data.count < lastCount) { lastCount = data.count; }

                document.getElementById('count_disp').innerText = data.count + '/' + data.max_tickets;
                document.getElementById('speed_disp').innerText = data.speed + 's';
                
                let sDisp = document.getElementById('status_disp');
                if(data.status === 'running') { sDisp.innerText = 'نشط 🚀'; sDisp.style.color = '#10b981'; }
                else if(data.status === 'paused') { sDisp.innerText = 'استراحة ⏸️'; sDisp.style.color = '#fbbf24'; }
                else { sDisp.innerText = 'متوقف 🛑'; sDisp.style.color = '#ef4444'; }

                let logHtml = '';
                data.logs.forEach(l => { logHtml += '<div>• ' + l + '</div>'; });
                document.getElementById('log_box').innerHTML = logHtml || '<div>النظام جاهز...</div>';

                let rem = data.max_tickets - data.count;
                myChart.data.datasets[0].data = [data.count, rem > 0 ? rem : 0];
                myChart.update();

                let tktsHtml = '';
                data.history.forEach(t => {
                    let activeCls = (currentActiveTicket == t.id) ? 'active' : '';
                    tktsHtml += `<button id="btn_${t.id}" class="tkt-btn ${activeCls}" onclick="loadChat('${t.id}')"><span style="color:#80848e;">#</span> ${t.name}</button>`;
                });
                document.getElementById('ticket_list').innerHTML = tktsHtml || '<div style="color:#949ba4; font-size:12px; font-weight:600; padding:10px;">لم يتم استلام تكتات بعد</div>';
            } catch(e) {}
        }, 2000); 
        setInterval(fetchChat, 3000);
    </script>
</body>
</html>
"""

MASTER_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Master Pro Dashboard</title>
    <style>
        body { background: #0f172a; color: #fff; font-family: sans-serif; padding: 20px;}
        .card { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px;}
        table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #1e293b; border-radius: 10px; overflow: hidden;}
        th, td { padding: 12px; border-bottom: 1px solid #334155; text-align: center;}
        th { background: #020617; color: #38bdf8; }
        .btn { padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; color: white; font-weight: bold;}
        .btn-green { background: #10b981; } .btn-red { background: #ef4444; } .btn-yellow { background: #fbbf24; color: #000; }
        input { padding: 8px; border-radius: 5px; border: 1px solid #334155; background: #0f172a; color: #fff;}
    </style>
</head>
<body>
    <h1 style="text-align:center;">👑 لوحة تحكم الإدارة العليا (Master Pro)</h1>
    
    <div class="card">
        <h3>➕ إضافة حساب إداري جديد</h3>
        <form action="/master_add_user" method="post" style="display:flex; gap:10px; justify-content:center;">
            <input type="text" name="new_username" placeholder="اسم المستخدم" required>
            <input type="password" name="new_password" placeholder="كلمة المرور" required>
            <button type="submit" class="btn btn-green">إنشاء حساب</button>
        </form>
    </div>

    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3>👥 إدارة الحسابات الحالية</h3>
            <div>
                <form action="/master_global_action" method="post" style="display:inline-block;">
                    <button type="submit" name="action" value="pause_all" class="btn btn-yellow">⏸️ استراحة للجميع</button>
                    <button type="submit" name="action" value="stop_all" class="btn btn-red">🛑 إيقاف الجميع</button>
                </form>
            </div>
        </div>
        <table>
            <tr><th>المستخدم</th><th>الباسورد</th><th>الحالة</th><th>القسم</th><th>المنجز</th><th>الإجراءات السريعة</th></tr>
            {% for u, d in users.items() %}
            <tr>
                <td><b>{{ u }}</b></td>
                <td>{{ d.password }}</td>
                <td style="color: {% if d.status == 'running' %}#10b981{% elif d.status == 'paused' %}#fbbf24{% else %}#ef4444{% endif %};">
                    {{ 'نشط' if d.status == 'running' else 'استراحة' if d.status == 'paused' else 'متوقف' }}
                </td>
                <td>{{ d.ticket_filter }}</td>
                <td>{{ d.count }} / {{ d.max_tickets }}</td>
                <td>
                    <form action="/master_user_action" method="post" style="display:flex; gap:5px; justify-content:center;">
                        <input type="hidden" name="target_user" value="{{ u }}">
                        {% if d.status == 'running' %}
                            <button type="submit" name="action" value="pause" class="btn btn-yellow">⏸️</button>
                        {% elif d.status == 'paused' %}
                            <button type="submit" name="action" value="resume" class="btn btn-green">▶️</button>
                        {% endif %}
                        <button type="submit" name="action" value="stop" class="btn btn-red">🛑</button>
                        <a href="/master_report/{{ u }}" class="btn btn-secondary" style="background:#475569; text-decoration:none;">📄 تقرير</a>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

# ================= مسارات الفلاسك (Flask Routes) =================

@app.route('/manifest.json')
def manifest():
    return app.response_class(response=MANIFEST_JSON, mimetype='application/json')

@app.route('/')
def index():
    return render_template_string(LANDING_HTML)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in user_sessions and user_sessions[username]["password"] == password:
            session['user'] = username
            if not user_sessions[username]["token"]: return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user_sessions[session['user']]["token"] = request.form.get('token').strip()
        save_db(session['user'])
        return redirect(url_for('panel'))
    return render_template_string("""<body style="background:#030712; color:#fff; text-align:center; display:flex; justify-content:center; align-items:center; height:100vh;"><form method="POST"><textarea name="token" required style="width:300px; height:80px; padding:10px; border-radius:10px;"></textarea><br><button type="submit" style="padding:10px; width:320px; background:#3b82f6; border:none; border-radius:10px; color:#fff; margin-top:10px; font-weight:bold;">تأمين التوكن 🔒</button></form></body>""")

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]: return redirect(url_for('login'))
    usr = session['user']
    d = user_sessions[usr]
    theme_key = d.get("theme", "cyber_red")
    theme_data = THEMES.get(theme_key, THEMES["cyber_red"])
    
    return render_template_string(PANEL_HTML, username=usr, max_tickets=d["max_tickets"], count=d["count"], speed=d["speed"], 
                                  message=d["message"], theme=theme_key, themes=THEMES, theme_data=theme_data,
                                  ticket_filter=d.get("ticket_filter", "all"),
                                  status=d["status"], total_lifetime=d["total_lifetime"], logs=d["logs"])

@app.route('/api/status')
def api_status():
    if 'user' not in session: return json.dumps({"error": "unauth"})
    u = session['user']
    d = user_sessions[u]
    return json.dumps({
        "count": d["count"], "max_tickets": d["max_tickets"], "speed": d["speed"], 
        "status": d["status"], "logs": d["logs"], "total": d["total_lifetime"], 
        "history": d.get("claimed_history", [])
    })

@app.route('/api/chat/<ch_id>')
def api_chat(ch_id):
    if 'user' not in session: return json.dumps({"error": "unauth"})
    u = session['user']
    try:
        res = requests.get(f"{API}/{ch_id}/messages?limit=15", headers=get_secure_headers(user_sessions[u]["token"]), timeout=3)
        if res.status_code == 200:
            msgs = res.json()
            msgs.reverse()
            return json.dumps([{"author": m["author"]["username"], "content": m["content"], "bot": m["author"].get("bot", False)} for m in msgs])
    except: pass
    return json.dumps([])

@app.route('/set_status', methods=['POST'])
def set_status():
    if 'user' in session:
        usr = session['user']
        new_status = request.form.get('new_status')
        if new_status in ["running", "paused", "stopped"]:
            old_status = user_sessions[usr]["status"]
            user_sessions[usr]["status"] = new_status
            if new_status == "running" and old_status == "stopped" and user_sessions[usr]["token"]:
                if user_sessions[usr]["count"] >= user_sessions[usr]["max_tickets"]: user_sessions[usr]["count"] = 0
                threading.Thread(target=run_discord_bot, args=(usr,), daemon=True).start()
    return redirect(url_for('panel'))

@app.route('/update_main', methods=['POST'])
def update_main():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["message"] = request.form.get('custom_msg', '').strip()
        try:
            user_sessions[usr]["max_tickets"] = int(request.form.get('max_tickets', 10))
            user_sessions[usr]["speed"] = float(request.form.get('custom_speed', 1.1))
        except: pass
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/update_sidebar', methods=['POST'])
def update_sidebar():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["theme"] = request.form.get('theme', 'cyber_red')
        user_sessions[usr]["ticket_filter"] = request.form.get('ticket_filter', 'all')
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/reset_all', methods=['POST'])
def reset_all():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["count"] = 0
        user_sessions[usr]["logs"] = []
        user_sessions[usr]["claimed_history"] = []
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/master', methods=['GET', 'POST'])
def master():
    if request.method == 'POST':
        if request.form.get('pass') == MASTER_PASSWORD: session['master'] = True
    if not session.get('master'):
        return """<body style="background:#000; text-align:center; padding-top:100px;"><form method="POST"><input type="password" name="pass" placeholder="Master Password" style="padding:10px;"><button style="padding:10px; background:#3b82f6; color:#fff; border:none;">Login</button></form></body>"""
    return render_template_string(MASTER_HTML, users=user_sessions)

@app.route('/master_add_user', methods=['POST'])
def master_add_user():
    if session.get('master'):
        n_user = request.form.get('new_username').strip()
        n_pass = request.form.get('new_password').strip()
        if n_user and n_user not in user_sessions:
            user_sessions[n_user] = create_default_session_data(n_user, n_pass)
            save_db(n_user)
    return redirect(url_for('master'))

@app.route('/master_global_action', methods=['POST'])
def master_global_action():
    if session.get('master'):
        action = request.form.get('action')
        for u, d in user_sessions.items():
            if action == "pause_all" and d["status"] == "running": d["status"] = "paused"
            elif action == "stop_all": d["status"] = "stopped"
    return redirect(url_for('master'))

@app.route('/master_user_action', methods=['POST'])
def master_user_action():
    if session.get('master'):
        target = request.form.get('target_user')
        action = request.form.get('action')
        if target in user_sessions:
            if action == "pause" and user_sessions[target]["status"] == "running": user_sessions[target]["status"] = "paused"
            elif action == "resume" and user_sessions[target]["status"] == "paused": user_sessions[target]["status"] = "running"
            elif action == "stop": user_sessions[target]["status"] = "stopped"
    return redirect(url_for('master'))

@app.route('/master_report/<username>')
def master_report(username):
    if not session.get('master') or username not in user_sessions: return "Access Denied"
    d = user_sessions[username]
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Username', 'Password', 'Status', 'Filter', 'Daily Count', 'Total Lifetime'])
    cw.writerow([username, d["password"], d["status"], d["ticket_filter"], d["count"], d["total_lifetime"]])
    cw.writerow([])
    cw.writerow(['Recent Logs'])
    for log in d["logs"]: cw.writerow([re.sub('<[^<]+>', '', log)])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=Report_{username}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
