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
app.secret_key = "MR_ELITE_SECRET_CORE_ULTIMATE"

INITIAL_USERS = {
    "Saif": "12345678", "Marshall": "oopp0099", "Youssef": "oopp009987",
    "Kara": "oopp00998", "isso": "12345678", "Azmy": "12345678", "Dark": "123456789"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"
SAIF_ALERT_CHANNEL = "1545711547169513483"

CATEGORY_IDS = {
    "administrative": "1353444395575414844",
    "players": "1353444390387060736",
    "factions": "1353444400679747665"
}

THEMES = {
    "cyber_red": {"name": "أحمر Cyberpunk", "prim": "#dc2626", "sec": "#7f1d1d", "bg": "#170505"},
    "lynwood": {"name": "أزرق Lynwood Police", "prim": "#2563eb", "sec": "#1e3a8a", "bg": "#0a0f1d"},
    "neon_purple": {"name": "بنفسجي Neon", "prim": "#9333ea", "sec": "#4c1d95", "bg": "#0f0518"},
    "stealth_dark": {"name": "أسود شبحي", "prim": "#475569", "sec": "#1e293b", "bg": "#020617"}
}

global_settings = {"min_speed": 1.0, "broadcast_msg": "", "broadcast_id": 0}

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
        "message": f"أهلاً بك، معك {uname} الإدارة العليا. كيف أخدمك؟",
        "ticket_filter": "all", "speed": 1.1, "max_tickets": 10, "count": 0, "total_lifetime": 0,
        "logs": [], "is_suspended": 0, "compact_mode": 0, "last_sent_text": "", "last_sent_time": 0,
        "active_tickets": set(), "lock": threading.Lock(), "theme": "cyber_red", "claimed_history": [],
        "hidden_tickets": set(), "currently_viewing": "لا شيء"
    }

def init_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY, password TEXT, token TEXT, message TEXT, 
                      ticket_filter TEXT, speed REAL, max_tickets INTEGER,
                      count INTEGER, total_lifetime INTEGER, theme TEXT, is_suspended INTEGER DEFAULT 0, compact_mode INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ticket_logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, ticket_id TEXT, timestamp REAL)''')
        
        c.execute("PRAGMA table_info(users)")
        existing_cols = [col[1] for col in c.fetchall()]
        if "is_suspended" not in existing_cols: c.execute("ALTER TABLE users ADD COLUMN is_suspended INTEGER DEFAULT 0")
        if "compact_mode" not in existing_cols: c.execute("ALTER TABLE users ADD COLUMN compact_mode INTEGER DEFAULT 0")

        for uname, pwd in INITIAL_USERS.items():
            c.execute("SELECT username FROM users WHERE username=?", (uname,))
            if not c.fetchone():
                c.execute('''INSERT INTO users (username, password, token, message, ticket_filter, speed, max_tickets, count, total_lifetime, theme)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                             (uname, pwd, "", f"أهلاً بك، معك {uname} الإدارة العليا.", "all", 1.1, 10, 0, 0, "cyber_red"))
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
            if uname not in user_sessions: user_sessions[uname] = create_default_session_data(uname, row_dict.get("password", "12345678"))
            user_sessions[uname]["password"] = row_dict.get("password", "12345678")
            user_sessions[uname]["token"] = cipher(row_dict.get("token", ""), False)
            user_sessions[uname]["message"] = row_dict.get("message", "")
            user_sessions[uname]["ticket_filter"] = row_dict.get("ticket_filter", "all")
            user_sessions[uname]["speed"] = row_dict.get("speed", 1.1)
            user_sessions[uname]["max_tickets"] = row_dict.get("max_tickets", 10)
            user_sessions[uname]["count"] = row_dict.get("count", 0)
            user_sessions[uname]["total_lifetime"] = row_dict.get("total_lifetime", 0)
            user_sessions[uname]["theme"] = row_dict.get("theme", "cyber_red")
            user_sessions[uname]["is_suspended"] = row_dict.get("is_suspended", 0)
            user_sessions[uname]["compact_mode"] = row_dict.get("compact_mode", 0)

def save_db(uname):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        d = user_sessions[uname]
        enc_token = cipher(d["token"], True)
        c.execute("SELECT username FROM users WHERE username=?", (uname,))
        if not c.fetchone():
            c.execute('''INSERT INTO users (username, password, token, message, ticket_filter, speed, max_tickets, count, total_lifetime, theme, is_suspended, compact_mode)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                      (uname, d["password"], enc_token, d["message"], d["ticket_filter"], d["speed"], d["max_tickets"], d["count"], d["total_lifetime"], d.get("theme","cyber_red"), d["is_suspended"], d["compact_mode"]))
        else:
            c.execute('''UPDATE users SET password=?, token=?, message=?, ticket_filter=?, 
                         speed=?, max_tickets=?, count=?, total_lifetime=?, theme=?, is_suspended=?, compact_mode=? WHERE username=?''',
                      (d["password"], enc_token, d["message"], d["ticket_filter"], d["speed"], d["max_tickets"], d["count"], d["total_lifetime"], d.get("theme","cyber_red"), d["is_suspended"], d["compact_mode"], uname))
        conn.commit()
        conn.close()

def log_ticket(username, ticket_id):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO ticket_logs (username, ticket_id, timestamp) VALUES (?, ?, ?)", (username, ticket_id, time.time()))
        conn.commit()
        conn.close()

init_db()
load_db()

def get_secure_headers(token):
    build_num = random.randint(320000, 325000)
    props = {"os": "iOS", "browser": "Discord Client", "device": "iPhone 13, pro, max"}
    return {"Authorization": token.strip(), "Content-Type": "application/json", "User-Agent": "Discord/241.0 CFNetwork/1498.700.2 Darwin/23.4.0"}

def safe_post(username, url, payload, current_speed, is_claim=False):
    # رجعنا لنظام البوست القديم الصاروخي بدون تأخيرات إضافية
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
    # رجعنا لمنطق القنص القديم والمجرب للسرعة القصوى
    session_data = user_sessions[username]
    
    with session_data["lock"]:
        if session_data["status"] != "running" or session_data["is_suspended"]: return
        if session_data["count"] >= session_data["max_tickets"]:
            session_data["status"] = "stopped"
            return
            
        filter_mode = session_data.get("ticket_filter", "all")
        if filter_mode != "all" and str(parent_id) != str(CATEGORY_IDS.get(filter_mode)): return
        
        if ch_id in session_data["active_tickets"]: return
        session_data["active_tickets"].add(ch_id)
        
        session_data["count"] += 1
        session_data["total_lifetime"] += 1
        current_count = session_data["count"]
        max_lim = session_data["max_tickets"]

    current_speed = session_data["speed"]

    # الدوران العشوائي للرسائل (ميزة جديدة تم الحفاظ عليها)
    msg_list = [m.strip() for m in session_data["message"].split('||') if m.strip()]
    custom_msg = random.choice(msg_list) if msg_list else "استلمت التكت."
    
    now_ts = time.time()
    if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 2.0):
        custom_msg += "᠎" * random.randint(1, 2)
    session_data["last_sent_text"] = custom_msg
    session_data["last_sent_time"] = now_ts

    res = safe_post(username, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed, is_claim=True)
    
    with session_data["lock"]:
        if res and res.status_code in [200, 201]:
            log_ticket(username, ch_id)
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"✨ استلمت **#{name}** | <a href='{ticket_url}' target='_blank'>الرابط</a>"
            
            t_time = datetime.now().strftime("%I:%M %p")
            cat_type = "administrative" if str(parent_id) == CATEGORY_IDS["administrative"] else "players" if str(parent_id) == CATEGORY_IDS["players"] else "factions"
            session_data["claimed_history"].append({"id": ch_id, "name": name, "time": t_time, "cat": cat_type})
            if len(session_data["claimed_history"]) > 20: session_data["claimed_history"].pop(0)
            
            session_data["logs"].insert(0, f"{log_text} ({current_count}/{max_lim})")
            if len(session_data["logs"]) > 20: session_data["logs"].pop()
            save_db(username)
            
            if current_count >= max_lim:
                session_data["status"] = "stopped"
                session_data["logs"].insert(0, "🛑 تم بلوغ الحد الأقصى، توقف النظام.")
        else:
            session_data["count"] = max(0, session_data["count"] - 1)
            session_data["total_lifetime"] = max(0, session_data["total_lifetime"] - 1)
            session_data["logs"].insert(0, f"<span style='color: #ef4444;'>❌ تعذر استلام #{name}</span>")
            
        if ch_id in session_data["active_tickets"]: session_data["active_tickets"].remove(ch_id)

def run_discord_bot(username):
    d = user_sessions[username]
    token = d["token"]
    d["logs"].insert(0, "🚀 تم تفعيل النظام الكلاسيكي السريع جداً...")
    def on_message(ws, msg):
        if d["status"] == "stopped" or d["is_suspended"]: ws.close(); return
        if d["status"] == "paused": return
        try:
            raw = json.loads(msg)
            if raw.get("op") == 10: ws.send(json.dumps({"op": 1, "d": None}))
            if raw.get("t") == "CHANNEL_CREATE" and raw.get("d", {}).get("guild_id") == SERVER_ID:
                ch_id, name, parent_id = raw["d"]["id"], raw["d"]["name"], raw["d"].get("parent_id")
                if time.time() - (((int(ch_id) >> 22) + 1420070400000) / 1000.0) < 15:
                    threading.Thread(target=process_ticket, args=(username, ch_id, name, parent_id)).start()
        except: pass
    def on_open(ws): ws.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "iOS", "browser": "Discord Client"}, "intents": 1 | 512}}))
    while d["status"] in ["running", "paused"] and not d["is_suspended"]:
        try: websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_open=on_open, on_message=on_message).run_forever()
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

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/2202/2202112.png">
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
        
        <!-- واجهة الخزنة -->
        <div id="vault-view" style="display:none;">
            <div class="avatar" id="vault-avatar">M</div>
            <h2 id="vault-name" style="margin:5px 0 20px 0; color:#cbd5e1;">مرحباً مجدداً</h2>
            <p style="font-size:12px; color:#94a3b8; margin-bottom:15px;">أدخل رمز PIN السري</p>
            <input type="password" id="pin-input" maxlength="4" pattern="[0-9]*" inputmode="numeric" placeholder="••••">
            <div id="pin-error" class="error-msg">الرمز غير صحيح، حاول مجدداً</div>
            <button onclick="unlockVault()">فتح الخزنة 🔓</button>
            <a href="#" onclick="resetVault()" style="color:#ef4444; text-decoration:none; font-size:12px; display:block; margin-top:20px;">تسجيل الدخول بحساب آخر</a>
        </div>

        <!-- واجهة الدخول لأول مرة -->
        <div id="normal-view" style="display:none;">
            <h2 style="margin-top:0;">بوابة الدخول</h2>
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
        let vaultData = localStorage.getItem("mr_vault_v4");
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
            
            localStorage.setItem("mr_vault_v4", JSON.stringify({u: u, p: btoa(p), pin: pin}));
            document.getElementById("hidden-user").value = u;
            document.getElementById("hidden-pass").value = p;
            document.getElementById("hidden-form").submit();
        }

        function unlockVault() {
            let data = JSON.parse(localStorage.getItem("mr_vault_v4"));
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
            localStorage.removeItem("mr_vault_v4");
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
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/2202/2202112.png">
    <title>M.R Command Center</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=gg+sans:wght@400;600&display=swap'); 
        :root { --prim: {{ theme_data.prim }}; --sec: {{ theme_data.sec }}; --bg: {{ theme_data.bg }}; }
        body { background: var(--bg); color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 15px; padding-bottom: 60px; min-height: 100vh;}
        
        /* إضاءة الحواف السينمائية (Edge Lighting) */
        #edge-lighting { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 9999; opacity: 0; transition: opacity 0.3s, box-shadow 0.3s; }
        .edge-flash-admin { opacity: 1 !important; box-shadow: inset 0 0 50px rgba(239,68,68,0.9) !important; }
        .edge-flash-player { opacity: 1 !important; box-shadow: inset 0 0 50px rgba(59,130,246,0.9) !important; }
        .edge-flash-faction { opacity: 1 !important; box-shadow: inset 0 0 50px rgba(251,191,36,0.9) !important; }

        /* توفير البطارية */
        body.battery-saver * { animation: none !important; box-shadow: none !important; text-shadow: none !important; background-image: none !important; }
        
        /* الوضع المدمج */
        body.compact-mode .glass-card { padding: 15px; }
        body.compact-mode h1 { font-size: 16px; margin: 0;}
        body.compact-mode .btn { padding: 8px; font-size: 12px; }
        body.compact-mode input, body.compact-mode select { padding: 6px; font-size: 11px; margin-bottom: 5px;}
        body.compact-mode .chart-container { height: 90px; }
        body.compact-mode textarea { height: 40px; }
        
        .openbtn { font-size: 26px; cursor: pointer; background: rgba(0,0,0,0.6); color: white; border: 1px solid var(--prim); border-radius: 50%; width: 45px; height: 45px; position: fixed; top: 10px; left: 10px; z-index: 900; display: flex; align-items: center; justify-content: center;}
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; right: 0; background-color: rgba(10, 15, 29, 0.98); backdrop-filter: blur(15px); overflow-x: hidden; transition: 0.4s; padding-top: 50px; text-align: right; border-left: 1px solid rgba(255,255,255,0.1); }
        .sidebar-content { padding: 0 20px;}
        .sidebar .closebtn { position: absolute; top: 10px; right: 20px; font-size: 30px; color: #ef4444; text-decoration:none;}
        
        .glass-card { background: rgba(0, 0, 0, 0.6); max-width: 440px; width: 100%; padding: 26px; border-radius: 20px; border: 1px solid rgba(255,255,255, 0.1); margin: 0 auto 10px auto;}
        .badge-container { display: flex; gap: 5px; margin-bottom: 15px; }
        .glass-badge { flex: 1; background: rgba(0,0,0,0.5); padding: 8px; border-radius: 12px; font-size: 11px; border: 1px solid rgba(255,255,255,0.05);}
        .glass-badge b { color: var(--prim); font-size: 13px; display: block;}
        .chart-container { background: rgba(0,0,0,0.4); border-radius: 14px; padding: 10px; height: 130px; margin-bottom: 10px;}

        .action-row { display: flex; gap: 8px; margin-bottom: 15px; }
        .btn { flex: 1; padding: 12px; font-weight: 800; border: none; border-radius: 12px; cursor: pointer; color: #fff; font-family: 'Cairo'; width:100%; box-sizing:border-box;}
        .btn-start { background: linear-gradient(135deg, #059669, #047857); }
        .btn-pause { background: linear-gradient(135deg, #fbbf24, #d97706); color: #000;}
        .btn-stop { background: linear-gradient(135deg, #dc2626, #991b1b); }
        .btn-secondary { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); margin-top:5px;}
        
        input, select, textarea { width: 100%; padding: 10px; background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 10px; box-sizing: border-box; font-family: 'Cairo'; margin-bottom: 10px;}
        
        /* شاشة ديسكورد المستنسخة */
        .ghost-panel { background: #313338; max-width: 440px; width: 100%; border-radius: 15px; margin: 10px auto; display: flex; flex-direction: column; height: 500px; overflow: hidden; position: relative;}
        .pull-indicator { position: absolute; top: -30px; left: 0; width: 100%; text-align: center; color: #949ba4; font-size: 12px; transition: 0.2s;}
        .ghost-header { background: #2b2d31; color: #f2f3f5; font-weight: bold; padding: 10px; font-size: 14px; text-align: right; z-index: 10;}
        .ticket-list { display: flex; padding: 10px; gap: 5px; background: #2b2d31; overflow-x: auto; touch-action: pan-y; }
        .tkt-btn { background: #2b2d31; border: none; color: #949ba4; padding: 6px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; white-space: nowrap; transition: transform 0.2s;}
        .tkt-btn.active { background: #404249; color: #f2f3f5; }
        .chat-box { flex: 1; padding: 10px 0; overflow-y: auto; display: flex; flex-direction: column; gap: 2px;}
        .discord-msg { display: flex; padding: 5px 10px; flex-direction: row-reverse; text-align: right;}
        .discord-avatar { width: 35px; height: 35px; border-radius: 50%; margin-right: 10px; background: #5865F2; display: flex; align-items: center; justify-content: center; font-weight: bold;}
        .discord-text { color: #dbdee1; font-size: 14px; line-height: 1.3;}

        /* نافذة الإحصائيات (Modal) */
        .modal { display: none; position: fixed; z-index: 9999; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; }
        .modal-content { background: #1e293b; padding: 20px; border-radius: 15px; text-align: center; width: 80%; border: 1px solid #3b82f6;}
        
        .log-box { background: #000; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 10px; height: 60px; overflow-y: auto; text-align: right; font-size: 11px; color: #94a3b8; margin-top: 5px; }
    </style>
</head>
<body class="{% if compact_mode %}compact-mode{% endif %}">
    
    <div id="edge-lighting"></div>
    <button class="openbtn" onclick="openNav()">=</button>

    <div id="mySidebar" class="sidebar">
        <a href="javascript:void(0)" class="closebtn" onclick="closeNav()">&times;</a>
        <div class="sidebar-content">
            <button onclick="showStats()" class="btn btn-start" style="margin-bottom:15px;">📊 إحصائياتي الشخصية</button>
            <button onclick="toggleGhost()" class="btn btn-secondary" style="margin-bottom:15px;">👁️ إظهار/إخفاء المراقبة</button>
            <button onclick="requestNotificationPermission()" class="btn btn-secondary" style="margin-bottom:15px; background: #8b5cf6;">🔔 إشعارات الجوال (Push)</button>
            
            <form action="/update_sidebar" method="post">
                <select name="theme">
                    {% for k, v in themes.items() %}<option value="{{ k }}" {% if theme == k %}selected{% endif %}>{{ v.name }}</option>{% endfor %}
                </select>
                <select name="ticket_filter">
                    <option value="all" {% if ticket_filter == 'all' %}selected{% endif %}>🌐 جميع التكتات</option>
                    <option value="administrative" {% if ticket_filter == 'administrative' %}selected{% endif %}>🛡️ شكاوى إدارية</option>
                </select>
                <div style="text-align:right; margin-bottom:10px; font-size:12px; color:#94a3b8;">
                    <input type="checkbox" name="compact_mode" style="width:auto; display:inline;" {% if compact_mode %}checked{% endif %}> الوضع المدمج (للموبايل)
                </div>
                <button type="submit" class="btn btn-secondary" style="background: var(--prim); color:#fff;">حفظ التغييرات</button>
            </form>
            <form action="/token" method="get"><button class="btn btn-secondary">🔑 تحديث التوكن</button></form>
            <a href="/logout" class="btn btn-stop" style="margin-top:20px; text-decoration:none; display:block;">تسجيل خروج</a>
        </div>
    </div>

    <!-- نافذة الإحصائيات -->
    <div id="statsModal" class="modal">
        <div class="modal-content">
            <h3 style="color:#3b82f6; margin-top:0;">إحصائيات القنص</h3>
            <div style="display:flex; justify-content:space-around; margin:20px 0;">
                <div><b style="color:#10b981; font-size:20px;" id="stat_day">0</b><br><span style="font-size:12px;">اليوم</span></div>
                <div><b style="color:#fbbf24; font-size:20px;" id="stat_week">0</b><br><span style="font-size:12px;">أسبوع</span></div>
                <div><b style="color:#ef4444; font-size:20px;" id="stat_month">0</b><br><span style="font-size:12px;">شهر</span></div>
            </div>
            <button onclick="document.getElementById('statsModal').style.display='none'" class="btn btn-secondary">إغلاق</button>
        </div>
    </div>

    <div class="main-content">
        <div class="glass-card">
            <h1>M.R COMMAND CENTER</h1>
            <div class="user-tag">👤 {{ username }}</div>
            
            <div class="badge-container">
                <div class="glass-badge">الهدف <b id="count_disp">{{ count }}/{{ max_tickets }}</b></div>
                <div class="glass-badge">السرعة <b>{{ speed }}s</b></div>
                <div class="glass-badge">الوضع <b id="status_disp" style="color: {% if status == 'running' %}#10b981{% elif status == 'paused' %}#fbbf24{% else %}#ef4444{% endif %};">
                    {% if status == 'running' %}نشط 🚀{% elif status == 'paused' %}استراحة ⏸️{% else %}متوقف 🛑{% endif %}
                </b></div>
            </div>

            <div class="chart-container"><canvas id="progressChart"></canvas></div>
            
            <form action="/set_status" method="post" class="action-row">
                {% if status == 'stopped' %}
                    <button type="submit" name="new_status" value="running" class="btn btn-start">تشغيل النظام 🚀</button>
                {% else %}
                    {% if status == 'running' %}<button type="submit" name="new_status" value="paused" class="btn btn-pause">استراحة تكتيكية ⏸️</button>
                    {% else %}<button type="submit" name="new_status" value="running" class="btn btn-start">استئناف ▶️</button>{% endif %}
                    <button type="submit" name="new_status" value="stopped" class="btn btn-stop" style="flex: 0.5;">إيقاف 🛑</button>
                {% endif %}
            </form>

            <form action="/update_main" method="post">
                <div style="display:flex; gap:8px;">
                    <input type="number" name="max_tickets" value="{{ max_tickets }}" placeholder="التارجت">
                    <input type="number" step="0.01" name="custom_speed" value="{{ speed }}" placeholder="السرعة">
                </div>
                <textarea name="custom_msg" placeholder="اكتب رسائلك وافصل بينها بـ || للدوران العشوائي">{{ message }}</textarea>
                <button type="submit" class="btn btn-secondary">حفظ التغييرات السريعة 💾</button>
            </form>
            
            <div class="log-box" id="log_box">{% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div>النظام جاهز...</div>{% endfor %}</div>
        </div>

        <!-- شاشة ديسكورد المستنسخة -->
        <div class="ghost-panel" id="ghost_panel">
            <div class="pull-indicator" id="pullIndicator">اسحب للأسفل للتحديث ↓</div>
            <div class="ghost-header">Discord Live</div>
            <div class="ticket-list" id="ticket_list"></div>
            <div class="chat-box" id="chat_box"><div style="color:#949ba4; text-align:center; margin-top:40%; font-weight:600;">يرجى تحديد تذكرة للمراقبة...</div></div>
        </div>
    </div>

    <script>
        function openNav() { document.getElementById("mySidebar").style.width = "260px"; }
        function closeNav() { document.getElementById("mySidebar").style.width = "0"; }
        
        // إخفاء/إظهار شاشة المراقبة
        function toggleGhost() { 
            var p = document.getElementById("ghost_panel");
            p.style.display = (p.style.display === "none" || p.style.display === "") ? "flex" : "none";
            closeNav();
        }

        // الإشعارات
        function requestNotificationPermission() {
            if ("Notification" in window) {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") alert("✅ تم تفعيل إشعارات الجوال بنجاح!");
                    else alert("❌ يرجى السماح بالإشعارات من إعدادات المتصفح.");
                });
            } else { alert("جهازك لا يدعم الإشعارات المنبثقة."); }
            closeNav();
        }

        // توفير البطارية
        if(navigator.getBattery) {
            navigator.getBattery().then(function(b) {
                if(b.level <= 0.20 && !b.charging) document.body.classList.add('battery-saver');
                b.addEventListener('levelchange', function() {
                    if(b.level <= 0.20 && !b.charging) document.body.classList.add('battery-saver');
                    else document.body.classList.remove('battery-saver');
                });
            });
        }

        // السحب للتحديث (Pull-to-refresh)
        let touchStartY = 0;
        const ghostPanel = document.getElementById('ghost_panel');
        const pullInd = document.getElementById('pullIndicator');
        ghostPanel.addEventListener('touchstart', e => { touchStartY = e.touches[0].clientY; }, {passive: true});
        ghostPanel.addEventListener('touchmove', e => {
            if(ghostPanel.scrollTop === 0 && (e.touches[0].clientY - touchStartY) > 40) {
                pullInd.style.top = '10px'; pullInd.innerText = 'أفلت للتحديث ↻';
            }
        }, {passive: true});
        ghostPanel.addEventListener('touchend', e => {
            if(pullInd.style.top === '10px') {
                pullInd.innerText = 'جاري التحديث...';
                fetchChat().then(() => { pullInd.style.top = '-30px'; pullInd.innerText = 'اسحب للأسفل للتحديث ↓'; });
            }
        });

        // السحب للحذف (Swipe-to-Dismiss)
        let btnStartX = null;
        document.getElementById('ticket_list').addEventListener('touchstart', e => { if(e.target.classList.contains('tkt-btn')) btnStartX = e.touches[0].clientX; }, {passive: true});
        document.getElementById('ticket_list').addEventListener('touchmove', e => {
            if(!btnStartX || !e.target.classList.contains('tkt-btn')) return;
            let diff = btnStartX - e.touches[0].clientX;
            if(diff > 10) e.target.style.transform = `translateX(-${diff}px)`;
        }, {passive: true});
        document.getElementById('ticket_list').addEventListener('touchend', e => {
            if(!btnStartX || !e.target.classList.contains('tkt-btn')) return;
            let diff = btnStartX - e.changedTouches[0].clientX;
            if(diff > 40) {
                let id = e.target.id.split('_')[1];
                fetch('/api/hide_ticket/' + id, {method: 'POST'});
                e.target.style.display = 'none';
            } else { e.target.style.transform = 'translateX(0)'; }
            btnStartX = null;
        });

        var ctx = document.getElementById('progressChart').getContext('2d');
        var myChart = new Chart(ctx, { type: 'doughnut', data: { labels: ['المنجز', 'المتبقي'], datasets: [{ data: [{{ count }}, {{ max_tickets - count if max_tickets - count > 0 else 0 }}], backgroundColor: ['{{ theme_data.prim }}', 'rgba(255,255,255,0.05)'], borderWidth: 0 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, cutout: '75%' } });

        let currentActiveTicket = null;
        let lastBroadcastId = 0;
        let lastCount = {{ count }};

        async function fetchChat() {
            if(!currentActiveTicket) return;
            try {
                let res = await fetch('/api/chat/' + currentActiveTicket);
                let msgs = await res.json();
                if(msgs.error) return;
                let chatHtml = '';
                msgs.forEach(m => {
                    let initial = m.author.charAt(0).toUpperCase();
                    chatHtml += `<div class="discord-msg"><div class="discord-avatar">${initial}</div><div style="flex:1"><b style="color:#f2f3f5; font-size:13px;">${m.author}</b><div class="discord-text">${m.content}</div></div></div>`;
                });
                document.getElementById('chat_box').innerHTML = chatHtml || '<div style="color:#949ba4; text-align:center; margin-top:40%;">لا توجد رسائل</div>';
            } catch(e) {}
        }

        function loadChat(ch_id) {
            currentActiveTicket = ch_id;
            fetch('/api/viewing/' + ch_id);
            document.querySelectorAll('.tkt-btn').forEach(b => b.classList.remove('active'));
            let btn = document.getElementById('btn_' + ch_id);
            if(btn) btn.classList.add('active');
            fetchChat();
        }

        async function showStats() {
            let res = await fetch('/api/my_stats');
            let data = await res.json();
            document.getElementById('stat_day').innerText = data.daily;
            document.getElementById('stat_week').innerText = data.weekly;
            document.getElementById('stat_month').innerText = data.monthly;
            document.getElementById('statsModal').style.display = 'flex';
            closeNav();
        }

        function triggerEdgeLighting(cat) {
            let el = document.getElementById('edge-lighting');
            el.className = '';
            if(cat === 'administrative') el.classList.add('edge-flash-admin');
            else if(cat === 'players') el.classList.add('edge-flash-player');
            else el.classList.add('edge-flash-faction');
            setTimeout(() => { el.className = ''; }, 2500);
        }

        setInterval(async () => {
            try {
                let res = await fetch('/api/status');
                let data = await res.json();
                
                if(data.is_suspended) window.location.href = '/logout';
                if(data.broadcast_id > lastBroadcastId && data.broadcast_msg !== "") { alert("📢 " + data.broadcast_msg); lastBroadcastId = data.broadcast_id; }

                if (data.count > lastCount) {
                    let newTicket = data.history[data.history.length - 1];
                    if(newTicket) {
                        triggerEdgeLighting(newTicket.cat);
                        if ("Notification" in window && Notification.permission === "granted") {
                            new Notification("M.R Command Center 🚀", { body: "تم قنص تكت جديد: #" + newTicket.name, icon: "https://cdn-icons-png.flaticon.com/512/2202/2202112.png" });
                        }
                    }
                    lastCount = data.count;
                } else if (data.count < lastCount) { lastCount = data.count; }

                // شريط الحالة التفاعلي
                document.title = `🚀 ${data.count}/${data.max_tickets} | M.R System`;

                document.getElementById('count_disp').innerText = data.count + '/' + data.max_tickets;
                
                let logHtml = '';
                data.logs.forEach(l => { logHtml += '<div>• ' + l + '</div>'; });
                document.getElementById('log_box').innerHTML = logHtml || '<div>النظام جاهز...</div>';
                
                myChart.data.datasets[0].data = [data.count, data.max_tickets - data.count > 0 ? data.max_tickets - data.count : 0];
                myChart.update();

                let tktsHtml = '';
                data.history.forEach(t => {
                    let activeCls = (currentActiveTicket == t.id) ? 'active' : '';
                    tktsHtml += `<button id="btn_${t.id}" class="tkt-btn ${activeCls}" onclick="loadChat('${t.id}')">#${t.name}</button>`;
                });
                document.getElementById('ticket_list').innerHTML = tktsHtml;
            } catch(e) {}
        }, 2000); 
    </script>
</body>
</html>
"""

MASTER_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Master Pro | القيادة العليا</title>
    <style>
        body { background: #020617; color: #f8fafc; font-family: sans-serif; padding: 20px;}
        .card { background: #0f172a; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #1e293b;}
        table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #1e293b; border-radius: 10px; overflow: hidden;}
        th, td { padding: 12px; border-bottom: 1px solid #334155; text-align: center; font-size:14px;}
        th { background: #020617; color: #38bdf8; }
        .btn { padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; color: white; font-weight: bold;}
        .btn-red { background: #ef4444; } .btn-yellow { background: #fbbf24; color: #000; } .btn-green { background: #10b981; }
        input { padding: 8px; border-radius: 5px; border: 1px solid #334155; background: #020617; color: #fff;}
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px;}
    </style>
</head>
<body>
    <h1 style="text-align:center; color:#38bdf8;">👑 لوحة تحكم الإدارة العليا (Master Pro)</h1>
    
    <div class="grid">
        <div class="card">
            <h3>📢 إرسال إعلان للفريق (Broadcast)</h3>
            <form action="/master_settings" method="post" style="display:flex; gap:10px;">
                <input type="text" name="broadcast" placeholder="اكتب الإعلان ليظهر كـ منبثق للجميع..." style="flex:1;" required>
                <button type="submit" class="btn btn-yellow">إرسال 🚀</button>
            </form>
            <hr style="border-color:#334155; margin:15px 0;">
            <h3>⏱️ مقيّد السرعة (Speed Limit)</h3>
            <form action="/master_settings" method="post" style="display:flex; gap:10px;">
                <input type="number" step="0.1" name="min_speed" value="{{ min_speed }}" placeholder="الحد الأدنى للسرعة">
                <button type="submit" class="btn btn-red">تطبيق القيد 🔒</button>
            </form>
        </div>

        <div class="card">
            <h3>➕ إضافة إداري جديد</h3>
            <form action="/master_add_user" method="post" style="display:flex; gap:10px; flex-direction:column;">
                <input type="text" name="new_username" placeholder="اسم المستخدم (مثال: Ali)" required>
                <input type="text" name="new_password" placeholder="كلمة المرور" required>
                <button type="submit" class="btn btn-green">إنشاء الحساب 👤</button>
            </form>
        </div>
    </div>

    <div class="card">
        <h3>👥 إدارة الفريق والبث المباشر (Spectate)</h3>
        <table>
            <tr><th>المستخدم</th><th>الباسورد</th><th>الحالة</th><th>يقرأ الآن (Live 👁️)</th><th>المنجز</th><th>الإجراءات السريعة</th></tr>
            {% for u, d in users.items() %}
            <tr>
                <td><b>{{ u }}</b></td>
                <td>{{ d.password }}</td>
                <td style="color: {% if d.is_suspended %}#ef4444{% elif d.status == 'running' %}#10b981{% else %}#fbbf24{% endif %};">
                    {{ 'مجمد ❄️' if d.is_suspended else 'نشط 🚀' if d.status == 'running' else 'استراحة ⏸️' if d.status == 'paused' else 'متوقف 🛑' }}
                </td>
                <td style="color:#38bdf8;">{{ d.currently_viewing }}</td>
                <td>{{ d.count }}</td>
                <td>
                    <form action="/master_user_action" method="post" style="display:flex; gap:5px; justify-content:center;">
                        <input type="hidden" name="target_user" value="{{ u }}">
                        {% if not d.is_suspended %}
                            {% if d.status == 'running' %}<button type="submit" name="action" value="pause" class="btn btn-yellow">⏸️</button>{% endif %}
                            <button type="submit" name="action" value="stop" class="btn btn-red">🛑</button>
                            <button type="submit" name="action" value="suspend" class="btn" style="background:#475569;">تجميد ❄️</button>
                        {% else %}
                            <button type="submit" name="action" value="unsuspend" class="btn btn-green">فك التجميد 🔥</button>
                        {% endif %}
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <script>setTimeout(() => location.reload(), 10000);</script>
</body>
</html>
"""

# ================= مسارات الفلاسك (Flask Routes) =================

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # الدخول كمدير عام (Master)
        if username == "Marshall" and password == "oopp00998":
            session['master'] = True
            return redirect(url_for('master'))
            
        if username in user_sessions and user_sessions[username]["password"] == password:
            if user_sessions[username]["is_suspended"]: 
                return render_template_string(LOGIN_HTML, error="حسابك مجمد من قبل الإدارة العليا ❄️")
            session['user'] = username
            if not user_sessions[username]["token"]: 
                return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
            
        return render_template_string(LOGIN_HTML, error="بيانات الدخول غير صحيحة")
    return render_template_string(LOGIN_HTML)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user_sessions[session['user']]["token"] = request.form.get('token').strip()
        save_db(session['user'])
        return redirect(url_for('panel'))
    return render_template_string("""<body style="background:#030712; text-align:center; padding-top:100px;"><form method="POST"><textarea name="token" required style="width:300px; height:80px; padding:10px; border-radius:10px; font-family:monospace;"></textarea><br><button style="padding:12px; width:320px; background:#3b82f6; color:#fff; border:none; margin-top:10px; border-radius:10px; font-weight:bold; cursor:pointer;">حفظ التوكن وتأمين الحساب 🔒</button></form></body>""")

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect(url_for('login'))
    usr = session['user']
    d = user_sessions[usr]
    if d["is_suspended"]: return redirect(url_for('logout'))
    theme_key = d.get("theme", "cyber_red")
    return render_template_string(PANEL_HTML, username=usr, max_tickets=d["max_tickets"], count=d["count"], speed=d["speed"], message=d["message"], theme=theme_key, themes=THEMES, theme_data=THEMES[theme_key], ticket_filter=d["ticket_filter"], status=d["status"], compact_mode=d["compact_mode"], logs=d["logs"])

@app.route('/api/status')
def api_status():
    if 'user' not in session: return json.dumps({"error": "unauth"})
    u = session['user']
    d = user_sessions[u]
    visible_history = [t for t in d["claimed_history"] if t["id"] not in d.get("hidden_tickets", set())]
    return json.dumps({
        "count": d["count"], "max_tickets": d["max_tickets"], "speed": d["speed"], 
        "status": d["status"], "is_suspended": d["is_suspended"], "history": visible_history, 
        "broadcast_msg": global_settings["broadcast_msg"], "broadcast_id": global_settings["broadcast_id"],
        "logs": d["logs"]
    })

@app.route('/api/viewing/<ch_id>')
def api_viewing(ch_id):
    if 'user' in session: 
        user_sessions[session['user']]["currently_viewing"] = f"تكت #{ch_id[-4:]}"
    return "ok"

@app.route('/api/hide_ticket/<ch_id>', methods=['POST'])
def hide_ticket(ch_id):
    if 'user' in session: 
        user_sessions[session['user']]["hidden_tickets"].add(ch_id)
    return "ok"

@app.route('/api/my_stats')
def api_my_stats():
    if 'user' not in session: return jsonify({"error": "unauth"})
    usr = session['user']
    now = time.time()
    day_ago, week_ago, month_ago = now - 86400, now - (86400*7), now - (86400*30)
    
    with db_lock:
        c = sqlite3.connect('elite_system.db', check_same_thread=False).cursor()
        c.execute("SELECT COUNT(*) FROM ticket_logs WHERE username=? AND timestamp > ?", (usr, day_ago))
        d = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM ticket_logs WHERE username=? AND timestamp > ?", (usr, week_ago))
        w = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM ticket_logs WHERE username=? AND timestamp > ?", (usr, month_ago))
        m = c.fetchone()[0]
    return jsonify({"daily": d, "weekly": w, "monthly": m})

@app.route('/api/chat/<ch_id>')
def api_chat(ch_id):
    if 'user' not in session: return json.dumps({"error": "unauth"})
    try:
        res = requests.get(f"{API}/{ch_id}/messages?limit=15", headers=get_secure_headers(user_sessions[session['user']]["token"]), timeout=3)
        if res.status_code == 200:
            msgs = res.json()
            msgs.reverse()
            return json.dumps([{"author": m["author"]["username"], "content": m["content"]} for m in msgs])
    except: pass
    return json.dumps([])

@app.route('/set_status', methods=['POST'])
def set_status():
    if 'user' in session:
        usr = session['user']
        new_status = request.form.get('new_status')
        if new_status in ["running", "paused", "stopped"] and not user_sessions[usr]["is_suspended"]:
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
            user_sessions[usr]["speed"] = max(float(request.form.get('custom_speed', 1.1)), global_settings["min_speed"])
        except: pass
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/update_sidebar', methods=['POST'])
def update_sidebar():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["theme"] = request.form.get('theme', 'cyber_red')
        user_sessions[usr]["ticket_filter"] = request.form.get('ticket_filter', 'all')
        user_sessions[usr]["compact_mode"] = 1 if request.form.get('compact_mode') else 0
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('master', None)
    return redirect(url_for('login'))

@app.route('/master')
def master():
    if not session.get('master'): return redirect(url_for('login'))
    return render_template_string(MASTER_HTML, users=user_sessions, min_speed=global_settings["min_speed"])

@app.route('/master_settings', methods=['POST'])
def master_settings():
    if session.get('master'):
        if 'broadcast' in request.form:
            global_settings["broadcast_msg"] = request.form.get('broadcast')
            global_settings["broadcast_id"] += 1
        if 'min_speed' in request.form:
            try: global_settings["min_speed"] = float(request.form.get('min_speed'))
            except: pass
    return redirect(url_for('master'))

@app.route('/master_add_user', methods=['POST'])
def master_add_user():
    if session.get('master'):
        n_user = request.form.get('new_username').strip()
        n_pass = request.form.get('new_password').strip()
        if n_user and n_user not in user_sessions:
            user_sessions[n_user] = create_default_session_data(n_user, n_pass)
            save_db(n_user)
    return redirect(url_for('master'))

@app.route('/master_user_action', methods=['POST'])
def master_user_action():
    if session.get('master'):
        target = request.form.get('target_user')
        action = request.form.get('action')
        if target in user_sessions:
            if action == "pause": user_sessions[target]["status"] = "paused"
            elif action == "stop": user_sessions[target]["status"] = "stopped"
            elif action == "suspend": 
                user_sessions[target]["is_suspended"] = 1
                user_sessions[target]["status"] = "stopped"
                save_db(target)
            elif action == "unsuspend": 
                user_sessions[target]["is_suspended"] = 0
                save_db(target)
    return redirect(url_for('master'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
