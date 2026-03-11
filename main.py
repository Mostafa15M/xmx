import os
import time
import re
import csv
import requests
import easyocr
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
TARGET_PROXY = "socks5://128.199.111.243:34418" 
DATA_FILE = "crash_odds_PRO.csv"

class CrashLiveMonitor:
    def __init__(self):
        print("⏳ جاري تشغيل نظام المراقبة الحي...")
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.last_odd = None
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w', newline='') as f:
                csv.writer(f).writerow(["Time", "Odd", "Prediction"])

    def send_telegram(self, msg, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': msg}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=20)
        except: pass

    def run(self):
        with sync_playwright() as p:
            # تشغيل المتصفح مع إعدادات تخطي الحظر والبطء
            browser = p.chromium.launch(headless=True, proxy={"server": TARGET_PROXY})
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            page = context.new_page()

            try:
                print("🔗 محاولة فتح صفحة اللعبة...")
                page.goto("https://1xbet.com/en/games/crash", wait_until="networkidle", timeout=120000)
                
                while True:
                    # 1. التقاط سكرين شوت للحالة الحالية
                    current_shot = "live_status.png"
                    page.screenshot(path=current_shot)
                    
                    # 2. قراءة الرقم من السكرين شوت
                    results = self.reader.readtext(current_shot)
                    current_val = None
                    for (_, text, _) in results:
                        match = re.search(r'(\d+[\.,]\d+)', text)
                        if match:
                            current_val = match.group(1).replace(',', '.')
                            break
                    
                    # 3. لو الجولة انتهت، سجل في CSV وابعت التقرير
                    if current_val and current_val != self.last_odd:
                        self.last_odd = current_val
                        # تسجيل في الملف
                        with open(DATA_FILE, 'a', newline='') as f:
                            csv.writer(f).writerow([datetime.now().strftime('%H:%M:%S'), current_val, "AI_Calc"])
                        
                        msg = f"📸 <b>حالة اللعبة الآن:</b>\n🏁 فرقعت عند: <code>{current_val}x</code>\n📂 تم التحديث في الملف."
                        self.send_telegram(msg, current_shot)
                    else:
                        # لو لسه الطيارة طايرة أو الصفحة بتحمل، ابعت سكرين للتأكيد كل دقيقة
                        self.send_telegram("🔄 <b>مراقبة مستمرة.. الحالة الحالية:</b>", current_shot)

                    if os.path.exists(current_shot): os.remove(current_shot)
                    time.sleep(30) # تحديث كل 30 ثانية عشان ميبقاش "سبام"

            except Exception as e:
                self.send_telegram(f"⚠️ خطأ في المراقبة: {str(e)[:50]}")
                time.sleep(20)
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashLiveMonitor()
    while True:
        try: bot.run()
        except: time.sleep(30)
