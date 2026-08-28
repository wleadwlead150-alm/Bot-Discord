import json
import re
import time
import requests
import websocket
import threading
import random
import os
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "marshall_secret_key_ultra_luxury_v13"

USERS = {
    "Marshall": "oopp0099",
    "Bolana": "oopp00998",
    "Osama": "oopp009987",
    "Kara": "oopp009988",
    "Isso": "1234"
}

SERVER_ID = "1272600775331414159"
API = "https://discord.com/api/v9/channels"

LOG_CHANNELS = {
    "Osama": "1542223899792510996",
    "Marshall": "1542223986388107264",
    "Isso": "1542223986388107264"
}

DEVICE_PROFILES = [
    {
        "User-Agent": "Discord/188215 CFNetwork/1498.700.2 Darwin/23.4.0",
        "X-Super-Properties": "eyJvcyI6IiOSyIsImJyb3dzZXIiOiJEaXNjb3JkIENsaWVudCIsImRldmljZSI6ImlQaG9uZSAxMywgcHJvLCBtYXgiLCJzeXN0ZW1fdmVyc2lvbiI6IjE3LjUif="
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "X-Super-Properties": "eyJvcyI6ImlPUyIsImJyb3dzZXIiOiJkaXNjb3JkIiwiZGV2aWNlIjoiaVBob25lIiwic3lzdGVtX3ZlcnNpb24iOiIxNy40LjEif="
    }
]

user_sessions = {
    "Marshall": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "مرحباً عزيزي لاعب معك مرشال من فريق الإداري كيف يمكنني مساعدتك",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False
    },
    "Bolana": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "** أهلاً بك معك بولانا من فريق الإدارة كيف أساعدك **",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False
    },
    "Osama": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "** أهلاً بك معك أسامة، مختص حصراً بشكاوى الإداريين **",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False
    },
    "Kara": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "** أهلاً بك معك كارا من فريق الإدارة كيف أساعدك **",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False
    },
    "Isso": {
        "running": False, "speed": 0.05, "thread": None, "token": "",
        "message": "** أهلاً بك معك Isso، مختص حصراً باستلام الشكاوى ضد الإداريين والمشرفين **",
        "reply_template": "default",
        "logs": [], "count": 0, "total_lifetime": 0, "max_tickets": 5, "cooldown_mode": False, "skip_next": False, "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False
    }
}

master_global_audit = []
security_audit_logs = []
active_tickets = set()
state_lock = threading.Lock()

REPLY_TEMPLATES = {
    "default": "", 
    "evidence_req": "عزيزي الشكاوي اللي تكون فيها دلائل بهذي الطريقه لها متطلبات اتمنى منك اكمالها\n-# ** تفتح تصوير مقطع تظهر فيه جميع السيرفرات بعدها تدخل الخادم الخاص بك وتدخل الشنطه وتحط الجواز على شخصيتك ** .",
    "review_wait": "أهلاً عزيزي جاري مراجعة طلبك تحلى بالصبر\n\n-# **نحن نعمل لخدمتكم**",
    "ban_evidence": "أهلاً عزيزي نرجو الانتظار جاري طلب دليل حظرك من إدارة الخادم"
}

def get_secure_headers(token):
    profile = random.choice(DEVICE_PROFILES)
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": profile["User-Agent"],
        "X-Super-Properties": profile["X-Super-Properties"],
        "X-Discord-Locale": "ar"
    }

def check_token_health(token):
    if not token:
        return "❌ التوكن فارغ غير مدخل"
    try:
        headers = get_secure_headers(token)
        res = requests.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=5)
        if res.status_code == 200:
            user_data = res.json()
            tag = f"{user_data.get('username')}#{user_data.get('discriminator', '0')}"
            return f"✅ التوكن سليم وشغال تمام ({tag})"
        elif res.status_code == 401:
            return "❌ التوكن غير صالح أو منتهي الصلاحية (401 Unauthorized)"
        else:
            return f"⚠️ استجابة غير متوقعة من الديسكورد (كود: {res.status_code})"
    except Exception as e:
        return f"❌ خطأ في الاتصال بالشبكة فحص التوكن: {str(e)}"

def safe_post(token, url, payload, current_speed, username=None):
    try:
        headers = get_secure_headers(token)
        res = requests.post(url, json=payload, headers=headers, timeout=3)
        if res.status_code == 429:
            if username and username in user_sessions:
                with state_lock:
                    user_sessions[username]["rate_limit_errors"] += 1
                    if user_sessions[username]["rate_limit_errors"] >= 3:
                        user_sessions[username]["running"] = False
                        user_sessions[username]["banned_secure"] = True
                        user_sessions[username]["logs"].append("🚨 [Auto-Snooze & Lockout] تم كتم البوت وإيقافه تلقائياً لحماية الحساب بعد تكرار 3 أخطاء (Rate Limit).")
                        security_audit_logs.insert(0, f"⚠️ نظام الأمان (Auto-Snooze): تم كتم وإيقاف الحساب <b>{username}</b> تلقائياً لتجاوز حد الأخطاء.")
            retry_after = res.json().get("retry_after", current_speed)
            time.sleep(retry_after)
            return safe_post(token, url, payload, current_speed, username)
        return res
    except Exception:
        return None

def check_ticket_content_for_complaint(token, ch_id, username):
    headers = get_secure_headers(token)
    for _ in range(3):
        try:
            res = requests.get(f"{API}/{ch_id}/messages?limit=5", headers=headers, timeout=4)
            if res.status_code == 200:
                messages = res.json()
                if messages:
                    combined_text = ""
                    for m in messages:
                        combined_text += " " + m.get("content", "")
                        for embed in m.get("embeds", []):
                            combined_text += " " + embed.get("title", "") + " " + embed.get("description", "")
                    
                    combined_text = combined_text.lower()
                    admin_keywords = ["اداري", "إداري", "مشرف", "helper", "مراقب", "سوبر فايزر", "supervisor", "admin", "moderator"]
                    return any(kw in combined_text for kw in admin_keywords)
                else:
                    time.sleep(1.0)
            else:
                break
        except Exception:
            time.sleep(1.0)
    return False

def process_ticket(username, token, ch_id, name):
    if username in ["Isso", "Osama"]:
        is_admin_complaint = check_ticket_content_for_complaint(token, ch_id, username)
        if not is_admin_complaint:
            return  
    else:
        is_admin_complaint = check_ticket_content_for_complaint(token, ch_id, "Isso")
        if is_admin_complaint:
            return  

    with state_lock:
        session_data = user_sessions[username]
        if not session_data["running"] or session_data["banned_secure"]:
            return
            
        if session_data["cooldown_mode"]:
            if session_data["skip_next"]:
                session_data["skip_next"] = False
                session_data["logs"].append(f"⚡ [Cooldown] تم تخطي التكت `#{name}` بنجاح.")
                return
            else:
                session_data["skip_next"] = True

        if session_data["count"] >= session_data["max_tickets"]:
            session_data["running"] = False
            return
        if ch_id in active_tickets:
            return
        active_tickets.add(ch_id)

    current_speed = session_data["speed"]
    
    tpl_key = session_data.get("reply_template", "default")
    if tpl_key != "default" and tpl_key in REPLY_TEMPLATES:
        custom_msg = REPLY_TEMPLATES[tpl_key]
    else:
        custom_msg = session_data["message"]
    
    time.sleep(current_speed)
    
    res = safe_post(token, f"{API}/{ch_id}/messages", {"content": custom_msg}, current_speed, username)
    
    with state_lock:
        if res and res.status_code in [200, 201]:
            ticket_url = f"https://discord.com/channels/{SERVER_ID}/{ch_id}"
            log_text = f"🎯 تم استلام تكت **#{name}** | <a href='{ticket_url}' target='_blank'>رابط التكت</a>"
            
            global master_global_audit
            audit_entry = f"[{username}] استلم تكت <b>#{name}</b> | <a href='{ticket_url}' target='_blank'>رابط</a>"
            master_global_audit.insert(0, audit_entry)
            if len(master_global_audit) > 50:
                master_global_audit.pop()
            
            if username in LOG_CHANNELS:
                alert_channel_id = LOG_CHANNELS[username]
                alert_payload = {"content": f"🚨 **{username}** استلم تكت جديد:\n• اسم التكت: `#{name}`\n• الرابط: {ticket_url}"}
                safe_post(token, f"{API}/{alert_channel_id}/messages", alert_payload, current_speed, username)

            if session_data["count"] < session_data["max_tickets"]:
                session_data["count"] += 1
                session_data["total_lifetime"] += 1
                session_data["logs"].append(f"{log_text} (العدد: {session_data['count']}/{session_data['max_tickets']})")
                if session_data["count"] >= session_data["max_tickets"]:
                    session_data["running"] = False
                    session_data["logs"].append("🛑 تم الوصول للحد الأقصى المحدد من التكتات، توقف البوت.")
        else:
            status_code = res.status_code if res else "خطأ اتصال"
            session_data["logs"].append(f"<span style='color: #ef4444;'>❌ خطأ في استلاستكت #{name} (كود الحالة: {status_code})</span>")
        
    with state_lock:
        if ch_id in active_tickets:
            active_tickets.remove(ch_id)

def run_discord_bot(username):
    token = user_sessions[username]["token"]
    
    def on_message(ws, msg):
        if not user_sessions[username]["running"] or user_sessions[username]["banned_secure"]:
            ws.close()
            return
        try:
            raw = json.loads(msg)
            if raw.get("op") == 10:
                ws.send(json.dumps({"op": 1, "d": None}))
                
            if raw.get("t") == "CHANNEL_CREATE":
                d = raw.get("d", {})
                if d.get("guild_id") == SERVER_ID and d.get("type") == 0:
                    name = d.get("name", "").lower()
                    ch_id = d.get("id")
                    created_at = ((int(ch_id) >> 22) + 1420070400000) / 1000.0
                    if time.time() - created_at > 120:
                        return
                    with state_lock:
                        if user_sessions[username]["count"] >= user_sessions[username]["max_tickets"] or not user_sessions[username]["running"]:
                            return
                    threading.Thread(target=process_ticket, args=(username, token, ch_id, name)).start()
        except Exception:
            pass

    def on_open(ws):
        payload = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {"os": "ios", "browser": "discord", "device": "phone"},
                "intents": 1 << 0
            }
        }
        ws.send(json.dumps(payload))

    ws_url = "wss://gateway.discord.gg/?v=9&encoding=json"
    while user_sessions[username]["running"] and not user_sessions[username]["banned_secure"]:
        try:
            ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message)
            ws.run_forever()
        except Exception:
            time.sleep(1)

PANEL_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة التحكم المرعبة - الفضاء الأسود والأحمر الدموي</title>
    <style>
        body { background: radial-gradient(circle at center, #0f0202 0%, #030303 100%); color: #f1f5f9; font-family: Tahoma, sans-serif; text-align: center; margin: 0; padding: 15px; min-height: 100vh; }
        .card { background: linear-gradient(180deg, #0d0404 0%, #030202 100%); max-width: 440px; margin: 0 auto; padding: 22px; border-radius: 18px; border: 1px solid #7f1d1d; box-shadow: 0 25px 50px rgba(0,0,0,0.95), 0 0 35px rgba(220, 38, 38, 0.2); }
        .logo-glow { width: 75px; height: 75px; margin: 0 auto 10px auto; background: linear-gradient(135deg, #dc2626, #7f1d1d); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 32px; box-shadow: 0 0 20px rgba(220, 38, 38, 0.6); border: 2px solid #f87171; }
        h1 { color: #ef4444; font-size: 19px; margin-bottom: 2px; text-shadow: 0 2px 10px rgba(239, 68, 68, 0.5); }
        .user-tag { color: #34d399; font-size: 13px; margin-bottom: 12px; font-weight: bold; letter-spacing: 0.5px; }
        .speed-badge { background: #050202; border: 1px solid #450a0a; padding: 10px; border-radius: 10px; font-size: 12px; color: #fca5a5; margin-bottom: 8px; box-shadow: inset 0 2px 5px rgba(0,0,0,0.8); }
        .stats-badge { background: #050202; border: 1px solid #450a0a; padding: 6px; border-radius: 8px; font-size: 11px; color: #38bdf8; margin-bottom: 12px; }
        .btn { display: block; width: 100%; padding: 12px; margin: 8px 0; font-size: 14px; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; text-decoration: none; transition: all 0.2s ease; }
        .btn:active { transform: scale(0.98); }
        .btn-start { background: linear-gradient(135deg, #059669, #047857); color: white; box-shadow: 0 4px 15px rgba(5, 150, 105, 0.4); }
        .btn-stop { background: linear-gradient(135deg, #dc2626, #991b1b); color: white; box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4); }
        .btn-turbo { background: linear-gradient(135deg, #7c3aed, #5b21b6); color: white; box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4); }
        .btn-cooldown-on { background: linear-gradient(135deg, #2563eb, #1e40af); color: white; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4); }
        .btn-cooldown-off { background: linear-gradient(135deg, #181212, #261919); color: #94a3b8; border: 1px solid #475569; }
        .btn-silent-on { background: linear-gradient(135deg, #9a3412, #7c2d12); color: white; box-shadow: 0 4px 15px rgba(154, 52, 18, 0.4); }
        .btn-silent-off { background: linear-gradient(135deg, #181212, #261919); color: #94a3b8; border: 1px solid #475569; }
        .btn-reset { background: linear-gradient(135deg, #b45309, #78350f); color: white; box-shadow: 0 4px 15px rgba(180, 83, 9, 0.4); }
        .btn-clear { background: linear-gradient(135deg, #334155, #1e293b); color: #f87171; border: 1px solid #475569; }
        .btn-token { background: linear-gradient(135deg, #0284c7, #0369a1); color: white; }
        .btn-emergency { background: linear-gradient(135deg, #7f1d1d, #450a0a); color: #fecaca; border: 1px solid #ef4444; }
        .speed-row { display: flex; justify-content: space-between; gap: 6px; margin: 4px 0; }
        .btn-speed-up, .btn-speed-down { flex: 1; padding: 8px; background: #080303; border: 1px solid #450a0a; color: #34d399; font-size: 12px; font-weight: bold; border-radius: 8px; cursor: pointer; transition: 0.2s; }
        .config-section { text-align: right; margin-top: 10px; background: #060202; padding: 10px; border-radius: 10px; border: 1px solid #450a0a; }
        .config-title { color: #f87171; font-size: 11px; margin-bottom: 4px; font-weight: bold; }
        input[type="text"], input[type="password"], input[type="number"], textarea, select { width: 100%; padding: 8px; background: #020101; border: 1px solid #450a0a; color: #f1f5f9; border-radius: 8px; box-sizing: border-box; font-size: 11px; text-align: center; outline: none; margin-bottom: 5px; }
        textarea { height: 55px; text-align: right; resize: none; }
        .btn-save { width: 100%; padding: 8px; margin-top: 4px; background: linear-gradient(135deg, #b45309, #78350f); color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 11px; }
        .log-title { color: #f87171; font-size: 11px; margin-top: 10px; text-align: right; font-weight: bold; }
        .log-box { background: #020101; border: 1px solid #450a0a; border-radius: 9px; padding: 8px; height: 95px; overflow-y: auto; text-align: right; font-size: 10px; color: #94a3b8; margin-top: 4px; box-shadow: inset 0 2px 6px rgba(0,0,0,0.9); }
        .log-box a { color: #38bdf8; text-decoration: underline; }
        .logout-btn { color: #ef4444; font-size: 11px; display: block; margin-top: 14px; text-decoration: none; font-weight: bold; }
        .section-box { border: 1px dashed #7f1d1d; border-radius: 12px; padding: 10px; margin-top: 12px; background: #060202; text-align: right; }
    </style>
    <script>
        function confirmReset() { return confirm("هل تريد إعادة تعيين التكتات والأخطاء بالكامل؟"); }
        function confirmEmergency() { return confirm("⚠️ تحذير: هل أنت متأكد من إيقاف جميع البوتات لكل الحسابات فوراً؟"); }
    </script>
</head>
<body>
    <div class="card">
        <div class="logo-glow">⚡</div>
        <h1>لوحة التحكم المرعبة</h1>
        <div class="user-tag">الحساب النشط: {{ username }}</div>
        
        <div class="speed-badge">تم استلام: <b>{{ count }}/{{ max_tickets }}</b> | السرعة: <b>{{ speed }}ث</b></div>
        <div class="stats-badge">📊 إجمالي الإنجاز التراكمي: <b>{{ total_lifetime }} تكت</b> | الأخطاء: <b>{{ rate_errors }}</b></div>
        
        <form action="/toggle" method="post">
            {% if running %}
                <button type="submit" class="btn btn-stop">إيقاف البوت 🛑</button>
            {% else %}
                <button type="submit" class="btn btn-start">تشغيل البوت 🚀</button>
            {% endif %}
        </form>

        <form action="/turbo" method="post">
            <button type="submit" class="btn btn-turbo">⚡ تفعيل وضع التيربو الخارق (0.01ث)</button>
        </form>

        <div class="speed-row">
            <form action="/speed/up" method="post" style="flex:1; display:inline;"><button type="submit" class="btn-speed-up">⚡ تسريع (-)</button></form>
            <form action="/speed/down" method="post" style="flex:1; display:inline;"><button type="submit" class="btn-speed-down">⏳ إبطاء (+)</button></form>
        </div>

        <form action="/toggle_cooldown" method="post">
            {% if cooldown_mode %}
                <button type="submit" class="btn btn-cooldown-on">🛡️ نظام التخطي (مفعل: يستلم ويخط)</button>
            {% else %}
                <button type="submit" class="btn btn-cooldown-off">🛡️ نظام التخطي (معطل: استلام الكل)</button>
            {% endif %}
        </form>

        <form action="/toggle_silent" method="post">
            {% if silent_mode %}
                <button type="submit" class="btn btn-silent-on">🔇 الوضع الصامت (مفعل)</button>
            {% else %}
                <button type="submit" class="btn btn-silent-off">🔊 الوضع الصامت (معطل)</button>
            {% endif %}
        </form>

        <div class="config-section">
            <form action="/update_settings" method="post">
                <div class="config-title">تحديد حد التكتات الأقصى:</div>
                <input type="number" name="max_tickets" value="{{ max_tickets }}" min="1" max="100">
                
                <div class="config-title">تحديد سرعة البوت بالثواني (يدوياً لحد 0.001):</div>
                <input type="number" step="0.001" name="custom_speed" value="{{ speed }}" min="0.001" max="10.0" style="margin-bottom: 5px;">

                <div class="config-title">اختر قالب الرد السريـع:</div>
                <select name="reply_template" style="margin-bottom: 6px;">
                    <option value="default" {% if reply_template == 'default' %}selected{% endif %}>الرسالة المخصصة (أسفله)</option>
                    <option value="evidence_req" {% if reply_template == 'evidence_req' %}selected{% endif %}>طلب دلائل الشكاوى (تصوير السيرفرات والجواز)</option>
                    <option value="review_wait" {% if reply_template == 'review_wait' %}selected{% endif %}>جاري مراجعة الطلب (تحلى بالصبر)</option>
                    <option value="ban_evidence" {% if reply_template == 'ban_evidence' %}selected{% endif %}>طلب دليل الحظر من إدارة الخادم</option>
                </select>

                <div class="config-title">أو تخصيص نص الرسالة يدوياً:</div>
                <textarea name="custom_msg">{{ message }}</textarea>
                <button type="submit" class="btn-save">حفظ الإعدادات 💾</button>
            </form>
        </div>

        <form action="/reset_all" method="post" onsubmit="return confirmReset();"><button type="submit" class="btn btn-reset">🗑️ إعادة تعيين التكتات والأخطاء</button></form>
        <form action="/clear_logs" method="post"><button type="submit" class="btn btn-clear">🧹 تفريغ السجل فقط</button></form>
        
        <div style="display: flex; gap: 6px; margin: 8px 0;">
            <form action="/token" method="get" style="flex:1;"><button type="submit" class="btn btn-token" style="margin:0;">🔑 تعديل التوكن</button></form>
            <form action="/check_token" method="post" style="flex:1;"><button type="submit" class="btn" style="margin:0; background: linear-gradient(135deg, #047857, #065f46);">🔍 فحص صحة التوكن</button></form>
        </div>

        {% if username == "Marshall" %}
        <div class="section-box">
            <div class="config-title" style="color: #ef4444; font-size: 12px; margin-bottom: 8px;">👑 لوحة القيادة العليا (Marshall Admin):</div>
            <form action="/emergency_stop" method="post" onsubmit="return confirmEmergency();" style="margin-bottom: 8px;"><button type="submit" class="btn btn-emergency">🚨 طوارئ عامة (إيقاف كل الحسابات)</button></form>
            <form action="/create_account" method="post" style="background: #020101; padding: 8px; border-radius: 8px; border: 1px solid #7f1d1d; margin-bottom: 8px;">
                <div class="config-title">➕ إنشاء حساب جديد للنظام:</div>
                <input type="text" name="new_user" placeholder="اسم المستخدم" required>
                <input type="password" name="new_pass" placeholder="الرمز السري" required>
                <textarea name="new_token" placeholder="التوكن..." style="height: 40px;" required></textarea>
                <button type="submit" class="btn-save" style="background: linear-gradient(135deg, #059669, #047857);">إنشاء الحساب 🚀</button>
            </form>
            <form action="/manage_member_action" method="post" style="background: #020101; padding: 8px; border-radius: 8px; border: 1px solid #7f1d1d; margin-bottom: 8px;">
                <div class="config-title">👥 إدارة الأعضاء والتحكم الفردي:</div>
                <select name="target_member" style="margin-bottom: 6px;">
                    {% for member in all_users %}<option value="{{ member }}">{{ member }}</option>{% endfor %}
                </select>
                <div style="display: flex; gap: 5px;">
                    <button type="submit" name="action_type" value="stats" class="btn-save" style="background: #2563eb; flex: 1;">الإحصائيات 📊</button>
                    <button type="submit" name="action_type" value="kick" class="btn-save" style="background: #dc2626; flex: 1;" onclick="return confirm('طرد نهائي؟');">طرد 🚪</button>
                </div>
            </form>
            {% if selected_member_info %}<div style="margin-top: 6px; font-size: 10px; color: #34d399; font-weight: bold; background: #020101; padding: 6px; border-radius: 6px; border: 1px solid #7f1d1d;">{{ selected_member_info | safe }}</div>{% endif %}
            <div class="config-title" style="color: #38bdf8; margin-top: 10px;">🛡️ سجل الأمان (Auto-Snooze):</div>
            <div class="log-box" style="height: 75px; border-color: #1e3a8a;">
                {% for sec in security_logs %}<div>• {{ sec | safe }}</div>{% else %}<div style="color: #444; text-align: center; margin-top: 20px;">لا توجد تنبيهات...</div>{% endfor %}
            </div>
            <div class="config-title" style="color: #38bdf8; margin-top: 10px;">🌐 سجل العمليات العام:</div>
            <div class="log-box" style="height: 90px; border-color: #1e3a8a;">
                {% for item in global_audit %}<div>• {{ item | safe }}</div>{% else %}<div style="color: #444; text-align: center; margin-top: 25px;">لا توجد تكتات...</div>{% endfor %}
            </div>
        </div>
        {% endif %}

        <div class="log-title">سجل العمليات والأخطاء البصرية:</div>
        <div class="log-box">
            {% for item in logs %}<div>• {{ item | safe }}</div>{% else %}<div style="color: #444; text-align: center; margin-top: 25px;">لا توجد عمليات مسجلة...</div>{% endfor %}
        </div>
        <a href="/logout" class="logout-btn">تسجيل خروج من الحساب 🚪</a>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تسجيل الدخول</title>
<style>body{background:#030303;color:#fff;font-family:Tahoma;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.card{background:#0d0404;width:320px;padding:22px;border-radius:14px;border:1px solid #7f1d1d;box-shadow:0 15px 35px rgba(0,0,0,0.9)}input{width:100%;padding:10px;margin:8px 0;background:#020101;border:1px solid #450a0a;color:#fff;border-radius:8px;text-align:center;box-sizing:border-box;outline:none}.btn{width:100%;padding:11px;margin-top:10px;background:linear-gradient(135deg, #dc2626, #991b1b);color:#fff;border:none;border-radius:8px;font-weight:bold;cursor:pointer}</style></head>
<body><div class="card"><h2 style="color:#ef4444; margin-top:0;">تسجيل الدخول</h2><form method="POST"><input type="text" name="username" placeholder="اسم المستخدم" required><input type="password" name="password" placeholder="الرمز السري" required><button type="submit" class="btn">دخول للنظام</button></form></div></body></html>
"""

TOKEN_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تعديل التوكن</title>
<style>body{background:#030303;color:#fff;font-family:Tahoma;text-align:center;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.card{background:#0d0404;width:340px;padding:22px;border-radius:14px;border:1px solid #7f1d1d;box-shadow:0 15px 35px rgba(0,0,0,0.9)}textarea{width:100%;height:75px;background:#020101;border:1px solid #450a0a;color:#fff;border-radius:8px;text-align:center;resize:none;box-sizing:border-box;font-size:11px;outline:none}.btn{width:100%;padding:11px;margin-top:10px;background:linear-gradient(135deg, #0284c7, #0369a1);color:#fff;border:none;border-radius:8px;font-weight:bold;cursor:pointer}</style></head>
<body><div class="card"><h2 style="color:#38bdf8; margin-top:0;">تعديل توكن الحساب</h2><form method="POST"><textarea name="token" placeholder="الصق التوكن..." required></textarea><button type="submit" class="btn">حفظ وتحديث التوكن</button></form></div></body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            if username in user_sessions and user_sessions[username].get("kicked", False):
                return redirect(url_for('login'))
            session['user'] = username
            if not user_sessions[username]["token"]:
                return redirect(url_for('set_token'))
            return redirect(url_for('panel'))
    return render_template_string(LOGIN_HTML)

@app.route('/token', methods=['GET', 'POST'])
def set_token():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user_sessions[session['user']]["token"] = request.form.get('token').strip()
        user_sessions[session['user']]["logs"].append("🔑 تم تحديث وتعديل توكن الحساب بنجاح.")
        return redirect(url_for('panel'))
    return render_template_string(TOKEN_HTML)

@app.route('/check_token', methods=['POST'])
def check_token_route():
    if 'user' in session:
        usr = session['user']
        token = user_sessions[usr]["token"]
        result_msg = check_token_health(token)
        user_sessions[usr]["logs"].append(result_msg)
    return redirect(url_for('panel'))

@app.route('/panel')
def panel():
    if 'user' not in session or not user_sessions[session['user']]["token"]: return redirect(url_for('login'))
    usr = session['user']
    data = user_sessions[usr]
    selected_member_info = session.get('selected_member_info', None)
    return render_template_string(
        PANEL_HTML, username=usr, running=data["running"], speed=data["speed"], 
        message=data["message"], reply_template=data.get("reply_template", "default"),
        logs=data["logs"], count=data["count"], total_lifetime=data["total_lifetime"], 
        max_tickets=data["max_tickets"], cooldown_mode=data["cooldown_mode"], 
        silent_mode=data["silent_mode"], rate_errors=data["rate_limit_errors"], 
        all_users=list(user_sessions.keys()), selected_member_info=selected_member_info, 
        global_audit=master_global_audit, security_logs=security_audit_logs
    )

@app.route('/toggle', methods=['POST'])
def toggle():
    if 'user' in session:
        usr = session['user']
        data = user_sessions[usr]
        if not data["running"] and not data["banned_secure"]:
            if data["token"]:
                if data["count"] >= data["max_tickets"]:
                    data["count"] = 0
                data["running"] = True
                t = threading.Thread(target=run_discord_bot, args=(usr,))
                t.daemon = True
                t.start()
        else:
            data["running"] = False
    return redirect(url_for('panel'))

@app.route('/turbo', methods=['POST'])
def turbo():
    if 'user' in session:
        user_sessions[session['user']]["speed"] = 0.01
        user_sessions[session['user']]["logs"].append("⚡ تم تفعيل وضع التيربو الخارق (0.01ث).")
    return redirect(url_for('panel'))

@app.route('/toggle_cooldown', methods=['POST'])
def toggle_cooldown():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["cooldown_mode"] = not user_sessions[usr]["cooldown_mode"]
        user_sessions[usr]["skip_next"] = False
    return redirect(url_for('panel'))

@app.route('/toggle_silent', methods=['POST'])
def toggle_silent():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["silent_mode"] = not user_sessions[usr]["silent_mode"]
    return redirect(url_for('panel'))

@app.route('/reset_all', methods=['POST'])
def reset_all():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["count"] = 0
        user_sessions[usr]["rate_limit_errors"] = 0
        user_sessions[usr]["banned_secure"] = False
        user_sessions[usr]["logs"] = []
    return redirect(url_for('panel'))

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    if 'user' in session:
        user_sessions[session['user']]["logs"] = []
    return redirect(url_for('panel'))

@app.route('/emergency_stop', methods=['POST'])
def emergency_stop():
    if 'user' in session and session['user'] == "Marshall":
        for u in user_sessions:
            user_sessions[u]["running"] = False
    return redirect(url_for('panel'))

@app.route('/create_account', methods=['POST'])
def create_account():
    if 'user' in session and session['user'] == "Marshall":
        new_u = request.form.get('new_user', '').strip()
        new_p = request.form.get('new_pass', '').strip()
        new_t = request.form.get('new_token', '').strip()
        if new_u and new_p:
            USERS[new_u] = new_p
            user_sessions[new_u] = {
                "running": False, "speed": 0.05, "thread": None, "token": new_t,
                "message": f"أهلاً بك معك {new_u} من فريق الإدارة كيف أساعدك",
                "reply_template": "default", "logs": [], "count": 0, "total_lifetime": 0, 
                "max_tickets": 5, "cooldown_mode": False, "skip_next": False, 
                "silent_mode": False, "rate_limit_errors": 0, "banned_secure": False
            }
    return redirect(url_for('panel'))

@app.route('/manage_member_action', methods=['POST'])
def manage_member_action():
    if 'user' in session and session['user'] == "Marshall":
        target = request.form.get('target_member')
        action = request.form.get('action_type')
        if target in user_sessions:
            if action == 'stats':
                d = user_sessions[target]
                session['selected_member_info'] = f"({target}): إجمالي <b>{d['total_lifetime']}</b>، الحالي <b>{d['count']}/{d['max_tickets']}</b>"
            elif action == 'kick' and target != "Marshall":
                user_sessions[target]["running"] = False
                user_sessions[target]["kicked"] = True
                user_sessions[target]["token"] = ""
    return redirect(url_for('panel'))

@app.route('/speed/up', methods=['POST'])
def speed_up():
    if 'user' in session:
        usr = session['user']
        if user_sessions[usr]["speed"] > 0.001:
            user_sessions[usr]["speed"] = round(max(0.001, user_sessions[usr]["speed"] - 0.01), 3)
    return redirect(url_for('panel'))

@app.route('/speed/down', methods=['POST'])
def speed_down():
    if 'user' in session:
        usr = session['user']
        user_sessions[usr]["speed"] = round(user_sessions[usr]["speed"] + 0.02, 3)
    return redirect(url_for('panel'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user' in session:
        usr = session['user']
        new_msg = request.form.get('custom_msg', '').strip()
        new_tpl = request.form.get('reply_template', 'default')
        user_sessions[usr]["reply_template"] = new_tpl
        try:
            new_max = int(request.form.get('max_tickets', 5))
            if new_max > 0: user_sessions[usr]["max_tickets"] = new_max
        except ValueError:
            pass
        try:
            new_speed = float(request.form.get('custom_speed', 0.05))
            if new_speed >= 0.001: user_sessions[usr]["speed"] = round(new_speed, 3)
        except ValueError:
            pass
        if new_msg: user_sessions[usr]["message"] = new_msg
    return redirect(url_for('panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('selected_member_info', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
