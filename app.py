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
        
        remaining = int(res.headers.get('X-RateLimit-Remaining', 5))
        if remaining <= 2: time.sleep(0.2) 
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

    with anti_clash_lock:
        now = time.time()
        if now - last_global_claim_ts < 0.05: time.sleep(random.uniform(0.05, 0.1))
        last_global_claim_ts = time.time()

    msg_list = [m.strip() for m in session_data["message"].split('||') if m.strip()]
    custom_msg = random.choice(msg_list) if msg_list else "استلمت التكت."
    
    res = safe_post(username, f"{API}/{ch_id}/messages", {"content": custom_msg}, session_data["speed"], is_claim=True)
    
    with session_data["lock"]:
        if res and res.status_code in [200, 201]:
            log_ticket(username, ch_id)
            t_time = datetime.now().strftime("%I:%M %p")
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
