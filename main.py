import os
import time
import re
import cv2
import requests
import easyocr
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات الأساسية =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
# البروكسي اللي أثبت نجاحه في سكريناتك
TARGET_PROXY = "socks5://128.199.111.243:34418" 

class CrashAnalyst:
    def __init__(self):
        print("⏳ جاري تحميل محرك التحليل وقراءة الأرقام...")
        # تحميل محرك الذكاء الاصطناعي للقراءة
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.results_history = []

    def send_telegram(self, msg, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': msg}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=20)
        except: pass

    def perform_analysis(self, current_val):
        """تحليل الأرقام المكتشفة لتقديم توقعات"""
        try:
            val = float(current_val)
            self.results_history.append(val)
            if len(self.results_history) > 10: self.results_history.pop(0)
            
            avg = sum(self.results_history) / len(self.results_history)
            trend = "📈 صعود" if val >= avg else "📉 هبوط"
            return f"\n\n📊 <b>تحليل البيانات:</b>\nاتجاه السوق: {trend}\nمتوسط آخر 10 جولات: {avg:.2f}x"
        except: return "\n\n⚠️ جاري جمع بيانات كافية للتحليل..."

    def start_monitoring(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy={"server": TARGET_PROXY}, args=['--ignore-certificate-errors', '--no-sandbox'])
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            try:
                # محاولة الدخول (90 ثانية أمان)
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=90000)
                page.wait_for_selector("canvas", timeout=60000)
                self.send_telegram("🧠 <b>تم تفعيل نظام التحليل الذكي!</b>")

                for i in range(1, 11):
                    shot_path = f"analysis_step_{i}.png"
                    # لقطة لمنطقة العداد
                    page.locator("canvas").screenshot(path=shot_path)
                    
                    # عملية القراءة (OCR)
                    ocr_results = self.reader.readtext(shot_path)
                    detected_odd = ""
                    for (_, text, _) in ocr_results:
                        match = re.search(r'(\d+[\.,]\d+)', text)
                        if match:
                            detected_odd = match.group(1).replace(',', '.')
                            break
                    
                    # دمج القراءة مع التحليل
                    stats = self.perform_analysis(detected_odd) if detected_odd else ""
                    msg = f"📸 <b>جلسة {i}/10</b>\n🎯 الرقم المرصود: <code>{detected_odd or '---'}x</code>{stats}"
                    
                    self.send_telegram(msg, shot_path)
                    
                    if os.path.exists(shot_path): os.remove(shot_path)
                    time.sleep(30) # الفاصل الزمني المطلوب

            except Exception as e:
                self.send_telegram(f"⚠️ خطأ: {str(e)[:50]}")
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashAnalyst()
    while True:
        try:
            bot.start_monitoring()
            time.sleep(10)
        except: time.sleep(20)
