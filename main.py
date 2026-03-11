import os
import time
import csv
import re
import cv2
import numpy as np
from datetime import datetime
from playwright.sync_api import sync_playwright
import easyocr
from scipy import stats
import requests
import random
from collections import deque

# ===== CONFIG =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
CSV_FILE = "crash_odds_PRO.csv"

# البروكسي الوحيد اللي طلبت تستخدمه
TARGET_PROXY = "socks5://128.199.111.243:34418"

class CrashPredictor:
    def __init__(self):
        self.odds_history = deque(maxlen=200)
        self.streaks = {'low': 0, 'mid': 0, 'high': 0}

    def add_odd(self, odd):
        try:
            odd_val = float(odd)
            self.odds_history.append(odd_val)
            self.update_streaks(odd_val)
        except:
            pass

    def update_streaks(self, odd):
        self.streaks = {'low': 0, 'mid': 0, 'high': 0}
        for o in list(self.odds_history)[-10:]:
            if o < 2.0: self.streaks['low'] += 1
            elif o < 5.0: self.streaks['mid'] += 1
            else: self.streaks['high'] += 1

    def predict(self):
        if len(self.odds_history) < 15:
            return "⏳ WAIT", 0.4, 0.0

        recent = list(self.odds_history)[-30:]
        x = np.arange(len(recent))

        predictions = []
        try:
            slope, intercept, r_value, _, _ = stats.linregress(x, recent)
            lin_pred = max(1.1, intercept + slope * (len(recent) + 1))
            predictions.append(lin_pred * (0.7 + r_value**2 * 0.3))
        except:
            pass

        alpha = 0.3
        ema = recent[0]
        for val in recent[1:]:
            ema = alpha * val + (1 - alpha) * ema
        predictions.append(ema * 1.1)

        streak_boost = 1.0
        if self.streaks['low'] >= 5: streak_boost = 2.2
        elif self.streaks['low'] >= 3: streak_boost = 1.6
        elif self.streaks['high'] >= 4: streak_boost = 0.75

        final_pred = np.mean(predictions) * streak_boost if predictions else np.mean(recent)
        confidence = min(0.92, 0.4 + len(recent)/200 + abs(streak_boost-1)*0.3)

        if final_pred > 4.0 and confidence > 0.8:
            return "🚀 STRONG BUY", confidence, final_pred
        elif final_pred > 2.4 and confidence > 0.7:
            return "✅ BUY", confidence, final_pred
        else:
            return "⏳ WAIT", confidence, final_pred


def preprocess_image(image):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(l, -1, kernel)
    l = cv2.addWeighted(l, 0.7, sharpened, 0.3, 0)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
    return enhanced


def extract_odd_from_image(image_path):
    try:
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        img = cv2.imread(image_path)
        if img is None:
            print("خطأ: الصورة مش موجودة أو فشل في قراءتها")
            return None

        # مناطق محتملة للـ multiplier (عدلتها شوية عشان تكون أدق)
        regions = [
            img[80:420,  550:1350],
            img[140:380, 750:1150],
            img[180:480, 650:1250],
            img[220:520, 700:1200],
        ]

        all_texts = []
        for region in regions:
            if region.size == 0:
                continue
            processed = preprocess_image(region)
            results = reader.readtext(processed)
            all_texts.extend(results)

        candidates = []
        for (_, text, conf) in all_texts:
            if conf > 0.35:
                match = re.search(r'(\d+\.?\d*)[xX]?', text, re.IGNORECASE)
                if match:
                    try:
                        odd = float(match.group(1))
                        if 1.01 <= odd <= 1000:
                            candidates.append((odd, conf))
                    except:
                        continue

        if candidates:
            best = max(candidates, key=lambda x: x[1])
            print(f"أفضل قراءة: {best[0]:.2f}x (ثقة {best[1]:.2f})")
            return f"{best[0]:.2f}"
        else:
            print("مفيش أرقام مناسبة تم قراءتها")
    except Exception as e:
        print(f"خطأ في OCR: {e}")
    return None


def send_telegram(message, image_paths=None):
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    # إرسال النص أولاً
    try:
        requests.post(
            f"{base_url}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=15
        )
        print("تم إرسال الرسالة النصية")
    except Exception as e:
        print(f"فشل إرسال النص: {e}")

    # إرسال الصور لو موجودة (مع تأخير بسيط)
    if image_paths:
        for i, path in enumerate(image_paths):
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as photo:
                        requests.post(
                            f"{base_url}/sendPhoto",
                            data={'chat_id': CHAT_ID, 'caption': f"صورة ديباج {i+1}"},
                            files={'photo': photo},
                            timeout=20
                        )
                    print(f"تم إرسال الصورة {i+1}: {path}")
                    time.sleep(8)  # تأخير أقل شوية عشان ما يبقاش بطيء أوي
                except Exception as e:
                    print(f"فشل إرسال الصورة {path}: {e}")
            else:
                print(f"الصورة مش موجودة: {path}")


def save_to_csv(odd):
    try:
        file_exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'odd'])
            writer.writerow([datetime.now().isoformat(), odd])
        print(f"تم حفظ: {odd}x")
    except Exception as e:
        print(f"خطأ في حفظ CSV: {e}")


def main():
    predictor = CrashPredictor()
    print(f"بدء التشغيل باستخدام البروكسي: {TARGET_PROXY}")

    while True:
        success = False
        try:
            with sync_playwright() as p:
                print("جاري تشغيل المتصفح...")
                browser = p.chromium.launch(
                    headless=True,
                    proxy={"server": TARGET_PROXY},
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--ignore-certificate-errors']
                )

                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 720},
                    ignore_https_errors=True
                )

                page = context.new_page()

                print("جاري الدخول على الصفحة...")
                page.goto(
                    "https://ma-1xbet.com/en/games/crash",
                    wait_until="networkidle",
                    timeout=90000
                )

                print("انتظار تحميل اللعبة...")
                try:
                    page.wait_for_selector("canvas, [class*='multiplier']", timeout=60000)
                    print("تم تحميل اللعبة بنجاح")
                except:
                    print("مش لاقي canvas أو multiplier – هجرب انتظر أكتر")
                    time.sleep(20)

                time.sleep(random.uniform(8, 12))  # انتظار عشوائي عشان ما يبانش bot

                # تصوير الشاشة
                shot = "live_round.png"
                debug_full = "debug_full.png"
                page.screenshot(path=shot)
                page.screenshot(path=debug_full, full_page=True)

                # محاولة استخراج الـ odd
                odd = extract_odd_from_image(shot)

                if odd:
                    print(f"تم قراءة: {odd}x")
                    save_to_csv(odd)
                    predictor.add_odd(odd)
                    signal, confidence, pred_odd = predictor.predict()

                    msg = f"""
<b>CRASH MONITOR UPDATE</b>

Current odd: <code>{odd}x</code>
Signal: {signal}
Predicted next: <code>{pred_odd:.2f}x</code>
Confidence: <code>{confidence:.0%}</code>
Proxy: {TARGET_PROXY}
Time: {datetime.now().strftime('%H:%M:%S')}
"""

                    send_telegram(msg, [debug_full, shot])
                else:
                    print("فشل قراءة الـ odd")
                    send_telegram(
                        f"❌ فشل قراءة الـ odd\nProxy: {TARGET_PROXY}\nTime: {datetime.now().strftime('%H:%M:%S')}",
                        [debug_full, shot]
                    )

                # تنظيف
                for f in [shot, debug_full]:
                    if os.path.exists(f):
                        os.remove(f)

                browser.close()

        except Exception as e:
            print(f"خطأ كبير: {e}")
            send_telegram(
                f"<b>CRASH BOT ERROR</b>\n{e}\nProxy: {TARGET_PROXY}\nإعادة المحاولة بعد 30 ثانية...",
                None
            )
            time.sleep(30)

        time.sleep(15)  # فاصل بين الدورات


if __name__ == "__main__":
    print("تشغيل Crash Predictor مع البروكسي المحدد...")
    main()
