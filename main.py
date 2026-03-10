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

# قائمة بروكسيات سنغافورة (SG) حديثة – جرب واحد واحد لو واحد فشل، غيّر أو أضف من free-proxy-list.net
PROXIES = [
    "http://51.79.135.131:8080",      # SG - Anonymous - حديث
    "http://143.42.66.91:80",         # SG - Anonymous - DigitalOcean SG
    "http://156.146.56.231:8081",     # SG - Anonymous - Datacamp SG
    "http://103.174.102.183:80",      # SG - احتياطي
    "http://103.174.102.127:3128",    # SG - احتياطي
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
            return None

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
            print(f"Best: {best[0]:.2f} conf {best[1]:.2f}")
            return f"{best[0]:.2f}"
        else:
            print("No candidates")
    except Exception as e:
        print(f"OCR error: {e}")
    return None


def send_telegram(message, image_paths=None):
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    # إرسال النص أولاً
    text_url = f"{base_url}/sendMessage"
    text_data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(text_url, data=text_data, timeout=10)
        print("Text sent")
    except Exception as e:
        print(f"Text failed: {e}")

    # إرسال الصور واحدة واحدة بتأخير 30 ثانية بينهم
    if image_paths:
        photo_url = f"{base_url}/sendPhoto"
        for i, path in enumerate(image_paths):
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as photo:
                        files = {'photo': photo}
                        data = {
                            'chat_id': CHAT_ID,
                            'caption': f"Debug screenshot {i+1}/{len(image_paths)}: {os.path.basename(path)}"
                        }
                        requests.post(photo_url, data=data, files=files, timeout=15)
                    print(f"Photo {i+1} sent: {path}")

                    # تأخير 30 ثانية بين الصور (ما عدا الأخيرة)
                    if i < len(image_paths) - 1:
                        print("Waiting 30 seconds before next photo...")
                        time.sleep(30)
                except Exception as e:
                    print(f"Photo {i+1} failed ({path}): {e}")
            else:
                print(f"Photo not found: {path}")


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
        print(f"Saved odd: {odd}")
    except Exception as e:
        print(f"CSV error: {e}")


def run_once():
    predictor = CrashPredictor()
    history = load_csv_data()
    predictor.odds_history.extend(history[-200:])
    print(f"Loaded {len(predictor.odds_history)} historical odds")

    success = False
    used_proxy = "No proxy used"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])

            # محاولة كل بروكسي
            for proxy in PROXIES:
                print(f"Trying proxy: {proxy}")
                try:
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                        viewport={'width': 1920, 'height': 1080},
                        proxy={"server": proxy}
                    )
                    page = context.new_page()

                    page.goto("https://1xbet.com/en/allgamesentrance/crash", wait_until="networkidle", timeout=60000)
                    print(f"Success with proxy: {proxy}")
                    used_proxy = proxy
                    success = True
                    break
                except Exception as e:
                    print(f"Proxy {proxy} failed: {e}")
                    continue

            # لو فشل الكل، جرب بدون
            if not success:
                print("All proxies failed, trying direct...")
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()
                page.goto("https://1xbet.com/en/allgamesentrance/crash", wait_until="networkidle", timeout=60000)

            print("Waiting for game...")
            try:
                page.wait_for_selector("canvas, [class*='multiplier'], .multiplier", timeout=60000)
                time.sleep(random.uniform(10, 15))
            except:
                time.sleep(15)

            page.screenshot(path="temp_screenshot.png")
            page.screenshot(path="debug_full.png", full_page=True)
            page.screenshot(path="debug_viewport.png")

            odd = extract_odd_from_image("temp_screenshot.png")

            images_to_send = ["debug_full.png", "debug_viewport.png", "temp_screenshot.png"]

            if odd:
                print(f"Detected: {odd}x")
                save_to_csv(odd)
                predictor.add_odd(odd)
                signal, confidence, pred_odd = predictor.predict()
                print(f"Signal: {signal} Conf: {confidence:.1%}")

                msg = f"""
<b>CRASH BOT RESULT</b> (Proxy: {used_proxy})

Current: <code>{odd}x</code>
Signal: {signal}
Target: <code>{pred_odd:.2f}x</code>
Conf: <code>{confidence:.1%}</code>
Time: {datetime.now().strftime('%H:%M:%S')}
"""

                send_telegram(msg, images_to_send)
            else:
                print("No odd detected")
                msg = f"""
<b>CRASH BOT UPDATE</b> (Proxy: {used_proxy})

❌ No odd detected
Check screenshots
Time: {datetime.now().strftime('%H:%M:%S')}
"""

                send_telegram(msg, images_to_send)

            browser.close()

    except Exception as e:
        print(f"Critical error: {e}")
        msg = f"""
<b>CRASH BOT ERROR</b>

Error: <code>{str(e)}</code>
Proxy: {used_proxy}
Time: {datetime.now().strftime('%H:%M:%S')}
"""
        send_telegram(msg)


if __name__ == "__main__":
    run_once()
