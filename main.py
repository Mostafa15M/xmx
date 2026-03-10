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

# ===== الإعدادات =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"

# قائمة كل البروكسيات اللي طلبتها (محدثة 2026)
PROXY_LIST = [
    {"server": "socks5://206.189.92.74:7777"},
    {"server": "socks5://128.199.111.243:34418"},
    {"server": "socks5://134.209.100.103:56055"},
    {"server": "socks5://13.250.36.159:48540"},
    {"server": "socks5://47.241.61.60:9050"},
    {"server": "socks5://51.79.156.122:9050"},
    {"server": "socks5://218.185.242.117:9050"},
    {"server": "socks5://128.199.161.225:9050"},
    {"server": "socks5://178.128.84.253:9050"},
    {"server": "socks5://159.65.14.150:9050"},
    {"server": "http://128.199.202.122:3128"},
    {"server": "socks5://165.22.101.15:80"},
    {"server": "socks5://209.97.175.37:9050"},
    {"server": "http://190.104.146.244:999"},
    {"server": "http://140.246.149.224:8888"},
    {"server": "http://101.255.94.161:8080"},
    {"server": "http://51.79.135.131:8080"},
    {"server": "http://152.42.213.210:8080"},
    {"server": "socks5://138.199.25.13:3901"},
    {"server": "socks5://124.156.207.229:1080"},
    {"server": "socks5://165.22.110.253:1080"},
    {"server": "http://143.42.66.91:80"},
    {"server": "http://8.219.97.248:80"},
]

class CrashMasterBot:
    def __init__(self):
        # تحميل OCR مرة واحدة في الذاكرة لتسريع العمل
        self.reader = easyocr.Reader(['en'], gpu=False)
        print("✅ محرك القراءة جاهز...")

    def send_telegram(self, msg, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo:
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': msg}, files={'photo': f}, timeout=20)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=15)
        except: pass

    def start_session(self):
        proxy = random.choice(PROXY_LIST)
        print(f"🔄 محاولة جديدة باستخدام بروكسي: {proxy['server']}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy=proxy, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            page = context.new_page()

            try:
                # الدخول للموقع بانتظار طويل للبروكسيات البطيئة
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=100000)
                
                # الانتظار حتى يظهر الـ Canvas (اللعبة) فعلياً في الصفحة
                print("⏳ بانتظار تحميل جرافيك اللعبة...")
                page.wait_for_selector("canvas", timeout=60000)
                time.sleep(20) # أمان إضافي للتحميل

                while True:
                    # تصوير الـ Canvas فقط (منطقة اللعبة) لزيادة الدقة
                    canvas = page.locator("canvas")
                    shot = f"crash_{int(time.time())}.png"
                    canvas.screenshot(path=shot)

                    # معالجة الصورة وقراءة الـ Odd
                    results = self.reader.readtext(shot)
                    found_odd = None
                    for (_, text, conf) in results:
                        match = re.search(r'(\d+[\.,]\d+)', text)
                        if match:
                            found_odd = match.group(1).replace(',', '.')
                            break
                    
                    if found_odd:
                        msg = f"🎯 <b>نتيجة Crash:</b> <code>{found_odd}x</code>\n⏰ {datetime.now().strftime('%H:%M:%S')}"
                        print(msg)
                        self.send_telegram(msg, shot)
                    
                    if os.path.exists(shot): os.remove(shot)
                    time.sleep(15) # جولة جديدة كل 15 ثانية

            except Exception as e:
                print(f"❌ فشل الاتصال بالبروكسي أو الموقع: {str(e)[:50]}...")
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashMasterBot()
    while True:
        try:
            bot.start_session()
        except KeyboardInterrupt:
            break
        except:
            time.sleep(5)
