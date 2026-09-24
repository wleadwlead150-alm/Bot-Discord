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
ADMIN_CATEGORY_ID = "1353444395575414844"
MASTER_PASSWORD = "MR_EAGLE_99"

KNOWN_SERVERS = ["lynwood", "santa cruz", "bell", "glendale", "covina", "hills", "chico", "napa", "mesa"]

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
        "theme": "lynwood", "ai_enabled": False, "ai_pro_enabled": False, "ai_rules": "أحتاج مساعدة|تفضل كيف أخدمك",
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
                      count INTEGER, total_lifetime INTEGER)''')
        for col in ["webhook", "theme", "ai_enabled", "ai_pro_enabled", "ai_rules"]:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT ''")
            except: pass

        for u in USERS.keys():
            c.execute("SELECT username FROM users WHERE username=?", (u,))
            if not c.fetchone():
                filter_val = "administrative" if u == "isso" else "all"
                c.execute('''INSERT INTO users (username, token, proxy, message, reply_template, ticket_filter, speed, max_tickets, count, total_lifetime, webhook, theme, ai_enabled, ai_pro_enabled, ai_rules)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lynwood', 0, 0, 'أحتاج مساعدة|تفضل')''', 
                             (u, "", "", user_sessions[u]["message"], "default", filter_val, 1.5, 10, 0, 0, ""))
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
                user_sessions[uname]["ai_pro_enabled"] = bool(row_dict.get("ai_pro_enabled", 0))
                user_sessions[uname]["ai_rules"] = row_dict.get("ai_rules", "")

def save_db(uname):
    with db_lock:
        conn = sqlite3.connect('elite_system.db', check_same_thread=False)
        c = conn.cursor()
        d = user_sessions[uname]
        enc_token = cipher(d["token"], True)
        c.execute('''UPDATE users SET token=?, proxy=?, message=?, reply_template=?, ticket_filter=?, 
                     speed=?, max_tickets=?, count=?, total_lifetime=?, webhook=?, theme=?, ai_enabled=?, ai_pro_enabled=?, ai_rules=? WHERE username=?''',
                  (enc_token, d.get("proxy",""), d["message"], d["reply_template"], d["ticket_filter"],
                   d["speed"], d["max_tickets"], d["count"], d["total_lifetime"], d.get("webhook",""), 
                   d.get("theme","lynwood"), int(d["ai_enabled"]), int(d["ai_pro_enabled"]), d["ai_rules"], uname))
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

def send_typing_bg(session_http, url):
    try: session_http.post(url, timeout=2)
    except: pass

def safe_post(username, url, payload, current_speed, is_claim=False):
    d = user_sessions[username]
    http_session = d["http_session"]
    http_session.headers.update(get_secure_headers(d["token"]))
    
    try:
        if "messages" in url and "typing" not in url and not is_claim:
            typing_url = f"{API}/{url.split('/channels/')[1].split('/')[0]}/typing"
            threading.Thread(target=send_typing_bg, args=(http_session, typing_url)).start()
            
        time.sleep(current_speed)
        res = http_session.post(url, json=payload, timeout=5)
        
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

def find_target_channel(http_session, token, server_name):
    if not server_name or server_name == "default": return None
    try:
        headers = get_secure_headers(token)
        res = http_session.get(f"https://discord.com/api/v9/guilds/{SERVER_ID}/channels", headers=headers, timeout=5)
        if res.status_code == 200:
            channels = res.json()
            search_key = server_name.lower().replace(" ", "-")
            target_id = None
            
            for c in channels:
                c_name = c.get("name", "").lower()
                if c.get("type") == 0 and "طلبات" in c_name and search_key in c_name:
                    target_id = c["id"]
                    break
            
            if not target_id:
                for c in channels:
                    c_name = c.get("name", "").lower()
                    if c.get("type") == 0 and "شات" in c_name and search_key in c_name:
                        target_id = c["id"]
                        break
            return target_id
    except: pass
    return None

def ai_worker(username, ch_id, ticket_name):
    d = user_sessions[username]
    http_session = d["http_session"]
    ai_on = d.get("ai_enabled")
    ai_pro_on = d.get("ai_pro_enabled")
    if not (ai_on or ai_pro_on): return

    server_name = "default"
    player_name = "غير معروف"
    ticket_number = re.sub(r'\D', '', ticket_name)
    if not ticket_number: ticket_number = ticket_name

    try:
        time.sleep(1.5) 
        init_res = http_session.get(f"{API}/{ch_id}/messages?limit=10", timeout=5)
        if init_res.status_code == 200:
            msgs = init_res.json()
            for m in msgs:
                if m.get("author", {}).get("bot", False): 
                    content = m.get("content", "").lower()
                    embeds = str(m.get("embeds", [])).lower()
                    for srv in KNOWN_SERVERS:
                        if srv in embeds or srv in content:
                            server_name = srv
                            break
                    mentions = m.get("mentions", [])
                    if mentions: player_name = mentions[0].get("username", "غير معروف")
    except Exception: pass

    last_msg_id = None
    ai_pro_state = 0 

    for _ in range(60): 
        time.sleep(3)
        if not d["running"]: break
        try:
            res = http_session.get(f"{API}/{ch_id}/messages?limit=5", timeout=5)
            if res.status_code == 200:
                msgs = res.json()
                for m in msgs:
                    if m["id"] == last_msg_id: continue 
                    
                    if not m.get("author", {}).get("bot", False) and m.get("author", {}).get("username") != username:
                        player_text = m.get("content", "").lower()
                        last_msg_id = m["id"]
                        
                        if ai_on and not ai_pro_on and d.get("ai_rules"):
                            rules = d["ai_rules"].split('\n')
                            for rule in rules:
                                if '|' in rule:
                                    keyword, reply = rule.split('|', 1)
                                    if keyword.strip().lower() in player_text:
                                        time.sleep(2) 
                                        safe_post(username, f"{API}/{ch_id}/messages", {"content": reply.strip()}, 1.5)
                                        d["logs"].insert(0, f"🤖 [AI] رصد الكلمة، تم الرد.")
                                        ai_on = False 
                                        break
                        
                        if ai_pro_on:
                            if ai_pro_state == 0:
                                time.sleep(2) 
                                safe_post(username, f"{API}/{ch_id}/typing", {}, 0)
                                time.sleep(1)
                                
                                if any(word in player_text for word in ["حظر", "حضر", "باند", "فك"]):
                                    reply_msg = "** اهلاً عزيزي قم برفق الصوره الدليل مع اسمك داخل الخادم **"
                                    safe_post(username, f"{API}/{ch_id}/messages", {"content": reply_msg}, 0)
                                    d["logs"].insert(0, "👑 [AI Pro] مسار طلب حظر.")
                                    ai_pro_state = 1
                                    break
                                
                                elif any(word in player_text for word in ["شكوى", "شكى", "سب", "شتيمه", "شتم", "نصب", "دي ام"]):
                                    reply_msg = "** اهلاً عزيزي ارجو منك إرفاق الدليل مع اسم لاعب **"
                                    safe_post(username, f"{API}/{ch_id}/messages", {"content": reply_msg}, 0)
                                    d["logs"].insert(0, "👑 [AI Pro] مسار طلب شكوى.")
                                    ai_pro_state = 2
                                    break

                            elif ai_pro_state == 1 or ai_pro_state == 2:
                                urls = re.findall(r'(https?://[^\s]+)', player_text)
                                attachments = m.get("attachments", [])
                                evidence_url = urls[0] if urls else (attachments[0].get("url") if attachments else None)
                                
                                if evidence_url:
                                    time.sleep(2)
                                    safe_post(username, f"{API}/{ch_id}/typing", {}, 0)
                                    time.sleep(1)
                                    thanks_msg = "__شكرًا لإرسال المعلومات المطلوبة :__\n```جاري العمل على الشكوى ⏱️ طلبك الآن قيد المراجعة من قبل الفريق المختص. سنقوم بإبلاغك فور اتخاذ أي إجراء بخصوص الشكوى. ⏳ يرجى التحلي بالصبر، وسنعود إليك في أقرب وقت ممكن. 
