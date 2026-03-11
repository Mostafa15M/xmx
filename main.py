import os
import time
import re
import csv
import requests
import easyocr
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات الأساسية =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
# البروكسي الثابت اللي اشتغل معاك
TARGET_PROXY = "socks5://128.199.111.243:34418" 
DATA_FILE = "crash_odds_PRO.csv"

class CrashMaster:
    def __init__(self):
        print("⏳ تحميل محرك القراءة والتحليل...")
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.last_odd = None
        # تجهيز ملف الداتا
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Exploded_Odd", "Next_Prediction"])

    def send_telegram(self, msg, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': msg}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=20)
        except: pass

    def predict_next(self):
        """تحليل ملف الـ CSV وتقديم التوقع"""
        try:
            with open(DATA_FILE, 'r') as f:
                rows = list(csv.reader(f))
                if len(rows) < 4: return 1.20 # داتا غير كافية
                odds = [float(row[1]) for row in rows[1:]][-5:]
                avg = sum(odds) / len(odds)
                # معادلة التوقع: لو المتوسط هابط، التوقع حذر
                return round(avg * 0.85, 2) if avg < 2.5 else 1.55
        except: return 1.15

    def run_bot(self):
        with sync_playwright() as p:
            # تشغيل المتصفح مع معالجة أخطاء الشهادات
            browser = p.chromium.launch(headless=True, proxy={"server": TARGET_PROXY}, args=['--ignore-certificate-errors', '--no-sandbox'])
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                # محاولة فتح اللعبة (90 ثانية كحد أقصى)
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=90000)
                page.wait_for_selector("canvas", timeout=60000)
                self.send_telegram("✅ <b>السيستم المتكامل اشتغل!</b>\nجاري مراقبة الطيارة وتسجيل كل 'أود' يفرقع...")

                while True:
                    temp_shot = "current.png"
                    page.locator("canvas").screenshot(path=temp_shot)
                    
                    # قراءة الرقم من الشاشة
                    result = self.reader.readtext(temp_shot)
                    current_val = None
                    for (_, text, _) in result:
                        match = re.search(r'(\d+[\.,]\d+)', text)
                        if match:
                            current_val = match.group(1).replace(',', '.')
                            break
                    
                    # لو الجولة خلصت (الرقم ثبت وتغير)
                    if current_val and current_val != self.last_odd:
                        self.last_odd = current_val
                        # 1. حساب التوقع
                        prediction = self.predict_next()
                        # 2. تسجيل الرقم اللي فرقع في الـ CSV
                        with open(DATA_FILE, 'a', newline='') as f:
                            csv.writer(f).writerow([datetime.now().strftime('%H:%M:%S'), current_val, prediction])
                        
                        # 3. إرسال التقرير
                        msg = f"🏁 <b>فرقعت عند:</b> <code>{current_val}x</code>\n🔮 <b>التوقع الجاي:</b> <code>{prediction}x</code>\n📂 تم التحديث في <code>{DATA_FILE}</code>"
                        self.send_telegram(msg, temp_shot)
                        print(f"Recorded: {current_val}x")

                    if os.path.exists(temp_shot): os.remove(temp_shot)
                    time.sleep(15) # سرعة الفحص

            except Exception as e:
                self.send_telegram(f"⚠️ توقف مؤقت: {str(e)[:50]}")
                time.sleep(20)
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashMaster()
    while True:
        try: bot.run_bot()
        except: time.sleep(30)
