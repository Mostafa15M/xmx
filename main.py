import os
import time
import csv
import re
import cv2
import numpy as np
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import easyocr
from scipy import stats
import requests
import random
from collections import deque

# ===== CONFIG =====
TELEGRAM_TOKEN = "7044109545:AAF_2u9_HqVGZzFIubnIWCQ3dFm7MyQfmWw"
CHAT_ID = "5773032750"
CSV_FILE = "crash_odds_PRO.csv"

# الـ proxy الثابت اللي نجح قبل كده
FIXED_PROXY = {"server": "http://186.182.6.191:3129"}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

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
            return "⏳ انتظر", 0.4, 0.0

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
            return "🚀 شراء قوي", confidence, final_pred
        elif final_pred > 2.4 and confidence > 0.7:
            return "✅ شراء", confidence, final_pred
        else:
            return "⏳ انتظر", confidence, final_pred


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
            return None

        regions = [
            img[80:420,  550:1350],
            img[140:380, 750:1150],
            img[180:480, 650:1250],
            img[220:520, 700:1200],
            img[100:500, 600:1300],
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
            if conf > 0.25:
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
            print(f"اكتشاف odd: {best[0]:.2f}x (ثقة {best[1]:.2f}) من {os.path.basename(image_path)}")
            return f"{best[0]:.2f}"
        else:
            print("ما لقاش odd")
    except Exception as e:
        print(f"خطأ OCR: {e}")
    return None


def send_telegram(message, image_paths=None):
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    text_url = f"{base_url}/sendMessage"
    text_data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(text_url, data=text_data, timeout=15)
        print("تم إرسال الرسالة")
    except Exception as e:
        print(f"فشل الإرسال: {e}")

    if image_paths:
        photo_url = f"{base_url}/sendPhoto"
        for i, path in enumerate(image_paths):
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as photo:
                        files = {'photo': photo}
                        data = {'chat_id': CHAT_ID, 'caption': f"صورة {i+1}/{len(image_paths)} - {os.path.basename(path)}"}
                        requests.post(photo_url, data=data, files=files, timeout=20)
                    print(f"تم إرسال الصورة {i+1}")
                    if i < len(image_paths) - 1:
                        time.sleep(25)
                except Exception as e:
                    print(f"فشل الصورة {i+1}: {e}")


def load_csv_data():
    data = []
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            data.append(float(row[1]))
                        except:
                            pass
        except:
            pass
    return data


def save_to_csv(odd):
    try:
        file_exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'odd'])
            writer.writerow([datetime.now().isoformat(), odd])
        print(f"تم حفظ: {odd}")
    except Exception as e:
        print(f"خطأ CSV: {e}")


def run_once():
    print("البوت شغال بالـ proxy الثابت + رابط Crash مباشر")
    predictor = CrashPredictor()
    history = load_csv_data()
    predictor.odds_history.extend(history[-200:])
    print(f"تم تحميل {len(predictor.odds_history)} odd سابقة")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])

            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                proxy=FIXED_PROXY,
                ignore_https_errors=True,
                bypass_csp=True,
                java_script_enabled=True,
            )
            page = context.new_page()

            CRASH_URL = "https://1x-bet.mobi/en/games/crash"

            print(f"جاري الدخول على: {CRASH_URL}")
            page.goto(
                CRASH_URL,
                wait_until="domcontentloaded",
                timeout=180000
            )

            try:
                page.wait_for_load_state("domcontentloaded", timeout=90000)
                print("الصفحة حملت")
            except:
                print("مشكلة تحميل - إعادة محاولة...")
                page.reload(wait_until="domcontentloaded", timeout=90000)

            print("بانتظار تحميل اللعبة...")
            time.sleep(random.uniform(60, 120))

            try:
                page.wait_for_selector("canvas, [class*='multiplier'], .multiplier", timeout=120000)
                print("تم العثور على اللعبة!")
            except:
                print("ما لقاش multiplier")

            screenshots = []
            for i in range(5):
                path = f"debug_shot_{i+1}_{int(time.time())}.png"
                try:
                    page.screenshot(path=path, full_page=True, timeout=90000)
                    screenshots.append(path)
                    print(f"تم التقاط {i+1}")
                except PlaywrightTimeoutError:
                    print(f"timeout في {i+1}")
                except Exception as e:
                    print(f"خطأ في {i+1}: {e}")
                time.sleep(15)

            odd = None
            for scr in screenshots:
                if os.path.exists(scr):
                    detected = extract_odd_from_image(scr)
                    if detected:
                        odd = detected
                        break

            images_to_send = [p for p in screenshots if os.path.exists(p)]

            if odd:
                save_to_csv(odd)
                predictor.add_odd(odd)
                signal, conf, pred = predictor.predict()

                msg = f"""
<b>نتيجة - رابط Crash مباشر</b>

odd: <code>{odd}x</code>
إشارة: {signal}
هدف: <code>{pred:.2f}x</code>
ثقة: <code>{conf:.0%}</code>
وقت: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
                send_telegram(msg, images_to_send)
            else:
                msg = f"""
<b>ما لقاش odd</b> - رابط Crash مباشر

تحقق الصور
غالباً اللعبة علقت في التحميل
وقت: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
                send_telegram(msg, images_to_send)

            browser.close()

    except Exception as e:
        print(f"خطأ كبير: {str(e)}")
        send_telegram(f"""
<b>خطأ في البوت</b>

{str(e)[:400]}
وقت: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
""")


if __name__ == "__main__":
    print("البوت شغال بالـ proxy الثابت + رابط Crash مباشر")
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("تم إيقاف البوت")
            break
        except Exception as e:
            print(f"خطأ في الحلقة: {e}")
            time.sleep(120)

        wait = random.uniform(180, 360)
        print(f"التشغيل التالي بعد ≈ {wait//60:.0f} دقيقة")
        time.sleep(wait)
