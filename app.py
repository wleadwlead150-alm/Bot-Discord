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
app.secret_key = "MR_ELITE_SECRET_CORE_V101"

INITIAL_USERS = {
    "Saif": "12345678", "Marshall": "oopp0099", "Youssef": "oopp009987",
    "Kara": "oopp00998", "isso": "12345678", "Azmy": "12345678"
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
    "lynwood": {"name": "أزرق Lynwood Police", "prim": "#2563eb", "sec": "#1e3a8a", "bg": "#0a0f1d"}
}

global_settings = {"min_speed": 1.0, "broadcast_msg": "", "broadcast_id": 0}

user_sessions = {}
db_lock = threading.Lock()
anti_clash_lock = threading.Lock()
last_global_claim_ts = 0

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
    d = user_sessions[username]
    token = d["token"]
    headers = get_secure_headers(token)
    try:
        if current_speed > 0: time.sleep(current_speed)
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        
        # التبريد التلقائي (Dynamic Cool-down)
        remaining = int(res.headers.get('X-RateLimit-Remaining', 5))
        if remaining <= 2: time.sleep(0.2) # إضافة 0.2 ثانية تبريد إذا اقترب الحظر
        
        if remaining <= 0: time.sleep(float(res.headers.get('X-RateLimit-Reset-After', 0.5)) + 0.05)
        if res.status_code == 429:
            time.sleep(res.json().get("retry_after", 1.0) + 0.1)
            return safe_post(username, url, payload, 0)
        return res
    except: return None

def process_ticket(username, ch_id, name, parent_id):
    global last_global_claim_ts
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

    # مانع التصادم بين الإداريين (Anti-Clash System)
    with anti_clash_lock:
        now = time.time()
        if now - last_global_claim_ts < 0.05: time.sleep(random.uniform(0.05, 0.1))
        last_global_claim_ts = time.time()

    # الدوران العشوائي للرسائل (Message Rotation)
    msg_list = [m.strip() for m in session_data["message"].split('||') if m.strip()]
    custom_msg = random.choice(msg_list) if msg_list else "استلمت التكت."
    
    now_ts = time.time()
    if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 2.0):
        custom_msg += "᠎" * random.randint(1, 2)
    session_data["last_sent_text"] = custom_msg
    session_data["last_sent_time"] = now_ts

    res = safe_post(username, f"{API}/{ch_id}/messages", {"content": custom_msg}, session_data["speed"], is_claim=True)
    
    with session_data["lock"]:
        if res and res.status_code in [200, 201]:
            log_ticket(username, ch_id)
            t_time = datetime.now().strftime("%I:%M %p")
            # تحديد نوع التكت لإضاءة الحواف
            cat_type = "administrative" if str(parent_id) == CATEGORY_IDS["administrative"] else "players" if str(parent_id) == CATEGORY_IDS["players"] else "factions"
            session_data["claimed_history"].append({"id": ch_id, "name": name, "time": t_time, "cat": cat_type})
            if len(session_data["claimed_history"]) > 20: session_data["claimed_history"].pop(0)
            session_data["logs"].insert(0, f"✨ استلمت **#{name}**")
            save_db(username)
        else:
            session_data["count"] = max(0, session_data["count"] - 1)
            session_data["total_lifetime"] = max(0, session_data["total_lifetime"] - 1)
        if ch_id in session_data["active_tickets"]: session_data["active_tickets"].remove(ch_id)

def run_discord_bot(username):
    d = user_sessions[username]
    token = d["token"]
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

# ================= HTML TEMPLATES =================

MANIFEST_JSON = """{"name": "M.R Sniper Pro", "short_name": "M.R Sniper", "start_url": "/login", "display": "standalone", "background_color": "#030712", "theme_color": "#ef4444", "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/2202/2202112.png", "sizes": "512x512", "type": "image/png"}]}"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="manifest" href="/manifest.json"><link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/2202/2202112.png">
    <title>تسجيل الدخول</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;800&display=swap');
        body { background: #030712; color: #fff; font-family: 'Cairo', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(15px); padding: 40px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.2); width: 320px; text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: rgba(0,0,0,0.6); border: 1px solid #1e293b; color: #fff; border-radius: 8px; text-align: center; font-size: 16px;}
        button { width: 100%; padding: 12px; background: #3b82f6; color: #fff; border: none; border-radius: 8px; font-weight: 800; font-family: 'Cairo'; cursor: pointer; margin-top: 15px;}
    </style>
</head>
<body>
    <div class="card">
        <h2>بوابة العبور</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
        {% if error %}<p style="color:#ef4444; font-size:12px;">{{ error }}</p>{% endif %}
    </div>
</body>
</html>
"""

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link rel="manifest" href="/manifest.json"><link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/2202/2202112.png">
    <title>M.R Command Center</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=gg+sans:wght@400;600&display=swap'); 
        :root { --prim: {{ theme_data.prim }}; --sec: {{ theme_data.sec }}; --bg: {{ theme_data.bg }}; }
        body { background: var(--bg); color: #f8fafc; font-family: 'Cairo', sans-serif; text-align: center; margin: 0; padding: 15px; padding-bottom: 60px; min-height: 100vh;}
        
        /* إضاءة الحواف (Edge Lighting) */
        #edge-lighting { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 9999; opacity: 0; transition: opacity 0.3s, box-shadow 0.3s; }
        .edge-flash-admin { opacity: 1 !important; box-shadow: inset 0 0 40px rgba(239,68,68,0.8) !important; }
        .edge-flash-player { opacity: 1 !important; box-shadow: inset 0 0 40px rgba(59,130,246,0.8) !important; }
        .edge-flash-faction { opacity: 1 !important; box-shadow: inset 0 0 40px rgba(251,191,36,0.8) !important; }

        body.battery-saver * { animation: none !important; box-shadow: none !important; text-shadow: none !important; background-image: none !important; }
        body.compact-mode .glass-card { padding: 15px; }
        body.compact-mode h1 { font-size: 16px; margin: 0;}
        body.compact-mode .btn { padding: 8px; font-size: 12px; }
        body.compact-mode input, body.compact-mode select { padding: 6px; font-size: 11px; margin-bottom: 5px;}
        body.compact-mode .chart-container { height: 90px; }
        
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

        .modal { display: none; position: fixed; z-index: 9999; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; }
        .modal-content { background: #1e293b; padding: 20px; border-radius: 15px; text-align: center; width: 80%; border: 1px solid #3b82f6;}
    </style>
</head>
<body class="{% if compact_mode %}compact-mode{% endif %}">
    
    <div id="edge-lighting"></div>
    <button class="openbtn" onclick="openNav()">=</button>

    <div id="mySidebar" class="sidebar">
        <a href="javascript:void(0)" class="closebtn" onclick="closeNav()">&times;</a>
        <div class="sidebar-content">
            <button onclick="showStats()" class="btn btn-start" style="margin-bottom:15px;">📊 إحصائياتي الشخصية</button>
            <form action="/update_sidebar" method="post">
                <select name="theme">
                    {% for k, v in themes.items() %}<option value="{{ k }}" {% if theme == k %}selected{% endif %}>{{ v.name }}</option>{% endfor %}
                </select>
                <select name="ticket_filter">
                    <option value="all" {% if ticket_filter == 'all' %}selected{% endif %}>🌐 جميع التكتات</option>
                    <option value="administrative" {% if ticket_filter == 'administrative' %}selected{% endif %}>🛡️ شكاوى إدارية</option>
                </select>
                <div style="text-align:right; margin-bottom:10px; font-size:12px; color:#94a3b8;">
                    <input type="checkbox" name="compact_mode" style="width:auto; display:inline;" {% if compact_mode %}checked{% endif %}> تفعيل الوضع المدمج (للموبايل)
                </div>
                <button type="submit" class="btn btn-secondary" style="background: var(--prim); color:#fff;">حفظ التغييرات</button>
            </form>
            <form action="/token" method="get"><button class="btn btn-secondary">🔑 تحديث التوكن</button></form>
            <a href="/logout" class="btn btn-stop" style="margin-top:20px; text-decoration:none; display:block;">تسجيل خروج</a>
        </div>
    </div>

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
        </div>

        <div class="ghost-panel" id="ghost_panel">
            <div class="pull-indicator" id="pullIndicator">اسحب للأسفل للتحديث ↓</div>
            <div class="ghost-header">Discord Live</div>
            <div class="ticket-list" id="ticket_list"></div>
            <div class="chat-box" id="chat_box"><div style="color:#949ba4; text-align:center; margin-top:40%; font-weight:600;">يرجى تحديد تذكرة...</div></div>
        </div>
    </div>

    <script>
        function openNav() { document.getElementById("mySidebar").style.width = "250px"; }
        function closeNav() { document.getElementById("mySidebar").style.width = "0"; }

        if(navigator.getBattery) {
            navigator.getBattery().then(function(b) {
                if(b.level <= 0.20 && !b.charging) document.body.classList.add('battery-saver');
                b.addEventListener('levelchange', function() {
                    if(b.level <= 0.20 && !b.charging) document.body.classList.add('battery-saver');
                    else document.body.classList.remove('battery-saver');
                });
            });
        }

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
                    if(newTicket) triggerEdgeLighting(newTicket.cat);
                    lastCount = data.count;
                } else if (data.count < lastCount) { lastCount = data.count; }

                // شريط الحالة التفاعلي (Dynamic App Title)
                document.title = `🚀 ${data.count}/${data.max_tickets} | M.R System`;

                document.getElementById('count_disp').innerText = data.count + '/' + data.max_tickets;
                myChart.data.datasets[0].data = [data.count, data.max_tickets - data.count > 0 ? data.max_tickets - data.count : 0];
                myChart.update();

                let tktsHtml = '';
                data.history.forEach(t => {
                    let activeCls = (currentActiveTicket == t.id) ? 'active' : '';
                    tktsHtml += `<button id="btn_${t.id}" class="tkt-btn ${activeCls}" onclick="loadChat('${t.id}')">#${t.name}</button>`;
                });
                document.getElementById('ticket_list').innerHTML = tktsHtml;
            } catch(e) {}
        }, 3000); 
    </script>
</body>
</html>
"""

MASTER_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>Master Pro</title>
    <style>
        body { background: #020617; color: #f8fafc; font-family: sans-serif; padding: 20px;}
        .card { background: #0f172a; padding: 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #1e293b;}
        table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #1e293b; border-radius: 10px; overflow: hidden;}
        th, td { padding: 12px; border-bottom: 1px solid #334155; text-align: center; font-size:14px;}
        th { background: #020617; color: #38bdf8; }
        .btn { padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; color: white; font-weight: bold;}
        .btn-red { background: #ef4444; } .btn-yellow { background: #fbbf24; color: #000; }
        input { padding: 8px; border-radius: 5px; border: 1px solid #334155; background: #020617; color: #fff;}
    </style>
</head>
<body>
    <h1 style="text-align:center; color:#38bdf8;">👑 لوحة تحكم الإدارة العليا (Master Pro)</h1>
    <div class="card">
        <h3>👥 إدارة الفريق</h3>
        <table>
            <tr><th>المستخدم</th><th>الحالة</th><th>يقرأ الآن (Live 👁️)</th><th>المنجز</th></tr>
            {% for u, d in users.items() %}
            <tr>
                <td><b>{{ u }}</b></td>
                <td style="color: {% if d.is_suspended %}#ef4444{% elif d.status == 'running' %}#10b981{% else %}#fbbf24{% endif %};">
                    {{ 'مجمد ❄️' if d.is_suspended else 'نشط 🚀' if d.status == 'running' else 'استراحة ⏸️' if d.status == 'paused' else 'متوقف 🛑' }}
                </td>
                <td style="color:#38bdf8;">{{ d.currently_viewing }}</td>
                <td>{{ d.count }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <script>setTimeout(() => location.reload(), 10000);</script>
</body>
</html>
"""

@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        if username == "Marshall" and password == "oopp00998":
            session['master'] = True; return redirect(url_for('master'))
        if username in user_sessions and user_sessions[username]["password"] == password:
            if user_sessions[username]["is_suspended"]: return render_template_string(LOGIN_HTML, error="حسابك مجمد ❄️")
            session['user'] = username
            if not user_sessions[username]["token"]: return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
        return render_template_string(LOGIN_HTML, error="بيانات غير صحيحة")
    return render_template_string(LOGIN_HTML)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user_sessions[session['user']]["token"] = request.form.get('token').strip(); save_db(session['user']); return redirect(url_for('panel'))
    return render_template_string("""<body style="background:#030712; text-align:center; padding-top:100px;"><form method="POST"><textarea name="token" required style="width:300px; height:80px;"></textarea><br><button style="padding:10px; background:#3b82f6; color:#fff; border:none; margin-top:10px;">حفظ</button></form></body>""")

@app.route('/panel')
def panel():
    if 'user' not in session: return redirect(url_for('login'))
    usr = session['user']; d = user_sessions[usr]
    if d["is_suspended"]: return redirect(url_for('logout'))
    theme_key = d.get("theme", "cyber_red")
    return render_template_string(PANEL_HTML, username=usr, max_tickets=d["max_tickets"], count=d["count"], speed=d["speed"], message=d["message"], theme=theme_key, themes=THEMES, theme_data=THEMES[theme_key], ticket_filter=d["ticket_filter"], status=d["status"], compact_mode=d["compact_mode"])

@app.route('/api/status')
def api_status():
    if 'user' not in session: return json.dumps({"error": "unauth"})
    u = session['user']; d = user_sessions[u]
    visible_history = [t for t in d["claimed_history"] if t["id"] not in d.get("hidden_tickets", set())]
    return json.dumps({"count": d["count"], "max_tickets": d["max_tickets"], "speed": d["speed"], "status": d["status"], "is_suspended": d["is_suspended"], "history": visible_history, "broadcast_msg": global_settings["broadcast_msg"], "broadcast_id": global_settings["broadcast_id"]})

@app.route('/api/viewing/<ch_id>')
def api_viewing(ch_id):
    if 'user' in session: user_sessions[session['user']]["currently_viewing"] = f"تكت #{ch_id[-4:]}"
    return "ok"

@app.route('/api/hide_ticket/<ch_id>', methods=['POST'])
def hide_ticket(ch_id):
    if 'user' in session: user_sessions[session['user']]["hidden_tickets"].add(ch_id)
    return "ok"

@app.route('/api/my_stats')
def api_my_stats():
    if 'user' not in session: return jsonify({"error": "unauth"})
    usr = session['user']; now = time.time(); day_ago, week_ago, month_ago = now - 86400, now - (86400*7), now - (86400*30)
    with db_lock:
        c = sqlite3.connect('elite_system.db', check_same_thread=False).cursor()
        c.execute("SELECT COUNT(*) FROM ticket_logs WHERE username=? AND timestamp > ?", (usr, day_ago)); d = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM ticket_logs WHERE username=? AND timestamp > ?", (usr, week_ago)); w = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM ticket_logs WHERE username=? AND timestamp > ?", (usr, month_ago)); m = c.fetchone()[0]
    return jsonify({"daily": d, "weekly": w, "monthly": m})

@app.route('/api/chat/<ch_id>')
def api_chat(ch_id):
    if 'user' not in session: return json.dumps({"error": "unauth"})
    try:
        res = requests.get(f"{API}/{ch_id}/messages?limit=15", headers=get_secure_headers(user_sessions[session['user']]["token"]), timeout=3)
        if res.status_code == 200:
            msgs = res.json(); msgs.reverse()
            return json.dumps([{"author": m["author"]["username"], "content": m["content"]} for m in msgs])
    except: pass
    return json.dumps([])

@app.route('/set_status', methods=['POST'])
def set_status():
    if 'user' in session:
        usr = session['user']; new_status = request.form.get('new_status')
        if new_status in ["running", "paused", "stopped"] and not user_sessions[usr]["is_suspended"]:
            old_status = user_sessions[usr]["status"]; user_sessions[usr]["status"] = new_status
            if new_status == "running" and old_status == "stopped" and user_sessions[usr]["token"]:
                if user_sessions[usr]["count"] >= user_sessions[usr]["max_tickets"]: user_sessions[usr]["count"] = 0
                threading.Thread(target=run_discord_bot, args=(usr,), daemon=True).start()
    return redirect(url_for('panel'))

@app.route('/update_main', methods=['POST'])
def update_main():
    if 'user' in session:
        usr = session['user']; user_sessions[usr]["message"] = request.form.get('custom_msg', '').strip()
        try:
            user_sessions[usr]["max_tickets"] = int(request.form.get('max_tickets', 10))
            user_sessions[usr]["speed"] = max(float(request.form.get('custom_speed', 1.1)), global_settings["min_speed"])
        except: pass
        save_db(usr)
    return redirect(url_for('panel'))

@app.route('/update_sidebar', methods=['POST'])
def update_sidebar():
    if 'user' in session:
        usr = session['user']; user_sessions[usr]["theme"] = request.form.get('theme', 'cyber_red')
        user_sessions[usr]["ticket_filter"] = request.form.get('ticket_filter', 'all')
        user_sessions[usr]["compact_mode"] = 1 if request.form.get('compact_mode') else 0; save_db(usr)
    return redirect(url_for('panel'))

@app.route('/logout')
def logout(): session.pop('user', None); session.pop('master', None); return redirect(url_for('login'))

@app.route('/master')
def master():
    if not session.get('master'): return redirect(url_for('login'))
    return render_template_string(MASTER_HTML, users=user_sessions)

if __name__ == '__main__': app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
