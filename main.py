import os
import json
import requests
import re

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen_ads.json"

# Sabhi locations ki list
LOCATIONS = [
    {"name": "Varanasi", "id": "4059351"},
    {"name": "Allahabad", "id": "4059246"},
    {"name": "Azamgarh", "id": "4059249"},
    {"name": "Bhadohi", "id": "4059260"},
    {"name": "Ghazipur", "id": "4059281"},
    {"name": "Jaunpur", "id": "4059291"},
    {"name": "Maunath Bhanjan", "id": "4059311"},
    {"name": "Sultanpur", "id": "4059345"}
]

OLX_API_URL = "https://www.olx.in/api/relevance/v4/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Referer": "https://www.olx.in/varanasi_g4059351/mobile-phones_c1453",
    "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

TARGET_QUERIES = ["S24 FE", "Reno 14"]


def load_seen(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_seen(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f)


def classify_listing(text):
    text_lower = text.lower()

    # Samsung S24 FE check (exclude 128GB)
    if "s24 fe" in text_lower or "s24fe" in text_lower:
        if re.search(r"\b128\s*(gb)?\b", text_lower):
            return None
        return "Samsung S24 FE (128GB Excluded)"

    # Oppo Reno 14 Base model check (exclude Pro / Pro+ / Pro Max variations)
    reno_14_pattern = r"\breno\s*14(?!\s*(pro|\+))"
    if re.search(reno_14_pattern, text_lower):
        if any(v in text_lower for v in ["pro", "pro+", "+", "pro max"]):
            return None
        return "Oppo Reno 14 (Base)"

    return None


def fetch_filtered_ads():
    session = requests.Session()
    session.headers.update(HEADERS)

    valid_ads = []

    # Har location ke liye search karega
    for loc in LOCATIONS:
        for query in TARGET_QUERIES:
            params = {
                "category": "1453",
                "facet_only": "false",
                "location": loc["id"],
                "query": query,
                "size": "40",
            }

            try:
                response = session.get(OLX_API_URL, params=params, timeout=15)
                if response.status_code != 200:
                    continue

                data = response.json()
                ads = data.get("data", [])

                for ad in ads:
                    title = ad.get("title", "")
                    description = ad.get("description", "")
                    full_text = f"{title} {description}"

                    model_tag = classify_listing(full_text)
                    if model_tag:
                        price_data = ad.get("price", {}).get("value", {})
                        price = price_data.get("display", "N/A")

                        valid_ads.append({
                            "id": str(ad.get("id")),
                            "title": title,
                            "price": price,
                            "location": loc["name"],
                            "url": f"https://www.olx.in/item/{ad.get('id')}",
                            "tag": model_tag
                        })
            except Exception as e:
                print(f"Error fetching {query} for {loc['name']}: {e}")

    return valid_ads


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


def main():
    seen_ids = set(load_seen(SEEN_FILE, []))
    ads = fetch_filtered_ads()

    # Duplicate ads hatane ke liye (agar multi-query me repeat huye)
    unique_ads = {ad["id"]: ad for ad in ads}.values()

    new_ads = [ad for ad in unique_ads if ad["id"] not in seen_ids]

    if not seen_ids and not new_ads and ads:
        # First run safeguard: agar koi match hai par notify pehli bar sabhi ka karna ho
        new_ads = list(unique_ads)

    if new_ads:
        for ad in new_ads:
            msg = (
                f"🚨 <b>New OLX Alert!</b>\n\n"
                f"📱 <b>Model:</b> {ad['tag']}\n"
                f"📍 <b>Location:</b> {ad['location']}\n"
                f"💰 <b>Price:</b> {ad['price']}\n"
                f"📝 <b>Title:</b> {ad['title']}\n\n"
                f"🔗 <a href='{ad['url']}'>View Ad on OLX</a>"
            )
            send_telegram_message(msg)
            seen_ids.add(ad["id"])

        save_seen(SEEN_FILE, list(seen_ids))
        print(f"Sent {len(new_ads)} alerts.")
    else:
        print("No new matching ads found across monitored locations.")
        if not seen_ids:
            # First time jab database khali ho aur koi ad na mile
            send_telegram_message("🤖 <b>Bot Active</b>\n\nMonitoring started for Varanasi, Allahabad, Azamgarh, Bhadohi, Ghazipur, Jaunpur, Mau & Sultanpur. No matching ads right now.")
            save_seen(SEEN_FILE, ["initialized"])


if __name__ == "__main__":
    main()
