import os
import time
import random
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات الأساسية =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"

# كل البروكسيات اللي طلبتها بالظبط
PROXY_LIST = [
    "socks5://206.189.92.74:7777", "socks5://128.199.111.243:34418",
    "socks5://134.209.100.103:56055", "socks5://13.250.36.159:48540",
    "socks5://47.241.61.60:9050", "socks5://51.79.156.122:9050",
    "socks5://218.185.242.117:9050", "socks5://128.199.161.225:9050",
    "socks5://178.128.84.253:9050", "socks5://159.65.14.150:9050",
    "http://128.199.202.122:3128", "socks5://165.22.101.15:80",
    "socks5://209.97.175.37:9050", "http://190.104.146.244:999",
    "http://140.246.149.224:8888", "http://101.255.94.161:8080",
    "http://51.79.135.131:8080", "http://152.42.213.210:8080",
    "socks5://138.199.25.13:3901", "socks5://124.156.207.229:1080",
    "socks5://165.22.110.253:1080", "http://143.42.66.91:80",
    "http://8.219.97.248:80"
]

# الروابط البديلة في حال الحظر
URLS = [
    "https://1xbet.com/en/games/crash",
    "https://1xbet-en.com/en/games/crash",
    "https://ua-1x-bet.com/en/games/crash"
]

class CrashBot:
    def send_telegram(self, message, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': message}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}, timeout=20)
        except: pass

    def run(self):
        with sync_playwright() as p:
            proxy_url = random.choice(PROXY_LIST)
            print(f"🔄 محاولة باستخدام: {proxy_url}")
            
            # أهم جزء: ignore_https_errors=True لحل مشكلة CERT_AUTHORITY_INVALID
            browser = p.chromium.launch(headless=True, proxy={"server": proxy_url}, args=['--ignore-certificate-errors'])
            context = browser.new_context(ignore_https_errors=True, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()

            try:
                target_url = random.choice(URLS)
                self.send_telegram(f"📡 <b>محاولة اتصال</b>\nالرابط: {target_url}\nالبروكسي: <code>{proxy_url}</code>")
                
                page.goto(target_url, wait_until="load", timeout=90000)
                
                # الانتظار حتى يظهر العداد
                page.wait_for_selector("canvas", timeout=60000)
                time.sleep(20)

                while True:
                    shot = "live.png"
                    page.locator("canvas").screenshot(path=shot)
                    self.send_telegram(f"✅ <b>متصل الآن!</b>\n⏰ {datetime.now().strftime('%H:%M:%S')}", shot)
                    if os.path.exists(shot): os.remove(shot)
                    time.sleep(60)

            except Exception as e:
                error_str = str(e).split('\n')[0]
                self.send_telegram(f"⚠️ <b>فشل الاتصال:</b>\n<code>{error_str}</code>\nجاري تجربة بروكسي آخر...")
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashBot()
    while True:
        try:
            bot.run()
        except:
            time.sleep(10)
