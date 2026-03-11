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
# البروكسي اللي شغال معاك ومخطى الحظر
TARGET_PROXY = "socks5://128.199.111.243:34418" 
# ملف قاعدة البيانات الخاص بك
DATA_FILE = "crash_odds_PRO.csv"

class CrashMaster:
    def __init__(self):
        print("⏳ جاري تحضير محرك الذكاء الاصطناعي...")
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.last_saved_odd = None
        # إنشاء الملف وتجهيز العناوين لو مش موجود
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

    def log_and_predict(self, final_odd):
        """بيحط الاود الي فرقع في الملف ويحسب التوقع القادم بناءً على التاريخ"""
        try:
            history = []
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r') as f:
                    reader = csv.reader(f)
                    next(reader) 
                    history = [float(row[1]) for row in reader if row[1]]

            # معادلة التوقع للجولة القادمة
            prediction = 1.20
            if len(history) >= 3:
                # بيحلل متوسط آخر 5 جولات عشان يتوقع الجاية
                avg = sum(history[-5:]) / len(history[-5:])
                prediction = round(avg * 0.88, 2) if avg < 2.5 else 1.60
            
            # تسجيل الرقم اللي فرقع دلوقتى في ملف الـ CSV
            with open(DATA_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now().strftime('%H:%M:%S'), final_odd, prediction])
            
            return prediction
        except: return 1.15

    def start_engine(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy={"server": TARGET_PROXY}, args=['--ignore-certificate-errors', '--no-sandbox'])
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                # محاولة الدخول مع معالجة الـ Timeout اللي كانت بتظهرلك
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=90000)
                page.wait_for_selector("canvas", timeout=60000)
                self.send_telegram("✅ <b>النظام المتكامل جاهز!</b>\nجاري رصد الجولات وتحديث ملف الـ CSV...")

                while True:
                    shot = "live_round.png"
                    page.locator("canvas").screenshot(path=shot)
                    
                    # قراءة الـ Odd من الشاشة
                    results = self.reader.readtext(shot)
                    current_odd = None
                    for (_, text, _) in results:
                        match = re.search(r'(\d+[\.,]\d+)', text)
                        if match:
                            current_odd = match.group(1).replace(',', '.')
                            break
                    
                    # لو الطيارة فرقعت (الرقم ثبت وتغير عن اللي فات)
                    if current_odd and current_odd != self.last_saved_odd:
                        self.last_saved_odd = current_odd
                        # تسجيل في الملف وحساب التوقع
                        next_pred = self.log_and_predict(current_odd)
                        
                        msg = f"🏁 <b>فرقعت عند:</b> <code>{current_odd}x</code>\n"
                        msg += f"🔮 <b>التوقع للجولة الجاية:</b> <code>{next_pred}x</code>\n"
                        msg += f"📂 تم التحديث في <code>{DATA_FILE}</code>"
                        
                        self.send_telegram(msg, shot)
                        print(f"Recorded to CSV: {current_odd}x")

                    if os.path.exists(shot): os.remove(shot)
                    time.sleep(12) # فحص مستمر كل جولة

            except Exception as e:
                # لو حصل أي Timeout في الصفحة بيحاول يفتحها تاني
                print(f"Restarting due to: {e}")
                time.sleep(15)
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashMaster()
    while True:
        try: bot.start_engine()
        except: time.sleep(20)
