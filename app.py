import os
import time
import requests
import threading
from flask import Flask

# إعداد سيرفر فلاسك الوهمي ليبقى التطبيق شغلاً على رندر
app = Flask("")

@app.route("/")
def home():
    return "Bot is running successfully!"

API = "https://discord.com/api/v10/channels"

def get_secure_headers(token):
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

def check_ticket_for_user(token, ch_id, username):
    """
    تقوم بفحص التذكرة وتوجيهها حسب اسم الإداري (Isso أو Osama أو غيرهم):
    - إذا كان الحساب لـ Isso أو Osama: يقبل فقط الشكاوى ضد الإداريين ويرفض شكاوى اللاعبين.
    - إذا كان الحساب لأي إداري آخر: يقبل شكاوى اللاعبين ويرفض الشكاوى الإدارية.
    """
    headers = get_secure_headers(token)
    for _ in range(3):
        try:
            res = requests.get(f"{API}/{ch_id}/messages?limit=5", headers=headers, timeout=4)
            if res.status_code == 200:
                messages = res.json()
                if messages:
                    embed_text = ""
                    for m in messages:
                        for embed in m.get("embeds", []):
                            embed_text += " " + embed.get("title", "") + " " + embed.get("description", "")
                            for field in embed.get("fields", []):
                                embed_text += " " + field.get("name", "") + " " + field.get("value", "")
                    
                    embed_text = embed_text.lower()
                    
                    # التحقق مما إذا كانت التذكرة تخص إداريين أم لاعبين
                    admin_keywords = ["اداري", "إداري", "مشرف", "مراقب", "سوبر فايزر", "supervisor", "helper", "admin", "moderator"]
                    is_admin_complaint = any(kw in embed_text for kw in admin_keywords)
                    
                    is_player_complaint = "شكاوي اللاعبين" in embed_text or "شكاوى اللاعبين" in embed_text

                    # تحديد اسم الحساب الحالي (نحول الاسم إلى حروف صغيرة للمقارنة الدقيقة)
                    current_user = username.lower()
                    
                    # إذا كان الحساب لـ Isso أو Osama
                    if "isso" in current_user or "osama" in current_user:
                        # يستلمون فقط الشكاوى ضد الإداريين، ويرفضون شكاوى اللاعبين
                        if is_admin_complaint and not is_player_complaint:
                            return True
                        return False
                    
                    else:
                        # الباقون: يستلمون شكاوى اللاعبين ويرفضون الشكاوى ضد الإداريين
                        if is_player_complaint and not is_admin_complaint:
                            return True
                        return False
                else:
                    time.sleep(1.0)
            else:
                break
        except Exception:
            time.sleep(1.0)
            
    return False

# تشغيل سيرفر فلاسك في الخلفية لمنع خروج التطبيق على رندر
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()

    print("Bot wrapper started successfully.")
    while True:
        time.sleep(10)
