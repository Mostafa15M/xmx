import os
import time
import random
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات الأساسية =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"

# كل البروكسيات الـ 23 اللي كانت معاك بالظبط
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
            print(f"🔄 جاري المحاولة ببروكسي: {proxy_url}")
            
            # حل مشاكل الشهادات SSL وتجاهل الأخطاء لسرعة الفتح
            browser = p.chromium.launch(headless=True, proxy={"server": proxy_url}, args=['--ignore-certificate-errors', '--no-sandbox'])
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                # رسالة لبداية المحاولة
                self.send_telegram(f"📡 محاولة اتصال ببروكسي: <code>{proxy_url}</code>")
                
                # الدخول للرابط مع تايم أوت معقول (40 ثانية) عشان لو البروكسي تقيل يغيره فوراً
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=40000)
                
                # فحص الحظر
                if "Access denied" in page.content():
                    self.send_telegram("❌ البروكسي محجوب، هجرب غيره...")
                    return

                # الانتظار لحد ما مربع اللعبة يظهر (Canvas)
                page.wait_for_selector("canvas", timeout=30000)
                time.sleep(15) # وقت أمان عشان الأرقام تظهر

                while True:
                    shot = "crash_now.png"
                    # تصوير منطقة اللعبة فقط بدقة
                    page.locator("canvas").screenshot(path=shot)
                    self.send_telegram(f"✅ <b>العداد الآن:</b>\n⏰ {datetime.now().strftime('%H:%M:%S')}", shot)
                    
                    if os.path.exists(shot): os.remove(shot)
                    time.sleep(30) # تحديث كل 30 ثانية

            except Exception as e:
                # لو فشل يصور الغلط عشان نشوفه
                err_shot = "error.png"
                try: page.screenshot(path=err_shot)
                except: err_shot = None
                self.send_telegram(f"⚠️ فشل الاتصال: {str(e)[:50]}", err_shot)
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashBot()
    while True:
        try:
            bot.run()
        except:
            time.sleep(5)
