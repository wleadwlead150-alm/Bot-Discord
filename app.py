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
                    
                    # الفلترة حصراً للشكاوى ضد الإداريين والمشرفين (لكل من أسامة وإيسو)
                    admin_keywords = ["اداري", "إداري", "مشرف", "helper", "مراقب", "سوبر فايزر", "supervisor", "admin", "moderator"]
                    return any(kw in combined_text for kw in admin_keywords)
                else:
                    time.sleep(1.0)
            else:
                break
        except Exception:
            time.sleep(1.0)
    return False
