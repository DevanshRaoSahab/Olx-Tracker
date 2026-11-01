import json
import os
import re
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7327715275")
SEEN_FILE = "seen_ads.json"
LAST_UPDATE_ID_FILE = "last_update_id.json"

OLX_API_URL = "https://www.olx.in/api/relevance/v4/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Referer": "https://www.olx.in/varanasi_g4059281/mobile-phones_c1453",
    "Origin": "https://www.olx.in",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Ch-Ua": (
        '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"'
    ),
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

TARGET_QUERIES = ["S24 FE", "Reno 14"]
LOCATION_ID = "4059281"  # Varanasi


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f)


def classify_listing(text):
    text_lower = text.lower()

    # Samsung S24 FE check (exclude 128GB)
    s24_fe_pattern = r"\bs[\s-]?24[\s-]?fe\b"
    if re.search(s24_fe_pattern, text_lower):
        if re.search(r"\b128\s*(gb|g)?\b", text_lower):
            return None
        return "Samsung S24 FE (256GB+)"

    # Oppo Reno 14 Base model check (exclude Pro / Pro+ / Pro Max variations)
    reno_14_pattern = r"\breno[\s-]?14\b"
    if re.search(reno_14_pattern, text_lower):
        if re.search(r"\bpro(\s*\+|\s*max)?\b", text_lower):
            return None
        return "Oppo Reno 14 (Base)"

    return None


def fetch_filtered_ads():
    session = requests.Session()
    session.headers.update(HEADERS)
    valid_ads = []
    seen_ids_in_run = set()

    for query in TARGET_QUERIES:
        params = {
            "category": "1453",
            "facet_only": "false",
            "location": LOCATION_ID,
            "query": query,
            "size": "40",
        }
        try:
            response = session.get(
                OLX_API_URL, params=params, headers=HEADERS, timeout=15
            )
            if response.status_code != 200:
                continue

            data = response.json()
            ads = data.get("data", [])

            for ad in ads:
                ad_id = str(ad.get("id"))
                if ad_id in seen_ids_in_run:
                    continue

                title = ad.get("title", "")
                description = ad.get("description", "")
                full_text = f"{title} {description}"

                model_tag = classify_listing(full_text)
                if not model_tag:
                    continue

                seen_ids_in_run.add(ad_id)
                price = (
                    ad.get("price", {}).get("value", {}).get("display", "N/A")
                )
                location = ad.get("locations_resolved", {}).get(
                    "ADMIN_LEVEL_3_name", "Varanasi"
                )
                url = f"https://www.olx.in/item/{ad_id}"

                valid_ads.append(
                    {
                        "id": ad_id,
                        "title": title,
                        "model_tag": model_tag,
                        "price": price,
                        "location": location,
                        "url": url,
                    }
                )
        except Exception:
            continue

    return valid_ads


def send_telegram_message(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def handle_start_command():
    if not TELEGRAM_BOT_TOKEN:
        return

    last_update_id = load_json(LAST_UPDATE_ID_FILE, 0)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 2}

    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return
        data = resp.json()
        updates = data.get("result", [])
        if not updates:
            return

        for update in updates:
            up_id = update.get("update_id", 0)
            if up_id > last_update_id:
                last_update_id = up_id

            message = update.get("message", {})
            text = message.get("text", "").strip()
            chat_id = message.get("chat", {}).get("id")

            if text.startswith("/start") and chat_id:
                current_ads = fetch_filtered_ads()
                if not current_ads:
                    msg = (
                        "👋 <b>Bot Active</b>\n\nNo active listings found in"
                        " Varanasi for S24 FE (excluding 128GB) or Oppo Reno 14"
                        " series."
                    )
                else:
                    lines = [
                        (
                            f"• [{ad['model_tag']}] <a"
                            f" href='{ad['url']}'>{ad['title']}</a> - "
                            f"<b>{ad['price']}</b> ({ad['location']})"
                        )
                        for ad in current_ads
                    ]
                    msg = (
                        f"👋 <b>Current Listings ({len(current_ads)}"
                        " Found):</b>\n\n" + "\n\n".join(lines)
                    )
                send_telegram_message(chat_id, msg)

        save_json(LAST_UPDATE_ID_FILE, last_update_id)
    except Exception:
        pass


def monitor_new_listings():
    seen_ads = set(load_json(SEEN_FILE, []))
    current_ads = fetch_filtered_ads()
    new_seen = set(seen_ads)

    for ad in current_ads:
        ad_id = ad["id"]
        if ad_id in seen_ads:
            continue

        alert = (
            f"🚨 <b>New Listing Found: {ad['model_tag']}</b>\n\n"
            f"📱 <b>Title:</b> {ad['title']}\n"
            f"💰 <b>Price:</b> {ad['price']}\n"
            f"📍 <b>Location:</b> {ad['location']}\n"
            f"🔗 <a href='{ad['url']}'>Open Listing</a>"
        )
        if send_telegram_message(TELEGRAM_CHAT_ID, alert):
            new_seen.add(ad_id)

    save_json(SEEN_FILE, list(new_seen))


def main():
    handle_start_command()
    monitor_new_listings()


if __name__ == "__main__":
    main()
