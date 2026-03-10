import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ===== الإعدادات الثابتة =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
# البروكسي المعتمد بناءً على تجاربك الناجحة
TARGET_PROXY = "socks5://128.199.111.243:34418" 

class CrashMonitor:
    def send_telegram(self, msg, photo=None):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        try:
            if photo and os.path.exists(photo):
                with open(photo, 'rb') as f:
                    requests.post(url + "sendPhoto", data={'chat_id': CHAT_ID, 'caption': msg}, files={'photo': f}, timeout=30)
            else:
                requests.post(url + "sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=20)
        except:
            print("خطأ في إرسال التليجرام")

    def start_session(self):
        with sync_playwright() as p:
            print(f"🚀 بدء جلسة جديدة عبر: {TARGET_PROXY}")
            
            # تشغيل المتصفح مع إعدادات تخطي الحظر والشهادات
            browser = p.chromium.launch(headless=True, proxy={"server": TARGET_PROXY}, args=['--ignore-certificate-errors', '--no-sandbox'])
            context = browser.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 720})
            page = context.new_page()

            try:
                # محاولة فتح اللعبة (انتظار حتى 90 ثانية للتحميل)
                page.goto("https://1xbet.com/en/games/crash", wait_until="load", timeout=90000)
                
                # التأكد إن العداد (Canvas) ظهر
                page.wait_for_selector("canvas", timeout=60000)
                self.send_telegram("✅ <b>تم الاتصال بنجاح!</b>\nجاري سحب 10 صور (فاصل 30 ثانية)...")
                
                # حلقة تكرار لـ 10 صور فقط في الجلسة الواحدة
                for i in range(1, 11):
                    shot_name = f"crash_{i}.png"
                    # تصوير منطقة العداد
                    page.locator("canvas").screenshot(path=shot_name)
                    
                    current_time = datetime.now().strftime('%H:%M:%S')
                    self.send_telegram(f"📸 <b>صورة رقم ({i}/10)</b>\n⏰ الوقت: {current_time}", shot_name)
                    
                    # مسح الصورة بعد الإرسال
                    if os.path.exists(shot_name): os.remove(shot_name)
                    
                    # الانتظار 30 ثانية قبل الصورة التالية (إلا في الصورة الأخيرة)
                    if i < 10:
                        time.sleep(30)

                self.send_telegram("🏁 <b>انتهت الدورة (10 صور).</b>\nجاري إعادة تنشيط الصفحة لجولة جديدة...")

            except Exception as e:
                error_details = str(e)[:100]
                self.send_telegram(f"⚠️ <b>توقف مؤقت:</b>\n<code>{error_details}</code>\nجاري إعادة المحاولة...")
            finally:
                browser.close()

if __name__ == "__main__":
    bot = CrashMonitor()
    # تشغيل مستمر (كل دورة 10 صور)
    while True:
        try:
            bot.start_session()
            time.sleep(10) # استراحة بسيطة بين الجلسات
        except Exception as e:
            print(f"خطأ عام: {e}")
            time.sleep(30)
