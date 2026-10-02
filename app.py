import json
import time
import requests
import websocket
import threading
import random
import os
import base64
import sqlite3
import csv
from datetime import timedelta
from io import StringIO
from flask import Flask, render_template_string, request, redirect, url_for, session, make_response

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "MR_ELITE_SECRET_CORE_V99")

# 🔒 تأمين الجلسات
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,  # اجعلها True إذا كنت على HTTPS
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

# =========================================================
# USERS
# =========================================================

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

# =========================================================
# SESSIONS
# =========================================================

user_sessions = {
    u: {
        "running": False, "speed": 1.1, "thread": None, "token": "", "proxy": "", "webhook": "",
        "message": f"أهلاً بك، معك {u} الإدارة العليا. كيف يمكنني مساعدتك؟",
        "ticket_filter": "administrative" if u == "isso" else "all",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 10,
        "cooldown_mode": False, "skip_next": False, "banned_secure": False,
        "last_sent_text": "", "last_sent_time": 0,
        "active_tickets": set(), "lock": threading.RLock(),
        "theme": "cyber_red", "claimed_history": []
    } for u in USERS.keys()
}

db_lock = threading.RLock()

# =========================================================
# CIPHER
# =========================================================

def cipher(text, encrypt=True):
    if not text:
        return ""
    key = app.secret_key
    if not encrypt:
        try:
            text = base64.b64decode(text.encode()).decode()
        except Exception:
            return text
    res = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))
    if encrypt:
        return base64.b64encode(res.encode()).decode()
    return res

# =========================================================
# DATABASE
# =========================================================

def init_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False, timeout=10)
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users
                         (username TEXT PRIMARY KEY, token TEXT, proxy TEXT, message TEXT,
                          ticket_filter TEXT, speed REAL, max_tickets INTEGER,
                          count INTEGER, total_lifetime INTEGER, webhook TEXT, theme TEXT)''')

            c.execute("PRAGMA table_info(users)")
            existing_cols = [col[1] for col in c.fetchall()]
            required_cols = {
                "webhook": "TEXT DEFAULT ''",
                "theme": "TEXT DEFAULT 'lynwood'",
                "ticket_filter": "TEXT DEFAULT 'all'"
            }
            for col_name, col_type in required_cols.items():
                if col_name not in existing_cols:
                    try:
                        c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    except Exception:
                        pass

            for u in USERS.keys():
                c.execute("SELECT username FROM users WHERE username=?", (u,))
                if not c.fetchone():
                    filter_val = "administrative" if u == "isso" else "all"
                    c.execute('''INSERT INTO users (username, token, proxy, message, ticket_filter, speed, max_tickets, count, total_lifetime, webhook, theme)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', 'cyber_red')''',
                              (u, "", "", user_sessions[u]["message"], filter_val, 1.1, 10, 0, 0))
            conn.commit()
        finally:
            conn.close()


def load_db():
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False, timeout=10)
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM users")
            rows = c.fetchall()
            col_names = [d[0] for d in c.description]
        finally:
            conn.close()

        for r in rows:
            uname = r[0]
            if uname in user_sessions:
                row_dict = dict(zip(col_names, r))
                user_sessions[uname]["token"] = cipher(row_dict.get("token", ""), False)
                user_sessions[uname]["message"] = row_dict.get("message", "")
                user_sessions[uname]["ticket_filter"] = row_dict.get("ticket_filter", "all")
                user_sessions[uname]["speed"] = row_dict.get("speed", 1.1)
                user_sessions[uname]["max_tickets"] = row_dict.get("max_tickets", 10)
                user_sessions[uname]["count"] = row_dict.get("count", 0)
                user_sessions[uname]["total_lifetime"] = row_dict.get("total_lifetime", 0)
                user_sessions[uname]["webhook"] = row_dict.get("webhook", "")
                user_sessions[uname]["theme"] = row_dict.get("theme", "cyber_red")


def save_db(uname):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False, timeout=10)
        try:
            c = conn.cursor()
            d = user_sessions[uname]
            enc_token = cipher(d["token"], True)

            c.execute("SELECT username FROM users WHERE username=?", (uname,))
            if not c.fetchone():
                c.execute('''INSERT INTO users (username, token, proxy, message, ticket_filter, speed, max_tickets, count, total_lifetime, webhook, theme)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (uname, enc_token, d.get("proxy", ""), d["message"], d["ticket_filter"],
                           d["speed"], d["max_tickets"], d["count"], d["total_lifetime"],
                           d.get("webhook", ""), d.get("theme", "cyber_red")))
            else:
                c.execute('''UPDATE users SET token=?, proxy=?, message=?, ticket_filter=?,
                             speed=?, max_tickets=?, count=?, total_lifetime=?, webhook=?, theme=? WHERE username=?''',
                          (enc_token, d.get("proxy", ""), d["message"], d["ticket_filter"],
                           d["speed"], d["max_tickets"], d["count"], d["total_lifetime"],
                           d.get("webhook", ""), d.get("theme", "cyber_red"), uname))
            conn.commit()
        finally:
            conn.close()


init_db()
load_db()

# =========================================================
# DISCORD HEADERS
# =========================================================

def get_secure_headers(token):
    build_num = random.randint(320000, 325000)
    props = {
        "os": "iOS", "browser": "Discord Client",
        "device": "iPhone 13, pro, max", "system_version": "17.5",
        "client_build_number": build_num, "client_version": "241.0"
    }
    b64_props = base64.b64encode(json.dumps(props).encode()).decode()
    return {
        "Authorization": token.strip(),
        "Content-Type": "application/json",
        "User-Agent": "Discord/241.0 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": b64_props,
        "X-Discord-Locale": "ar",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
    }

# =========================================================
# SAFE POST
# =========================================================

def safe_post(username, url, payload, current_speed):
    d = user_sessions[username]
    token = d["token"]
    headers = get_secure_headers(token)

    try:
        if current_speed > 0:
            time.sleep(current_speed)

        res = requests.post(url, json=payload, headers=headers, timeout=10)

        remaining = int(res.headers.get('X-RateLimit-Remaining', 5))
        if remaining <= 0:
            reset_after = float(res.headers.get('X-RateLimit-Reset-After', 0.5))
            time.sleep(reset_after + 0.05)

        if res.status_code == 429:
            try:
                retry_after = res.json().get("retry_after", 1.0)
            except Exception:
                retry_after = 1.0
            time.sleep(retry_after + 0.1)
            return safe_post(username, url, payload, 0)
        return res
    except Exception:
        return None

# =========================================================
# PROCESS TICKET
# =========================================================

def process_ticket(username, ch_id, name, parent_id):
    session_data = user_sessions[username]

    with session_data["lock"]:
        if not session_data["running"] or session_data["banned_secure"]:
            return

        if session_data["count"] >= session_data["max_tickets"]:
            session_data["running"] = False
            return

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
            else:
                session_data["skip_next"] = True

        if ch_id in session_data["active_tickets"]:
            return
        session_data["active_tickets"].add(ch_id)

        session_data["count"] += 1
        session_data["total_lifetime"] += 1
        current_count = session_data["count"]
        max_lim = session_data["max_tickets"]

        # 🔒 تجهيز الرسالة تحت القفل
        custom_msg = session_data["message"]
        now_ts = time.time()
        if session_data["last_sent_text"] == custom_msg and (now_ts - session_data["last_sent_time"] < 2.0):
            custom_msg += "᠎" * random.randint(1, 2)
        session_data["last_sent_text"] = custom_msg
        session_data["last_sent_time"] = now_ts
        current_speed = session_data["speed"]

    res = safe_post(username, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed)

    with session_data["lock"]:
        if res and res.status_code in (200, 201):
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"✨ استلمت **#{name}** | <a href='{ticket_url}' target='_blank'>الرابط</a>"

            session_data["claimed_history"].append({"id": ch_id, "name": name})
            if len(session_data["claimed_history"]) > 10:
                session_data["claimed_history"].pop(0)

            if username == "Saif":
                alert_payload = {
                    "content": f"💎 **إشعار الإدارة** 💎\nالإداري **{username}** استلم تذكرة ✅\n🎫 `#{name}`\n🔗 {ticket_url}"
                }
                threading.Thread(
                    target=safe_post,
                    args=(username, f"{API}/{SAIF_ALERT_CHANNEL}/messages", alert_payload, 0),
                    daemon=True
                ).start()

            session_data["logs"].insert(0, f"{log_text} ({current_count}/{max_lim})")
            if len(session_data["logs"]) > 20:
                session_data["logs"].pop()
            save_db(username)

            if current_count >= max_lim:
                session_data["running"] = False
                session_data["logs"].insert(0, "🛑 تم بلوغ الحد الأقصى، توقف النظام.")
        else:
            session_data["count"] = max(0, session_data["count"] - 1)
            session_data["total_lifetime"] = max(0, session_data["total_lifetime"] - 1)
            session_data["logs"].insert(0, f"<span style='color: #ef4444;'>❌ تعذر استلام #{name}</span>")

        if ch_id in session_data["active_tickets"]:
            session_data["active_tickets"].remove(ch_id)

# =========================================================
# DISCORD BOT
# =========================================================

def run_discord_bot(username):
    d = user_sessions[username]
    token = d["token"]
    d["logs"].insert(0, "🚀 تم تفعيل النظام الكلاسيكي السريع جداً...")

    def on_message(ws, msg):
        if not d["running"] or d["banned_secure"]:
            ws.close()
            return
        try:
            raw = json.loads(msg)
            t = raw.get("t")
            evt_data = raw.get("d", {})

            if raw.get("op") == 10:
                ws.send(json.dumps({"op": 1, "d": None}))

            if t == "CHANNEL_CREATE":
                if evt_data.get("guild_id") == SERVER_ID and evt_data.get("type") == 0:
                    ch_id = evt_data.get("id")
                    name = evt_data.get("name", "").lower()
                    parent_id = evt_data.get("parent_id", "")

                    created_timestamp = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                    if time.time() - created_timestamp > 15:
                        return

                    # 🔒 القفل هنا لتفادي Race Condition
                    with d["lock"]:
                        if d["count"] >= d["max_tickets"] or not d["running"]:
                            return

                    threading.Thread(
                        target=process_ticket,
                        args=(username, ch_id, name, parent_id),
                        daemon=True
                    ).start()
        except Exception:
            pass

    def on_open(ws):
        ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": token,
                "properties": {"os": "iOS", "browser": "Discord Client", "device": "iPhone"},
                "intents": 1 | 512
            }
        }))

    while d["running"] and not d["banned_secure"]:
        try:
            ws = websocket.WebSocketApp(
                "wss://gateway.discord.gg/?v=9&encoding=json",
                on_open=on_open,
                on_message=on_message
            )
            ws.run_forever()
        except Exception:
            time.sleep(2)

# =========================================================
# HTML TEMPLATES (لا تغيير)
# =========================================================

LANDING_HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>DISCORD TICKET</title><style>@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&display=swap');body{background:#030712;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;margin:0;font-family:'Orbitron',sans-serif;overflow:hidden;}.glitch-wrapper{position:relative;text-align:center;}h1{font-size:3.5rem;margin:0;letter-spacing:4px;color:#f8fafc;text-shadow:0 0 20px rgba(255,255,255,0.2);}h3{font-size:1.2rem;color:#94a3b8;margin-top:10px;letter-spacing:12px;font-weight:400;text-transform:uppercase;}.red-btn{margin-top:50px;padding:18px 50px;background:transparent;border:2px solid #ef4444;color:#ef4444;font-size:1.2rem;font-weight:700;text-transform:uppercase;letter-spacing:3px;text-decoration:none;border-radius:8px;transition:all 0.3s ease;box-shadow:0 0 15px rgba(239,68,68,0.2);cursor:pointer;}.red-btn:hover{background:#ef4444;color:#fff;box-shadow:0 0 40px rgba(239,68,68,0.8);transform:scale(1.05);}</style></head><body><div class="glitch-wrapper"><h1>DISCORD TICKET</h1><h3>Developer M.R</h3></div><a href="/login" class="red-btn">ENTER SYSTEM</a></body></html>"""

LOGIN_HTML = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>بوابة العبور</title><style>@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;800&display=swap');body{background:#030712;color:#fff;font-family:'Cairo',sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}.card{background:rgba(15,23,42,0.8);backdrop-filter:blur(15px);padding:40px;border-radius:16px;border:1px solid rgba(59,130,246,0.2);box-shadow:0 20px 50px rgba(0,0,0,0.8);width:320px;text-align:center;}input{width:100%;padding:12px;margin:10px 0;background:rgba(0,0,0,0.6);border:1px solid #1e293b;color:#fff;border-radius:8px;text-align:center;outline:none;transition:0.3s;box-sizing:border-box;}input:focus{border-color:#3b82f6;box-shadow:0 0 10px rgba(59,130,246,0.3);}button{width:100%;padding:12px;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-weight:800;font-family:'Cairo';cursor:pointer;transition:0.3s;margin-top:15px;}button:hover{background:#2563eb;box-shadow:0 0 20px rgba(59,130,246,0.5);}</style></head><body><div class="card"><h2 style="margin-top:0;">تسجيل الدخول</h2><form method="POST"><input type="text" name="username" placeholder="اسم المستخدم" required><input type="password" name="password" placeholder="كلمة المرور" required><button type="submit">دخول</button></form></div></body></html>"""

PANEL_HTML = """<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>M.R Elite Dashboard</title><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><style>@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap');:root{--prim:{{ theme_data.prim }};--sec:{{ theme_data.sec }};--bg:{{ theme_data.bg }};}body{background:var(--bg);color:#f8fafc;font-family:'Cairo',sans-serif;text-align:center;margin:0;padding:15px;min-height:100vh;display:flex;align-items:flex-start;justify-content:center;gap:20px;flex-wrap:wrap;}.glass-card{background:rgba(0,0,0,0.4);backdrop-filter:blur(20px);max-width:440px;width:100%;padding:26px;border-radius:20px;border:1px solid rgba(255,255,255,0.1);box-shadow:0 25px 50px rgba(0,0,0,0.9),inset 0 0 20px var(--sec);margin-top:20px;}h1{color:#fff;font-size:20px;margin-bottom:5px;font-weight:900;}.user-tag{color:var(--prim);font-size:13px;background:rgba(0,0,0,0.5);padding:5px 15px;border-radius:20px;border:1px solid var(--prim);display:inline-block;margin-bottom:15px;}.badge-container{display:flex;gap:8px;margin-bottom:15px;}.glass-badge{flex:1;background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.05);padding:10px;border-radius:12px;font-size:11px;}.glass-badge b{color:var(--prim);font-size:14px;display:block;margin-top:3px;}.chart-container{background:rgba(0,0,0,0.3);border-radius:14px;padding:10px;border:1px solid rgba(255,255,255,0.05);margin-bottom:15px;height:130px;}.btn{display:block;width:100%;padding:12px;margin:6px 0;font-size:13px;font-weight:700;border:none;border-radius:12px;cursor:pointer;transition:0.3s;font-family:'Cairo';color:#fff;}.btn-start{background:linear-gradient(135deg,#059669,#047857);}.btn-stop{background:linear-gradient(135deg,#dc2626,#991b1b);}.btn-secondary{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);}.config-section{background:rgba(0,0,0,0.4);padding:14px;border-radius:14px;border:1px solid rgba(255,255,255,0.05);text-align:right;}.config-title{color:var(--prim);font-size:11px;margin-bottom:4px;font-weight:700;}input,select,textarea{width:100%;padding:10px;background:rgba(0,0,0,0.6);border:1px solid rgba(255,255,255,0.1);color:#fff;border-radius:10px;box-sizing:border-box;font-size:11px;margin-bottom:8px;font-family:'Cairo';outline:none;}input:focus,select:focus,textarea:focus{border-color:var(--prim);}textarea{height:50px;resize:none;}.log-box{background:#000;border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:10px;height:100px;overflow-y:auto;text-align:right;font-size:11px;color:#94a3b8;margin-top:10px;}.ghost-panel{background:rgba(0,0,0,0.4);backdrop-filter:blur(20px);max-width:350px;width:100%;padding:20px;border-radius:20px;border:1px solid rgba(255,255,255,0.1);box-shadow:0 25px 50px rgba(0,0,0,0.9);margin-top:20px;display:flex;flex-direction:column;height:620px;}.ghost-header{font-weight:900;color:#e2e8f0;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:10px;margin-bottom:10px;}.ticket-list{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px;max-height:80px;overflow-y:auto;}.tkt-btn{background:rgba(255,255,255,0.1);border:none;color:#94a3b8;padding:5px 10px;border-radius:8px;cursor:pointer;font-size:11px;font-family:'Cairo';transition:0.2s;}.tkt-btn:hover,.tkt-btn.active{background:var(--prim);color:#fff;}.chat-box{flex:1;background:#000;border-radius:10px;padding:10px;overflow-y:auto;text-align:right;font-size:12px;display:flex;flex-direction:column;gap:8px;border:1px solid rgba(255,255,255,0.05);}.msg{background:rgba(255,255,255,0.05);padding:8px;border-radius:8px;word-break:break-word;}.msg.bot{background:rgba(37,99,235,0.1);border-right:3px solid #3b82f6;}.msg-author{font-size:10px;color:var(--prim);font-weight:bold;margin-bottom:2px;}</style></head><body><div class="glass-card"><h1>M.R SYSTEM</h1><div class="user-tag">👤 {{ username }}</div><div class="badge-container"><div class="glass-badge">إنجاز <b id="count_disp">{{ count }}/{{ max_tickets }}</b></div><div class="glass-badge">السرعة <b id="speed_dbtnisp">{{" speed }}s</b></div>< classdiv class="glass-b="adge">التراكمي <b idbtn="total_disp">{{ total_lifetime {% }}</b></div></div><div class="chart-container"><canvas id="progressChart"></canvas></div><form action="/toggle" method="post"><button type="submit" id="main_ if running %}btn-stop{% else %}btn-start{% endif %}">{% if running %}إيقاف النظام 🛑{% else %}تشغيل النظام 🚀{% endif %}</button></form><div class="config-section" style="margin-top:15px;"><form action="/update_settings" method="post"><div class="config-title">تخصيص المظهر (Theme):</div><select name="theme">{% for k, v in themes.items() %}<option value="{{ k }}" {% if theme == k %}selected{% endif %}>{{ v.name }}</option>{% endfor %}</select><div class="config-title">نوع الشكاوي المستهدفة:</div><select name="ticket_filter"><option value="all" {% if ticket_filter == 'all' %}selected{% endif %}>🌐 جميع التكتات</option><option value="administrative" {% if ticket_filter == 'administrative' %}selected{% endif %}>🛡️ الشكاوى الإدارية</option><option value="players" {% if ticket_filter == 'players' %}selected{% endif %}>👤 شكاوى اللاعبين</option><option value="factions" {% if ticket_filter == 'factions' %}selected{% endif %}>🎖️ شكاوى قائدات الفصائل</option></select><div style="display:flex;gap:8px;"><div style="flex:1;"><div class="config-title">الحد الأقصى:</div><input type="number" name="max_tickets" value="{{ max_tickets }}" min="1"></div><div style="flex:1;"><div class="config-title">السرعة (ثانية):</div><input type="number" step="0.01" name="custom_speed" value="{{ speed }}"></div></div><div class="config-title">نص الرد الافتراضي:</div><textarea name="custom_msg">{{ message }}</textarea><button type="submit" class="btn" style="background:var(--prim);">حفظ الإعدادات 💾</button></form></div><div style="display:flex;gap:8px;margin:10px 0;"><form action="/token" method="get" style="flex:1;"><button class="btn btn-secondary" style="margin:0;">🔑 التوكن</button></form><form action="/reset_all" method="post" onsubmit="return confirm('تصفير؟');" style="flex:1;"><button class="btn btn-secondary" style="margin:0;color:#ef4444;">🗑️ تصفير</button></form></div><div class="log-box" id="log_box">{% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div>النظام جاهز...</div>{% endfor %}</div><a href="/logout" style="color:#ef4444;text-decoration:none;font-size:12px;display:block;margin-top:15px;font-weight:700;">تسجيل خروج</a></div><div class="ghost-panel"><div class="ghost-header">👁️ التكتات المستلمة (Ghost Monitor)</div><div class="ticket-list" id="ticket_list"></div><div class="chat-box" id="chat_box"><div style="color:#475569;text-align:center;margin-top:50%;">اختر تكت من الأعلى لمراقبة الرسائل...</div></div></div><script>var ctx=document.getElementById('progressChart').getContext('2d');var myChart=new Chart(ctx,{type:'doughnut',data:{labels:['المنجز','المتبقي'],datasets:[{data:[{{ count }},{{ max_tickets - count if max_tickets - count > 0 else 0 }}],backgroundColor:['{{ theme_data.prim }}','rgba(255,255,255,0.05)'],borderWidth:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},cutout:'75%'}});let currentActiveTicket=null;function loadChat(ch_id){currentActiveTicket=ch_id;document.querySelectorAll('.tkt-btn').forEach(b=>b.classList.remove('active'));let btn=document.getElementById('btn_'+ch_id);if(btn)btn.classList.add('active');document.getElementById('chat_box').innerHTML='<div style="color:#475569;text-align:center;margin-top:50%;">جاري تحميل الرسائل...</div>';fetchChat();}async function fetchChat(){if(!currentActiveTicket)return;try{let res=await fetch('/api/chat/'+currentActiveTicket);let msgs=await res.json();if(msgs.error)return;let chatHtml='';msgs.forEach(m=>{let isBot=m.bot?'bot':'';let msgContent=m.content;let urlRegex=/(https?:\/\/[^\s]+)/g;msgContent=msgContent.replace(urlRegex,function(url){if(url.match(/\.(jpeg|jpg|gif|png|webp)$/i)){return `<br><img src="${url}" style="max-width:100%;border-radius:5px;margin-top:5px;"><br><a href="${url}" target="_blank" style="color:var(--prim);font-size:10px;">[رابط الصورة]</a>`;}return `<a href="${url}" target="_blank" style="color:var(--prim);text-decoration:underline;">${url}</a>`;});if(m.attachments&&m.attachments.length>0){m.attachments.forEach(att=>{if(att.url.match(/\.(jpeg|jpg|gif|png|webp)$/i)){msgContent+=`<br><img src="${att.url}" style="max-width:100%;border-radius:5px;margin-top:5px;">`;}msgContent+=`<br><a href="${att.url}" target="_blank" style="color:var(--prim);font-size:10px;">[مرفق: ${att.filename}]</a>`;});}chatHtml+=`<div class="msg ${isBot}"><div class="msg-author">${m.author}</div>${msgContent}</div>`;});if(chatHtml==='')chatHtml='<div style="color:#475569;text-align:center;margin-top:50%;">لا توجد رسائل بعد...</div>';document.getElementById('chat_box').innerHTML=chatHtml;}catch(e){}}setInterval(async()=>{