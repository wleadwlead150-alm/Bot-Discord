def check_ticket_content_for_complaint(token, ch_id, username):
    """
    تقوم هذه الدالة بفحص محتوى التذكرة للتأكد أنها (شكوى ضد إداري فقط)
    مع استبعاد شكاوى اللاعبين وشكاوى قادة الفصائل تماماً.
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
                    
                    # 1. إذا كانت التذكرة تخص شكاوى اللاعبين العادية أو قادة الفصائل -> نرفضها فوراً
                    player_or_leader_keywords = ["شكاوي اللاعبين", "شكاوى اللاعبين", "قائد", "فصيل", "ليدر", "leader"]
                    if any(kw in embed_text for kw in player_or_leader_keywords):
                        # استثناء: إذا كان الليدر مشمول بشكوى إدارية، نتحقق، وإلا فنستبعده
                        if not ("اداري" in embed_text or "إداري" in embed_text):
                            return False

                    # 2. يجب أن تحتوي حصراً على كلمات تخص الإداريين والمشرفين لاستلامها
                    admin_keywords = [
                        "اداري", "إداري", "مشرف", "مراقب", "سوبر فايزر", 
                        "supervisor", "helper", "admin", "moderator"
                    ]
                    
                    if any(kw in embed_text for kw in admin_keywords):
                        return True
                        
                    return False
                else:
                    time.sleep(1.0)
            else:
                break
        except Exception:
            time.sleep(1.0)
            
    return False
