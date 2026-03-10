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

PROXY_SERVERS = [
    "118.193.37.241:3129",
    "186.182.6.191:3129",
    "176.105.220.74:3129",
    "103.147.249.253:3129",
    "115.248.66.131:3129",
    "179.189.200.197:3129",
    "89.175.0.74:3129",
    "147.45.219.101:3129",
    "134.65.238.25:3129",
    "150.228.172.44:3129",
    "31.169.125.138:3129",
    "190.183.210.74:3129",
    "77.238.236.179:3129",
    "193.108.112.37:3129",
    "37.233.83.29:3129",
    "51.210.118.23:3129",
    "217.174.244.117:3129",
    "181.78.223.36:3129",
    "178.207.11.148:3129",
    "154.205.155.190:3129",
    # أضف المزيد إذا أردت
]

PROXIES = [{"server": f"http://{server}"} for server in PROXY_SERVERS]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
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
            if conf > 0.28:  # خفضنا شوية عشان نلتقط أكتر
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
            print(f"Best: {best[0]:.2f}x (conf {best[1]:.2f}) from {os.path.basename(image_path)}")
            return f"{best[0]:.2f}"
        else:
            print("No candidates found")
    except Exception as e:
        print(f"OCR error: {e}")
    return None


def send_telegram(message, image_paths=None):
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

    text_url = f"{base_url}/sendMessage"
    text_data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(text_url, data=text_data, timeout=15)
        print("Text sent to Telegram")
    except Exception as e:
        print(f"Telegram text failed: {e}")

    if image_paths:
        photo_url = f"{base_url}/sendPhoto"
        for i, path in enumerate(image_paths):
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as photo:
                        files = {'photo': photo}
                        data = {
                            'chat_id': CHAT_ID,
                            'caption': f"Debug screenshot {i+1}/{len(image_paths)} - {os.path.basename(path)}"
                        }
                        requests.post(photo_url, data=data, files=files, timeout=20)
                    print(f"Photo {i+1} sent")
                    if i < len(image_paths) - 1:
                        time.sleep(25)
                except Exception as e:
                    print(f"Photo {i+1} failed: {e}")


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

            random.shuffle(PROXIES)
            for proxy_dict in PROXIES[:30]:
                proxy_str = proxy_dict["server"]
                print(f"Trying proxy: {proxy_str}")

                try:
                    context = browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        viewport={'width': 1920, 'height': 1080},
                        proxy=proxy_dict,
                        ignore_https_errors=True,
                        bypass_csp=True,
                        java_script_enabled=True,
                    )
                    page = context.new_page()

                    page.goto(
                        "https://1xbet.com/en/allgamesentrance/crash",
                        wait_until="domcontentloaded",
                        timeout=90000
                    )

                    # انتظر حالة DOM مستقرة
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=45000)
                    except:
                        pass

                    print(f"Page loaded with proxy: {proxy_str}")
                    used_proxy = proxy_str.replace("http://", "")
                    success = True
                    break

                except Exception as e:
                    print(f"Proxy {proxy_str} failed: {str(e)[:120]}...")
                    continue

            if not success:
                print("All proxies failed → trying direct connection")
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={'width': 1920, 'height': 1080},
                    ignore_https_errors=True,
                )
                page = context.new_page()
                page.goto(
                    "https://1xbet.com/en/allgamesentrance/crash",
                    wait_until="domcontentloaded",
                    timeout=90000
                )
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=45000)
                except:
                    pass

            # انتظر قليلاً بعد التحميل
            time.sleep(random.uniform(8, 18))

            # خد 3 سكرين شوت مع timeout أكبر
            screenshots = []
            for i in range(3):
                path = f"debug_shot_{i+1}_{int(time.time())}.png"
                try:
                    page.screenshot(path=path, full_page=(i == 0), timeout=60000)
                    screenshots.append(path)
                    print(f"Screenshot {i+1} taken: {path}")
                except PlaywrightTimeoutError:
                    print(f"Screenshot {i+1} timed out - continuing anyway")
                except Exception as e:
                    print(f"Screenshot {i+1} error: {e}")

            odd = None
            for scr in screenshots:
                if os.path.exists(scr):
                    detected = extract_odd_from_image(scr)
                    if detected:
                        odd = detected
                        print(f"Detected odd: {odd}x")
                        break

            images_to_send = [p for p in screenshots if os.path.exists(p)]

            if odd:
                save_to_csv(odd)
                predictor.add_odd(odd)
                signal, conf, pred = predictor.predict()

                msg = f"""
<b>CRASH BOT RESULT</b> (Proxy: {used_proxy})

Current: <code>{odd}x</code>
Signal: {signal}
Target: <code>{pred:.2f}x</code>
Conf: <code>{conf:.0%}</code>
Time: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
                send_telegram(msg, images_to_send)
            else:
                msg = f"""
<b>NO ODD DETECTED</b> (Proxy: {used_proxy})

Check attached screenshots
Likely Access Denied or page didn't load properly
Time: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
"""
                send_telegram(msg, images_to_send)

            browser.close()

    except Exception as e:
        print(f"Critical error: {str(e)}")
        send_telegram(f"""
<b>CRASH BOT CRITICAL ERROR</b>

{str(e)[:400]}
Time: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
""")


if __name__ == "__main__":
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("Stopped by user")
            break
        except Exception as e:
            print(f"Main loop error: {e}")
            time.sleep(120)

        wait = random.uniform(240, 480)  # 4-8 دقائق
        print(f"Next attempt in ≈ {wait//60:.0f} minutes")
        time.sleep(wait)
