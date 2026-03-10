import os
import time
import random
import re
import requests
import cv2
import numpy as np
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"

# قائمة البروكسيات الشغالة
PROXY_LIST = [
    {"server": "socks5://206.189.92.74:7777"},
    {"server": "socks5://128.199.111.243:34418"},
    {"server": "socks5://134.209.100.103:56055"},
    {"server": "socks5://13.250.36.159:48540"},
    {"server": "socks5://159.65.14.150:9050"},
    {"server": "http://152.42.213.210:8080"},
    {"server": "http://51.79.135.131:8080"}
]

class CrashBot:
    def __init__(self):
        self.last_odd = None

    def send_telegram(self, message, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': message}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}, timeout=20)
        except:
            print("Telegram Error")

    def run(self):
        # رسالة تأكيد لبداية التشغيل عشان تطمن
        self.send_telegram("🚀 <b>البوت بدأ العمل على GitHub بنجاح!</b>\nجاري محاولة فتح اللعبة...")
        
        with sync_playwright() as p:
            proxy = random.choice(PROXY_LIST)
            print(f"🔄 محاولة بروكسي: {proxy['server']}")
            
            browser = p.chromium.launch(headless=True, proxy=proxy, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            page = context.new_page()

            try:
                # الدخول للعبة
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=120000)
                
                # الانتظار حتى تحميل اللعبة (Canvas)
                page.wait_for_selector("canvas", timeout=60000)
                print("✅ اللعبة حملت!")
                time.sleep(30) # وقت أمان إضافي

                while True:
                    shot_path = "live_view.png"
                    # تصوير منطقة اللعبة فقط
                    page.locator("canvas").screenshot(path=shot_path)
                    
                    # إرسال الصورة لتليجرام عشان نتابع الشاشة حية
                    current_time = datetime.now().strftime('%H:%M:%S')
                    self.send_telegram(f"📸 <b>تحديث مباشر من اللعبة</b>\n⏰ الوقت: {current_time}", shot_path)
                    
                    if os.path.exists(shot_path): os.remove(shot_path)
                    
                    # الانتظار للجولة التالية (دقيقة واحدة لتجنب ضغط GitHub)
                    time.sleep(60)

            except Exception as e:
                self.send_telegram(f"❌ حدث خطأ أثناء التشغيل:\n<code>{str(e)[:100]}</code>")
            finally:
                browser.close()

if __name__ == "__main__":
    # تأكد من اسم الكلاس هنا عشان ميحصلش Fail
    bot = CrashBot() 
    while True:
        try:
            bot.run()
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(20)
