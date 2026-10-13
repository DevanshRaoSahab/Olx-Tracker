import requests
import json
import os

TELEGRAM_BOT_TOKEN = "8238967218:AAGLa5BPQKtIeI2OyowzXK-b47O70WzXKZo"
TELEGRAM_CHAT_ID = "7327715275"
SEEN_IDS_FILE = "seen_ads.json"

TARGET_QUERIES = [
    "s24 fe",
    "galaxy s24 fe",
    "s24 fe 256",
    "s24 fe 8 256",
    "galaxy s24 fe 256",
    "galaxy s24 fe 8 256",
    "samsung s24 fe",
    "samsung s24 fe 8 256"
]

LOCATIONS = {
    "Varanasi": "4059351",
    "Gorakhpur": "1000035",
    "Mau": "4059311",
    "Bhadohi": "4403605",
    "Sultanpur": "4059345",
    "Allahabad": "4059246",
    "Jaunpur": "4059291",
}

def send_telegram_alert(ad):
    text = (
        f"🚨 *New Deal Found!*\n"
        f"📱 *Title:* {ad['title']}\n"
        f"💰 *Price:* ₹{ad['price']['value']['raw']}\n"
        f"📍 *Location:* {ad['locations_resolved']['ADMIN_LEVEL_3_name']}\n"
        f"🔗 [View on OLX](https://www.olx.in/item/{ad['id']})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    requests.post(url, json=payload)

def load_seen_ids():
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen_ids(seen_ids):
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(list(seen_ids), f)

def check_olx():
    seen_ids = load_seen_ids()
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"
    }

    for loc_name, loc_id in LOCATIONS.items():
        for query in TARGET_QUERIES:
            params = {
                "facet_limit": 100,
                "location": loc_id,
                "query": query,
                "sorting": "desc-creation"
            }
            try:
                res = requests.get("https://www.olx.in/api/relevance/v4/search", headers=headers, params=params, timeout=10)
                if res.status_code != 200:
                    continue
                data = res.json().get("data", [])

                for item in data:
                    ad_id = str(item.get("id"))
                    title = item.get("title", "").lower()
                    
                    if any(k in title for k in ["s24 fe", "s24fe"]):
                        if any(banned in title for banned in ["case", "cover", "tempered", "skin"]):
                            continue
                        
                        if ad_id not in seen_ids:
                            seen_ids.add(ad_id)
                            send_telegram_alert(item)
            except Exception as e:
                print(f"Error checking {loc_name}: {e}")

    save_seen_ids(seen_ids)

if __name__ == "__main__":
    check_olx()
