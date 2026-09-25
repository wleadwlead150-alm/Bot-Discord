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
from io import StringIO
from flask import Flask, render_template_string, request, redirect, url_for, session, make_response

app = Flask(__name__)
app.secret_key = "MR_ELITE_SECRET_CORE_V99"

USERS = {
    "Saif": "12345678",
    "Marshall": "oopp0099",
    "Youssef": "oopp009987",
    "Kara": "oopp00998",
    "isso": "12345678",
    "Azmy": "12345678"
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
    "lynwood": {"name": "أزرق Lynwood Police", "prim": "#2563eb", "sec": "#1e3a8a", "bg": "#0a0f1d"},
    "cyber_red": {"name": "أحمر Cyberpunk", "prim": "#dc2626", "sec": "#7f1d1d", "bg": "#170505"},
    "neon_purple": {"name": "بنفسجي Neon", "prim": "#9333ea", "sec": "#4c1d95", "bg": "#0f0518"},
    "stealth_dark": {"name": "أسود شبحي Stealth", "prim": "#475569", "sec": "#1e293b", "bg": "#020617"}
}

user_sessions = {
    u: {
        "running": False, "speed": 1.5, "thread": None, "token": "", "proxy": "", "webhook": "",
        "message": f"أهلاً بك، معك {u} الإدارة العليا. كيف يمكنني مساعدتك؟",
        "reply_template": "default", "ticket_filter": "administrative" if u == "isso" else "all",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10, 
        "cooldown_mode": False, "skip_next": False, "silent_mode": False, 
        "rate_limit_errors": 0, "banned_secure": False, "last_sent_text": "", "last_sent_time": 0,
        "active_tickets": set(), "lock": threading.Lock(),
        "theme": "lynwood", "ai_enabled": False, "ai_rules": "أحتاج مساعدة|تفضل كيف أخدمك",
        "claimed_history": [],
        "http_session": requests.Session()
    } for u in USERS.keys()
}

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

def init_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY, token TEXT, proxy TEXT, message TEXT, 
                      reply_template TEXT, ticket_filter TEXT, speed REAL, max_tickets INTEGER,
                      count INTEGER, total_lifetime INTEGER, webhook TEXT, theme TEXT, ai_enabled INTEGER, ai_rules TEXT)''')
        
        # التأكد من مطابقة الأعمدة تماماً لتجنب أي خطأ في القيم
        c.execute("PRAGMA table_info(users)")
        existing_cols = [col[1] for col in c.fetchall()]
        required_cols = {
            "webhook": "TEXT DEFAULT ''", "theme": "TEXT DEFAULT 'lynwood'", 
            "ai_enabled": "INTEGER DEFAULT 0", "ai_rules": "TEXT DEFAULT ''"
        }
        for col_name, col_type in required_cols.items():
            if col_name not in existing_cols:
                try: c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except: pass

        for u in USERS.keys():
            c.execute("SELECT username FROM users WHERE username=?", (u,))
            if not c.fetchone():
                filter_val = "administrative" if u == "isso" else "all"
                c.execute('''INSERT INTO users (username, token, proxy, message, reply_template, ticket_filter, speed, max_tickets, count, total_lifetime, webhook, theme, ai_enabled, ai_rules)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'lynwood', 0, 'أحتاج مساعدة|تفضل')''', 
                             (u, "", "", user_sessions[u]["message"], "default", filter_val, 1.5, 10, 0, 0))
        conn.commit()
        conn.close()

def load_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        rows = c.fetchall()
        col_names = [description[0] for description in c.description]
        conn.close()
        for r in rows:
            uname = r[0]
            if uname in user_sessions:
                row_dict = dict(zip(col_names, r))
                user_sessions[uname]["token"] = cipher(row_dict.get("token", ""), False)
                user_sessions[uname]["message"] = row_dict.get("message", "")
                user_sessions[uname]["reply_template"] = row_dict.get("reply_template", "default")
                user_sessions[uname]["ticket_filter"] = row_dict.get("ticket_filter", "all")
                user_sessions[uname]["speed"] = row_dict.get("speed", 1.5)
                user_sessions[uname]["max_tickets"] = row_dict.get("max_tickets", 10)
                user_sessions[uname]["count"] = row_dict.get("count", 0)
                user_sessions[uname]["total_lifetime"] = row_dict.get("total_lifetime", 0)
                user_sessions[uname]["webhook"] = row_dict.get("webhook", "")
                user_sessions[uname]["theme"] = row_dict.get("theme", "lynwood")
                user_sessions[uname]["ai_enabled"] = bool(row_dict.get("ai_enabled", 0))
                user_sessions[uname]["ai_rules"] = row_dict.get("ai_rules", "")

def save_db(uname):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        d = user_sessions[uname]
        enc_token = cipher(d["token"], True)
        c.execute('''UPDATE users SET token=?, proxy=?, message=?, reply_template=?, ticket_filter=?, 
                     speed=?, max_tickets=?, count=?, total_lifetime=?, webhook=?, theme=?, ai_enabled=?, ai_rules=? WHERE username=?''',
                  (enc_token, d.get("proxy",""), d["message"], d["reply_template"], d["ticket_filter"],
                   d["speed"], d["max_tickets"], d["count"], d["total_lifetime"], d.get("webhook",""), 
                   d.get("theme","lynwood"), int(d["ai_enabled"]), d["ai_rules"], uname))
        conn.commit()
        conn.close()

init_db()
load_db()

def get_secure_headers(token):
    build_num = random.randint(320000, 325000)
    props = {"os": "iOS", "browser": "Discord Client", "device": "iPhone 13, pro, max", "system_version": "17.5", "client_build_number": build_num, "client_version": "241.0"}
    b64_props = base64.b64encode(json.dumps(props).encode()).decode()
    return {
        "Authorization": token.strip(), "Content-Type": "application/json",
        "User-Agent": "Discord/241.0 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": b64_props, "X-Discord-Locale": "ar", "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
    }

def send_typing_bg(token, url):
    try: requests.post(url, headers=get_secure_headers(token), timeout=2)
    except: pass

def safe_post(username, url, payload, current_speed, is_claim=False):
    d = user_sessions[username]
    token = d["token"]
    headers = get_secure_headers(token)
    
    try:
        if "messages" in url and "typing" not in url and not is_claim and current_speed > 0:
            typing_url = f"{API}/{url.split('/channels/')[1].split('/')[0]}/typing"
            threading.Thread(target=send_typing_bg, args=(token, typing_url)).start()
            
        if current_speed > 0:
            time.sleep(current_speed)
            
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        
        remaining = int(res.headers.get('X-RateLimit-Remaining', 5))
        if remaining <= 0: 
            reset_after = float(res.headers.get('X-RateLimit-Reset-After', 0.5))
            time.sleep(reset_after + 0.05)
            
        if res.status_code == 429:
            retry_after = res.json().get("retry_after", current_speed + 1.0)
            time.sleep(retry_after + 0.1)
            return safe_post(username, url, payload, current_speed, is_claim)
        return res
    except Exception: return None

def process_ai_message(username, ch_id, message_data):
    d = user_sessions[username]
    if not d.get("ai_enabled"): return
    
    player_text = message_data.get("content", "").lower()
    if d.get("ai_rules"):
        rules = d["ai_rules"].split('\n')
        for rule in rules:
            if '|' in rule:
                keyword, reply = rule.split('|', 1)
                if keyword.strip().lower() in player_text:
                    safe_post(username, f"{API}/{ch_id}/messages", {"content": reply.strip()}, 1.5)
                    d["logs"].insert(0, f"🤖 [AI] رصد '{keyword}' وتم الرد.")
                    return

def process_ticket(username, ch_id, name, parent_id):
    session_data = user_sessions[username]
    with session_data["lock"]:
        if not session_data["running"] or session_data["banned_secure"]: return
        
        filter_mode = session_data.get("ticket_filter", "all")
        if filter_mode != "all":
            expected_category = CATEGORY_IDS.get(filter_mode)
            if expected_category and str(parent_id) != str(expected_category):
                return

        if session_data["cooldown_mode"]:
            if session_data["skip_next"]:
                session_data["skip_next"] = False
                session_data["logs"].insert(0, f"⚡ [Cooldown] تم تخطي التكت `#{name}`.")
                return
            else: session_data["skip_next"] = True

        if session_data["count"] >= session_data["max_tickets"]:
            session_data["running"] = False
            return
            
        if ch_id in session_data["active_tickets"]: return
        session_data["active_tickets"].add(ch_id)

    current_speed = session_data["speed"]
    custom_msg = session_data["message"]
    
    now_ts = time.time()
    if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 2.0):
        custom_msg += "᠎" * random.randint(1, 2)
    session_data["last_sent_text"] = custom_msg
    session_data["last_sent_time"] = now_ts

    res = None
    for attempt in range(10):
        speed_to_use = current_speed if attempt == 0 else 0
        res = safe_post(username, f"{API}/{ch_id}/messages", {"content": custom_msg}, speed_to_use, is_claim=True)
        if res and res.status_code in [200, 201]:
            break
        time.sleep(0.3)
    
    with session_data["lock"]:
        if res and res.status_code in [200, 201]:
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"✨ استلمت **#{name}** | <a href='{ticket_url}' target='_blank'>الرابط</a>"

            session_data["claimed_history"].append({"id": ch_id, "name": name})
            if len(session_data["claimed_history"]) > 10: session_data["claimed_history"].pop(0)

            if username == "Saif":
                alert_payload = {"content": f"💎 **إشعار الإدارة** 💎\nالإداري **{username}** استلم تذكرة ✅\n🎫 `#{name}`\n🔗 {ticket_url}"}
                threading.Thread(target=safe_post, args=(username, f"{API}/{SAIF_ALERT_CHANNEL}/messages", alert_payload, 0.5)).start()
            
            if session_data.get("webhook"):
                wh_payload = {"username": "M.R ELITE", "content": f"🚀 تم استلام تكت جديد بنجاح يا **{username}**!\nالتكت: #{name}\nالرابط: {ticket_url}"}
                try: requests.post(session_data["webhook"], json=wh_payload, timeout=2)
                except: pass

            if session_data["count"] < session_data["max_tickets"]:
                session_data["count"] += 1
                session_data["total_lifetime"] += 1
                session_data["logs"].insert(0, f"{log_text} ({session_data['count']}/{session_data['max_tickets']})")
                if len(session_data["logs"]) > 20: session_data["logs"].pop()
                save_db(username)

                if session_data["count"] >= session_data["max_tickets"]:
                    session_data["running"] = False
                    session_data["logs"].insert(0, "🛑 تم بلوغ الحد الأقصى، توقف النظام.")
        else:
            session_data["logs"].insert(0, f"<span style='color: #ef4444;'>❌ تعذر استلام #{name}</span>")
            
        if ch_id in session_data["active_tickets"]: session_data["active_tickets"].remove(ch_id)

def run_discord_bot(username):
    d = user_sessions[username]
    token = d["token"]
    
    d["logs"].insert(0, "🚀 تم تفعيل الرادار الصاروخي الكلاسيكي...")
    
    def on_message(ws, msg):
        if not d["running"] or d["banned_secure"]:
            ws.close(); return
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
                    
                    if time.time() - (((int(ch_id) >> 22) + 1420070400000) / 1000.0) > 90: return
                    
                    with d["lock"]:
                        if d["count"] >= d["max_tickets"] or not d["running"]: return
                    
                    threading.Thread(target=process_ticket, args=(username, ch_id, name, parent_id)).start()

            elif t == "MESSAGE_CREATE":
                ch_id = evt_data.get("channel_id")
                if ch_id in d["active_tickets"] and not evt_data.get("author", {}).get("bot", False):
                    if evt_data.get("author", {}).get("username") != username:
                        threading.Thread(target=process_ai_message, args=(username, ch_id, evt_data)).start()
        except: pass

    def on_open(ws):
        ws.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"}, "intents": 1 | 512}}))

    while d["running"] and not d["banned_secure"]:
        try:
            ws = websocket.WebSocketApp("wss://gateway.discord.gg/?v=9&encoding=json", on_open=on_open, on_message=on_message)
            ws.run_forever()
        except: time.sleep(2)

# ================= واجهات HTML =================

LANDING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DISCORD TICKET</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap');
        body { background: #030712; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: 'Orbitron', sans-serif; overflow: hidden; }
        .glitch-wrapper { position: relative; text-align: center; }
        h1 { font-size: 3.5rem; margin: 0; letter-spacing: 4px; color: #f8fafc; text-shadow: 0 0 20px rgba(255,255,255,0.2); }
        h3 { font-size: 1.2rem; color: #94a3b8; margin-top: 10px; letter-spacing: 12px; font-weight: 400; text-transform: uppercase;}
        .red-btn { margin-top: 50px; padding: 18px 50px; background: transparent; border: 2px solid #ef4444; color: #ef4444; font-size: 1.2rem; font-weight: 700; text-transform: uppercase; letter-spacing: 3px; text-decoration: none; border-radius: 8px; transition: all 0.3s ease; box-shadow: 0 0 15px rgba(239,68,68,0.2); cursor: pointer; }
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
    <title>بوابة العبور</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;800&display=swap');
        body { background: #030712; color: #fff; font-family: 'Cairo', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(15px); padding: 40px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.2); box-shadow: 0 20px 50px rgba(0,0,0,0.8); width: 320px; text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: rgba(0,0,0,0.6); border: 1px solid #1e293b; color: #fff; border-radius: 8px; text-align: center; outline: none; transition: 0.3s; box-sizing: border-box;}
        input:focus { border-color: #3b82f6; box-shadow: 0 0 10px rgba(59,130,246,0.3); }
        button { width: 100%; padding: 12px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-weight: 800; font-family: 'Cairo'; cursor: pointer; transition: 0.3s; margin-top: 15px;}
        button:hover { background: #2563eb; box-shadow: 0 0 20px rgba(59,130,246,0.5); }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="margin-top:0;">تسجيل الدخول</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
    </div>
</body>
</html>
"""

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>M.R Elite Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        
        :root { --prim: {{ theme_data.prim }}; --sec: {{ theme_data.sec }}; --bg: {{ theme_data.bg }}; }
        
        body { background: var(--bg); color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 15px; min-height: 100vh; display: flex; align-items: flex-start; justify-content: center; gap: 20px; flex-wrap: wrap;}
        
        .glass-card { background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(20px); max-width: 440px; width: 100%; padding: 26px; border-radius: 20px; border: 1px solid rgba(255,255,255, 0.1); box-shadow: 0 25px 50px rgba(0,0,0,0.9), inset 0 0 20px var(--sec); margin-top: 20px;}
        h1 { color: #fff; font-size: 20px; margin-bottom: 5px; font-weight: 900; }
        .user-tag { color: var(--prim); font-size: 13px; background: rgba(0,0,0,0.5); padding: 5px 15px; border-radius: 20px; border: 1px solid var(--prim); display: inline-block; margin-bottom: 15px;}
        
        .badge-container { display: flex; gap: 8px; margin-bottom: 15px; }
        .glass-badge { flex: 1; background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.05); padding: 10px; border-radius: 12px; font-size: 11px; }
        .glass-badge b { color: var(--prim); font-size: 14px; display: block; margin-top: 3px; }
        
        .chart-container { background: rgba(0,0,0,0.3); border-radius: 14px; padding: 10px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 15px; height: 130px; }

        .btn { display: block; width: 100%; padding: 12px; margin: 6px 0; font-size: 13px; font-weight: 700; border: none; border-radius: 12px; cursor: pointer; transition: 0.3s; font-family: 'Cairo'; color: #fff;}
        .btn-start { background: linear-gradient(135deg, #059669, #047857); }
        .btn-stop { background: linear-gradient(135deg, #dc2626, #991b1b); }
        .btn-secondary { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); }
        
        .btn-ai-on { background: linear-gradient(135deg, #8b5cf6, #6d28d9); box-shadow: 0 0 15px rgba(139,92,246,0.4);}
        .btn-ai-off { background: rgba(0,0,0,0.5); border: 1px solid #4c1d95; color: #c4b5fd; }

        .config-section { background: rgba(0,0,0,0.4); padding: 14px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.05); text-align: right;}
        .config-title { color: var(--prim); font-size: 11px; margin-bottom: 4px; font-weight: 700; }
        input, select, textarea { width: 100%; padding: 10px; background: rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 10px; box-sizing: border-box; font-size: 11px; margin-bottom: 8px; font-family: 'Cairo'; outline: none;}
        input:focus, select:focus, textarea:focus { border-color: var(--prim); }
        textarea { height: 50px; resize: none; }
        .ai-textarea { height: 60px; border-color: #8b5cf6; }

        .log-box { background: #000; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 10px; height: 100px; overflow-y: auto; text-align: right; font-size: 11px; color: #94a3b8; margin-top: 10px; }
        
        .ghost-panel { background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(20px); max-width: 350px; width: 100%; padding: 20px; border-radius: 20px; border: 1px solid rgba(255,255,255, 0.1); box-shadow: 0 25px 50px rgba(0,0,0,0.9); margin-top: 20px; display: flex; flex-direction: column; height: 620px;}
        .ghost-header { font-weight: 900; color: #e2e8f0; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 10px;}
        .ticket-list { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; max-height: 80px; overflow-y: auto; }
        .tkt-btn { background: rgba(255,255,255,0.1); border: none; color: #94a3b8; padding: 5px 10px; border-radius: 8px; cursor: pointer; font-size: 11px; font-family: 'Cairo'; transition: 0.2s;}
        .tkt-btn:hover, .tkt-btn.active { background: var(--prim); color: #fff; }
        
        .chat-box { flex: 1; background: #000; border-radius: 10px; padding: 10px; overflow-y: auto; text-align: right; font-size: 12px; display: flex; flex-direction: column; gap: 8px; border: 1px solid rgba(255,255,255,0.05);}
        .msg { background: rgba(255,255,255,0.05); padding: 8px; border-radius: 8px; word-break: break-word;}
        .msg.bot { background: rgba(37, 99, 235, 0.1); border-right: 3px solid #3b82f6; }
        .msg-author { font-size: 10px; color: var(--prim); font-weight: bold; margin-bottom: 2px;}
    </style>
</head>
<body>
    <div class="glass-card">
        <h1>M.R SYSTEM</h1>
        <div class="user-tag">👤 {{ username }}</div>
        
        <div class="badge-container">
            <div class="glass-badge">إنجاز <b id="count_disp">{{ count }}/{{ max_tickets }}</b></div>
            <div class="glass-badge">السرعة <b id="speed_disp">{{ speed }}s</b></div>
            <div class="glass-badge">التراكمي <b id="total_disp">{{ total_lifetime }}</b></div>
        </div>

        <div class="chart-container"><canvas id="progressChart"></canvas></div>
        
        <form action="/toggle" method="post">
            <button type="submit" id="main_btn" class="btn {% if running %}btn-stop{% else %}btn-start{% endif %}">
                {% if running %}إيقاف النظام 🛑{% else %}تشغيل النظام 🚀{% endif %}
            </button>
        </form>

        <div style="margin: 10px 0;">
            <form action="/toggle_ai" method="post">
                <button type="submit" class="btn {% if ai_enabled %}btn-ai-on{% else %}btn-ai-off{% endif %}">🤖 نظام الذكاء الاصطناعي (AI)</button>
            </form>
        </div>

        <div class="config-section">
            <form action="/update_settings" method="post">
                <div class="config-title">تخصيص المظهر (Theme):</div>
                <select name="theme">
                    {% for k, v in themes.items() %}
                    <option value="{{ k }}" {% if theme == k %}selected{% endif %}>{{ v.name }}</option>
                    {% endfor %}
                </select>

                <div class="config-title">نوع الشكاوي المستهدفة:</div>
                <select name="ticket_filter">
                    <option value="all" {% if ticket_filter == 'all' %}selected{% endif %}>🌐 جميع التكتات (All Tickets)</option>
                    <option value="administrative" {% if ticket_filter == 'administrative' %}selected{% endif %}>🛡️ الشكاوى الإدارية (1353444395575414844)</option>
                    <option value="players" {% if ticket_filter == 'players' %}selected{% endif %}>👤 شكاوى اللاعبين (1353444390387060736)</option>
                    <option value="factions" {% if ticket_filter == 'factions' %}selected{% endif %}>🎖️ شكاوى قائدات الفصائل (1353444400679747665)</option>
                </select>

                <div class="config-title">قواعد الذكاء الاصطناعي (الكلمة|الرد):</div>
                <textarea name="ai_rules" class="ai-textarea" placeholder="أحتاج مساعدة|تفضل كيف أخدمك">{{ ai_rules }}</textarea>
                
                <div style="display:flex; gap:8px;">
                    <div style="flex:1;"><div class="config-title">الحد الأقصى:</div><input type="number" name="max_tickets" value="{{ max_tickets }}" min="1"></div>
                    <div style="flex:1;"><div class="config-title">السرعة:</div><input type="number" step="0.01" name="custom_speed" value="{{ speed }}"></div>
                </div>
                
                <div class="config-title">نص الرد الافتراضي:</div>
                <textarea name="custom_msg">{{ message }}</textarea>
                <button type="submit" class="btn" style="background: var(--prim);">حفظ الإعدادات 💾</button>
            </form>
        </div>

        <div style="display: flex; gap: 8px; margin: 10px 0;">
            <form action="/token" method="get" style="flex:1;"><button class="btn btn-secondary" style="margin:0;">🔑 التوكن</button></form>
            <form action="/reset_all" method="post" onsubmit="return confirm('تصفير؟');" style="flex:1;"><button class="btn btn-secondary" style="margin:0; color:#ef4444;">🗑️ تصفير</button></form>
        </div>

        <div class="log-box" id="log_box">{% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div>النظام جاهز...</div>{% endfor %}</div>
        <a href="/logout" style="color:#ef4444; text-decoration:none; font-size:12px; display:block; margin-top:15px; font-weight:700;">تسجيل خروج</a>
    </div>

    <div class="ghost-panel">
        <div class="ghost-header">👁️ التكتات المستلمة (Ghost Monitor)</div>
        <div class="ticket-list" id="ticket_list"></div>
        <div class="chat-box" id="chat_box"><div style="color:#475569; text-align:center; margin-top:50%;">اختر تكت من الأعلى لمراقبة الرسائل...</div></div>
    </div>

    <script>
        var ctx = document.getElementById('progressChart').getContext('2d');
        var myChart = new Chart(ctx, {
            type: 'doughnut',
            data: { labels: ['المنجز', 'المتبقي'], datasets: [{ data: [{{ count }}, {{ max_tickets - count if max_tickets - count > 0 else 0 }}], backgroundColor: ['{{ theme_data.prim }}', 'rgba(255,255,255,0.05)'], borderWidth: 0 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, cutout: '75%' }
        });

        let currentActiveTicket = null;

        function loadChat(ch_id) {
            currentActiveTicket = ch_id;
            document.querySelectorAll('.tkt-btn').forEach(b => b.classList.remove('active'));
            let btn = document.getElementById('btn_' + ch_id);
            if(btn) btn.classList.add('active');
            document.getElementById('chat_box').innerHTML = '<div style="color:#475569; text-align:center; margin-top:50%;">جاري تحميل الرسائل...</div>';
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
                    let isBot = m.bot ? 'bot' : '';
                    let msgContent = m.content;
                    let urlRegex = /(https?:\/\/[^\s]+)/g;
                    msgContent = msgContent.replace(urlRegex, function(url) {
                        if(url.match(/\.(jpeg|jpg|gif|png|webp)$/i)) {
                            return `<br><img src="${url}" style="max-width:100%; border-radius:5px; margin-top:5px;"><br><a href="${url}" target="_blank" style="color:var(--prim); font-size:10px;">[رابط الصورة]</a>`;
                        }
                        return `<a href="${url}" target="_blank" style="color:var(--prim); text-decoration:underline;">${url}</a>`;
                    });

                    if(m.attachments && m.attachments.length > 0) {
                        m.attachments.forEach(att => {
                            if(att.url.match(/\.(jpeg|jpg|gif|png|webp)$/i)) {
                                msgContent += `<br><img src="${att.url}" style="max-width:100%; border-radius:5px; margin-top:5px;">`;
                            }
                            msgContent += `<br><a href="${att.url}" target="_blank" style="color:var(--prim); font-size:10px;">[مرفق: ${att.filename}]</a>`;
                        });
                    }

                    chatHtml += `<div class="msg ${isBot}"><div class="msg-author">${m.author}</div>${msgContent}</div>`;
                });
                if(chatHtml === '') chatHtml = '<div style="color:#475569; text-align:center; margin-top:50%;">لا توجد رسائل بعد...</div>';
                document.getElementById('chat_box').innerHTML = chatHtml;
            } catch(e) {}
        }

        setInterval(async () => {
            try {
                let res = await fetch('/api/status');
                let data = await res.json();
                
                document.getElementById('count_disp').innerText = data.count + '/' + data.max_tickets;
                document.getElementById('speed_disp').innerText = data.speed + 'ث';
                document.getElementById('total_disp').innerText = data.total;
                
                let btn = document.getElementById('main_btn');
                if(data.running) {
                    btn.className = "btn btn-stop"; btn.innerText = "إيقاف النظام 🛑";
                } else {
                    btn.className = "btn btn-start"; btn.innerText = "تشغيل النظام 🚀";
                }

                let logHtml = '';
                data.logs.forEach(l => { logHtml += '<div>• ' + l + '</div>'; });
                document.getElementById('log_box').innerHTML = logHtml || '<div style="text-align:center; color:#555;">النظام جاهز...</div>';

                let rem = data.max_tickets - data.count;
                myChart.data.datasets[0].data = [data.count, rem > 0 ? rem : 0];
                myChart.update();

                let tktsHtml = '';
                data.history.forEach(t => {
                    let activeCls = (currentActiveTicket == t.id) ? 'active' : '';
                    tktsHtml += `<button id="btn_${t.id}" class="tkt-btn ${activeCls}" onclick="loadChat('${t.id}')">#${t.name}</button>`;
                });
                if(tktsHtml === '') tktsHtml = '<div style="color:#64748b; font-size:11px;">لم يتم استلام تكتات بعد</div>';
                document.getElementById('ticket_list').innerHTML = tktsHtml;
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
    <title>M.R Master Dashboard</title>
    <style>
        body { background: #0f172a; color: #fff; font-family: sans-serif; text-align: center; padding: 20px;}
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #1e293b; border-radius: 10px; overflow: hidden;}
        th, td { padding: 15px; border-bottom: 1px solid #334155; }
        th { background: #0f172a; color: #38bdf8; }
        .btn { padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; color: white; background: #ef4444; text-decoration: none;}
        .btn-green { background: #10b981; }
    </style>
</head>
<body>
    <h1>👑 لوحة التحكم العليا (Master)</h1>
    <a href="/export_csv" class="btn btn-green" style="display:inline-block; margin-bottom:20px;">📥 تحميل تقرير (Excel CSV)</a>
    <table>
        <tr><th>اسم الحساب</th><th>الحالة</th><th>AI</th><th>القسم</th><th>المنجز</th><th>التراكمي</th><th>إجراء</th></tr>
        {% for u, d in users.items() %}
        <tr>
            <td>{{ u }}</td>
            <td style="color: {{ '#10b981' if d.running else '#ef4444' }};">{{ 'شغال 🟢' if d.running else 'متوقف 🔴' }}</td>
            <td>{{ '🤖 On' if d.ai_enabled else 'Off' }}</td>
            <td>{{ d.ticket_filter }}</td>
            <td>{{ d.count }} / {{ d.max_tickets }}</td>
            <td>{{ d.total_lifetime }}</td>
            <td><form action="/master_stop" method="post"><input type="hidden" name="target" value="{{ u }}"><button class="btn">إيقاف بالقوة</button></form></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(LANDING_HTML)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
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
    return render_template_string("""<!DOCTYPE html><html lang="ar" dir="rtl"><head><style>body{background:#030712;color:#fff;font-family:sans-serif;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh}textarea{width:300px;height:80px;background:#1e293b;color:#fff;border:none;border-radius:10px;padding:10px;outline:none;}textarea:focus{border-color:#3b82f6;}button{margin-top:10px;padding:10px;background:#3b82f6;color:#fff;border:none;border-radius:10px;cursor:pointer;width:320px;font-weight:bold}</style></head><body><div><h2>أدخل التوكن (سيتم تشفيره 🔒)</h2><form method="POST"><textarea name="token" required></textarea><br><button type="submit">حفظ وتأمين 🛡️</button></form></div></body></html>""")

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]: return redirect(url_for('login'))
    usr = session['user']
    d = user_sessions[usr]
    theme_key = d.get("theme", "lynwood")
    theme_data = THEMES.get(theme_key, THEMES["lynwood"])
    
    return render_template_string(PANEL_HTML, username=usr, max_tickets=d["max_tickets"], count=d["count"], speed=d["speed"], 
                                  message=d["message"], webhook=d.get("webhook",""), theme=theme_key, 
                                  themes=THEMES, theme_data=theme_data, ai_enabled=d["ai_enabled"], ai_rules=d["ai_rules"],
                                  ticket_filter=d.get("ticket_filter", "all"),
                                  running=d["running"], total_lifetime=d["total_lifetime"], logs=d["logs"])

@app.route('/api/status')
def api_status():
    if 'user' not in session: return json.dumps({"error": "unauth"})
    u = session['user']
    d = user_sessions[u]
    return json.dumps({
        "count": d["count"], 
        "max_tickets": d["max_tickets"], 
        "speed": d["speed"], 
        "running": d["running"], 
        "logs": d["logs"], 
        "total": d["total_lifetime"], 
        "history": d.get("claimed_history", [])
    })

@app.route('/api/chat/<ch_id>')
def api_chat(ch_id):
    if 'user' not in session: return json.dumps({"error": "unauth"})
    u = session['user']
    token = user_sessions[u]["token"]
    try:
        res = requests.get(f"{API}/{ch_id}/messages?limit=15", headers=get_secure_headers(token), timeout=3)
        if res.status_code == 200:
            msgs = res.json()
            msgs.reverse()
            clean_msgs = [{"author": m["author"]["username"], "content": m["content"], "bot": m["author"].get("bot", False), "attachments": m.get("attachments", [])} for m in msgs]
            return json.dumps(clean_msgs)
    except Exception: pass
    return json.dumps([])

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' in session:
        usr = session['user']
        if not user_sessions[usr]["running"] and user_sessions[usr]["token"]:
            if user_sessions[usr]["count"] >= user_sessions[usr]["max_tickets"]: user_sessions[usr]["count"] = 0
            user_sessions[usr]["running"] = True
            threading.Thread(target=run_discord_bot, args=(usr,), daemon=True).start()
        else: user_sessions[usr]["running"] = False
    return redirect(url_for('panel'))

@app.route('/toggle_ai', methods=['POST'])
def toggle_ai():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["ai_enabled"] = not user_sessions[usr]["ai_enabled"]
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["message"] = request.form.get('custom_msg', '').strip()
        user_sessions[usr]["theme"] = request.form.get('theme', 'lynwood')
        user_sessions[usr]["ticket_filter"] = request.form.get('ticket_filter', 'all')
        user_sessions[usr]["ai_rules"] = request.form.get('ai_rules', '').strip()
        try:
            user_sessions[usr]["max_tickets"] = int(request.form.get('max_tickets', 10))
            user_sessions[usr]["speed"] = float(request.form.get('custom_speed', 1.5))
        except: pass
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/master', methods=['GET', 'POST'])
def master():
    if request.method == 'POST':
        if request.form.get('pass') == MASTER_PASSWORD: session['master'] = True
    if not session.get('master'):
        return """<body style="background:#000; color:#fff; text-align:center; padding-top:100px; font-family:sans-serif;"><form method="POST"><input type="password" name="pass" placeholder="Master Password" style="padding:10px; border-radius:5px;"><button style="padding:10px; background:#3b82f6; color:#fff; border:none; border-radius:5px;">Login</button></form></body>"""
    return render_template_string(MASTER_HTML, users=user_sessions)

@app.route('/master_stop', methods=['POST'])
def master_stop():
    if session.get('master'):
        target = request.form.get('target')
        if target in user_sessions: user_sessions[target]["running"] = False
    return redirect(url_for('master'))

@app.route('/export_csv')
def export_csv():
    if not session.get('master'): return "Access Denied"
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Username', 'Status', 'AI', 'Filter', 'Daily Count', 'Total Lifetime'])
    for u, d in user_sessions.items():
        cw.writerow([u, 'Running' if d["running"] else 'Stopped', 'On' if d["ai_enabled"] else 'Off', d["ticket_filter"], d["count"], d["total_lifetime"]])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=M_R_Elite_Report.csv"
    output.headers["Content-type"] = "text/csv"
    return output

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
