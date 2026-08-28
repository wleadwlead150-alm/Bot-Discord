def check_ticket_content_for_complaint(token, ch_id, username):
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
                            # سحب العنوان والوصف وكل حقول الـ Embed بدقة
                            embed_text += " " + embed.get("title", "") + " " + embed.get("description", "")
                            for field in embed.get("fields", []):
                                embed_text += " " + field.get("name", "") + " " + field.get("value", "")
                    
                    embed_text = embed_text.lower()
                    
                    # إذا كانت التذكرة تخص "شكاوي اللاعبين" العادية، يتم رفضها فوراً لـ Isso و Osama
                    if "شكاوي اللاعبين" in embed_text or "شكاوى اللاعبين" in embed_text:
                        # استثناء: إذا كان المقصود شكوى ضد إداري، نتاكد هل مكتوبة بالداخل
                        if not ("إداري" in embed_text or "اداري" in embed_text or "مشرف" in embed_text):
                            return False

                    # التحقق لشخصية Isso و Osama (يجب أن تحتوي على كلمة تخص الإداريين أو قادة الفصائل)
                    admin_keywords = ["إداري", "اداري", "مشرف", "سوبر فايزر", "supervisor", "helper", "قائد", "فصيل", "ليدر"]
                    if any(kw in embed_text for kw in admin_keywords):
                        return True
                        
                    # إذا لم تكن شكوى إدارية وكانت تابعة للاعبين، لا يستلمها
                    return False
                else:
                    time.sleep(1.0)
            else:
                break
        except Exception:
            time.sleep(1.0)
            
    return False
