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
            if o < 2.0:    self.streaks['low'] += 1
            elif o < 5.0:  self.streaks['mid'] += 1
            else:          self.streaks['high'] += 1

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
        if self.streaks['low'] >= 5:  streak_boost = 2.2
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
            img[100:400,  600:1300],   # أوسع
            img[150:350,  800:1100],   # وسط
            img[200:500,  700:1200],   # أسفل شوية
            img[250:550,  750:1150],   # المنطقة الأصلية
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
            return f"{best[0]:.2f}"
    except Exception as e:
        print(f"OCR Error: {e}")
    return None


def send_telegram(signal, confidence, current_odd, pred_odd):
    emoji_map = {"🚀 STRONG BUY": "🔥", "✅ BUY": "💰", "⏳ WAIT": "⏳"}
    emoji = emoji_map.get(signal, "⚠️")

    message = f"""
{emoji} <b>CRASH SIGNAL</b> {emoji}

💰 Current: <code>{current_odd}x</code>
🎯 Target: <code>{pred_odd:.2f}x</code>
📈 Signal: {signal}
🎯 Conf: <code>{confidence:.1%}</code>

⏰ {datetime.now().strftime('%H:%M:%S')}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
        print("Telegram message sent")
    except Exception as e:
        print(f"Telegram failed: {e}")


def load_csv_data():
    data = []
    if os.path.exists(CSV_FILE):
        try:
            with open(CSV_FILE, 'r') as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
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
    except Exception as e:
        print(f"CSV save error: {e}")


def run_once():
    predictor = CrashPredictor()
    history = load_csv_data()
    predictor.odds_history.extend(history[-200:])
    print(f"Loaded {len(predictor.odds_history)} historical odds")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            print("Connecting to 1xbet...")
            page.goto("https://1xbet.com/en/allgamesentrance/crash", wait_until="networkidle", timeout=60000)

            print("Waiting for multiplier element...")
            try:
                page.wait_for_selector("canvas, [class*='multiplier'], .crash-multiplier, div[class*='multi'], span[class*='multi']", timeout=45000)
                time.sleep(random.uniform(8, 12))
            except:
                print("Multiplier selector not found, waiting extra time...")
                time.sleep(12)

            print("Taking screenshot...")
            page.screenshot(path="temp_screenshot.png")
            # Debug screenshot (full page)
            try:
                page.screenshot(path="debug_screenshot.png", full_page=True)
            except:
                pass

            odd = extract_odd_from_image("temp_screenshot.png")

            if odd:
                print(f"[{datetime.now().strftime('%H:%M')}] Detected: {odd}x")
                save_to_csv(odd)
                predictor.add_odd(odd)
                signal, confidence, pred_odd = predictor.predict()
                print(f"Prediction: {signal} ({confidence:.1%}) Target: {pred_odd:.1f}x")

                if "BUY" in signal:
                    send_telegram(signal, confidence, odd, pred_odd)
            else:
                print("No odd detected this run")

            browser.close()
    except Exception as e:
        print(f"Main execution error: {e}")


if __name__ == "__main__":
    run_once()
