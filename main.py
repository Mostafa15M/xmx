import os
import time
import re
import cv2
import requests
import easyocr
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
TARGET_PROXY = "socks5://128.199.111.243:34418" 

class CrashAnalyst:
    def __init__(self):
        print("⏳ جاري تشغيل محرك التحليل الذكي...")
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.history = [] # هنا بنخزن الأرقام اللي اتقرأت للتحليل

    def send_telegram(self, msg, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': msg}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=20)
        except: pass

    def analyze_odds(self, current_odd):
        """تحليل بسيط للأرقام المكتشفة"""
        try:
            val = float(current_odd)
            self.history.append(val)
            if len(self.history) > 10: self.history.pop(0)
            
            avg = sum(self.history) / len(self.history)
            status = "📈 اتجاه صاعد" if val > avg else "📉 اتجاه هابط"
            return f"\n📊 <b>التحليل:</b> {status}\n平均 المتوسط: {avg:.2f}x"
        except: return ""

    def start_session(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy={"server": TARGET_PROXY}, args=['--ignore-certificate-errors', '--no-sandbox'])
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=90000)
                page.wait_for_selector("canvas", timeout=60000)
                
                self.send_telegram("✅ <b>تم تفعيل نظام التحليل!</b>")

                for i in range(1, 11):
                    shot = f"analyze_{i}.png"
                    page.locator("canvas").screenshot(path=shot)
                    
                    # قراءة الرقم من الصورة
                    results = self.reader.readtext(shot)
                    text_found = ""
                    for (_, text, _) in results:
                        match = re.search(r'(\d+[\.,]\d+)', text)
                        if match:
                            text_found = match.group(1).replace(',', '.')
                            break
                    
                    analysis = self.analyze_odds(text_found) if text_found else "\n❓ لم يتم تحديد الرقم بدقة"
                    
                    msg = f"📸 <b>جلسة تحليل ({i}/10)</b>\n🎯 الرقم المرصود: <code>{text_found or '---'}x</code>{analysis}"
                    self.send_telegram(msg, shot)
                    
                    if os.path.exists(shot): os.remove(shot)
                    time.sleep(30)

            except Exception as e:
                self.send_telegram(f"⚠️ خطأ في التحليل: {str(e)[:50]}")
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashAnalyst()
    while True:
        bot.start_session()
        time.sleep(10)
