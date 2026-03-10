import os
import time
import random
import re
import cv2
import csv
import numpy as np
import requests
import easyocr
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== إعدادات الوصول =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
CSV_FILE = "crash_history_2026.csv"

# كل البروكسيات اللي طلبتها (الترسانة كاملة)
PROXY_LIST = [
    {"server": "socks5://206.189.92.74:7777"}, {"server": "socks5://128.199.111.243:34418"},
    {"server": "socks5://134.209.100.103:56055"}, {"server": "socks5://13.250.36.159:48540"},
    {"server": "socks5://47.241.61.60:9050"}, {"server": "socks5://51.79.156.122:9050"},
    {"server": "socks5://218.185.242.117:9050"}, {"server": "socks5://128.199.161.225:9050"},
    {"server": "socks5://178.128.84.253:9050"}, {"server": "socks5://159.65.14.150:9050"},
    {"server": "http://128.199.202.122:3128"}, {"server": "socks5://165.22.101.15:80"},
    {"server": "socks5://209.97.175.37:9050"}, {"server": "http://190.104.146.244:999"},
    {"server": "http://140.246.149.224:8888"}, {"server": "http://101.255.94.161:8080"},
    {"server": "http://51.79.135.131:8080"}, {"server": "http://152.42.213.210:8080"},
    {"server": "socks5://138.199.25.13:3901"}, {"server": "socks5://124.156.207.229:1080"},
    {"server": "socks5://165.22.110.253:1080"}, {"server": "http://143.42.66.91:80"},
    {"server": "http://8.219.97.248:80"},
]

class CrashSystem:
    def __init__(self):
        # تحميل محرك القراءة (EasyOCR)
        print("⏳ جاري تحميل محرك الذكاء الاصطناعي...")
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.last_odd = None

    def send_telegram(self, msg, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': msg}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=20)
        except Exception as e:
            print(f"❌ خطأ تليجرام: {e}")

    def process_image(self, path):
        """تحسين الصورة لزيادة دقة القراءة"""
        img = cv2.imread(path)
        if img is None: return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # زيادة التباين عشان الرقم الأبيض ينطق
        enhanced = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)[1]
        proc_path = f"proc_{path}"
        cv2.imwrite(proc_path, enhanced)
        return proc_path

    def run(self):
        with sync_playwright() as p:
            proxy = random.choice(PROXY_LIST)
            print(f"🚀 تشغيل ببروكسي: {proxy['server']}")
            
            browser = p.chromium.launch(headless=True, proxy=proxy, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            page = context.new_page()

            try:
                self.send_telegram(f"🔄 <b>محاولة اتصال جديدة</b>\nالبروكسي: <code>{proxy['server']}</code>")
                
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=120000)
                
                # استنى اللعبة تحمل فعلياً
                page.wait_for_selector("canvas", timeout=60000)
                print("✅ اللعبة ظهرت على الشاشة")
                time.sleep(25) # وقت تحميل المحتوى داخل الـ Canvas

                while True:
                    shot = f"crash_live.png"
                    # تصوير العداد فقط (الـ Canvas)
                    page.locator("canvas").screenshot(path=shot)
                    
                    # قراءة الرقم
                    proc_shot = self.process_image(shot)
                    results = self.reader.readtext(proc_shot or shot)
                    
                    current_odd = None
                    for (_, text, conf) in results:
                        # بحث عن نمط الرقم 1.00
                        match = re.search(r'(\d+[\.,]\d+)', text)
                        if match:
                            current_odd = match.group(1).replace(',', '.')
                            break
                    
                    if current_odd and current_odd != self.last_odd:
                        self.last_odd = current_odd
                        msg = f"🎯 <b>نتيجة جيدة:</b> <code>{current_odd}x</code>\n⏰ {datetime.now().strftime('%H:%M:%S')}"
                        print(msg)
                        self.send_telegram(msg, shot)
                        
                        # حفظ في الملف
                        with open(CSV_FILE, 'a', newline='') as f:
                            csv.writer(f).writerow([datetime.now(), current_odd])

                    # تنظيف
                    for f in [shot, proc_shot]:
                        if f and os.path.exists(f): os.remove(f)
                        
                    time.sleep(12) # فحص كل جولة

            except Exception as e:
                error_msg = f"⚠️ <b>توقف مؤقت:</b>\n{str(e)[:100]}"
                print(error_msg)
                self.send_telegram(error_msg)
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashMasterBot()
    while True:
        try:
            bot.run()
        except:
            time.sleep(10)
