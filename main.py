import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "7327715275"
STORED_IDS_FILE = "notified_ids.json"

CITIES = {
    "Varanasi": "4059351",
    "Allahabad": "4059246",
    "Azamgarh": "4059249",
    "Bhadohi": "4059260",
    "Ghazipur": "4059281",
    "Jaunpur": "4059291",
    "Maunath Bhanjan": "4059311",
}


def load_notified_ids():
    if os.path.exists(STORED_IDS_FILE):
        with open(STORED_IDS_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_notified_ids(notified_ids):
    with open(STORED_IDS_FILE, "w") as f:
        json.dump(list(notified_ids), f)


def send_telegram_media_group(media_group):
    if not TOKEN:
        print("TELEGRAM_TOKEN set nahi hai!")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMediaGroup"
    payload = {"chat_id": CHAT_ID, "media": media_group}
    requests.post(url, json=payload)


def send_telegram_message(message):
    if not TOKEN:
        print("TELEGRAM_TOKEN set nahi hai!")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)


def format_time(created_at_str):
    try:
        dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        dt_ist = dt.astimezone(ist_tz)
        return dt_ist.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return created_at_str


def check_city_ads(city_name, location_id, notified_ids):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    page = 0
    while True:
        url = f"https://www.olx.in/api/relevance/v2/search?query=s24%20fe&location={location_id}&page={page}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                break

            data = response.json()
            ads = data.get("data", [])

            if not ads:
                break

            for ad in ads:
                ad_id = str(ad.get("id"))
                if ad_id and ad_id not in notified_ids:
                    title = ad.get("title", "No Title")
                    price = (
                        ad.get("price", {})
                        .get("value", {})
                        .get("display_value", "N/A")
                    )
                    description = ad.get(
                        "description", "No description available"
                    )
                    time_raw = ad.get("created_at", "")
                    time_posted = format_time(time_raw)
                    url_ad = (
                        f"https://www.olx.in/item/{ad_id}"
                        if not ad.get("url")
                        else ad.get("url")
                    )

                    photos = ad.get("images", [])
                    photo_urls = [
                        img.get("url") for img in photos if img.get("url")
                    ][:10]

                    message = (
                        f"🚨 *New S24 FE Found!* 🚨\n\n"
                        f"*City:* {city_name}\n"
                        f"*Title:* {title}\n"
                        f"*Price:* {price}\n"
                        f"*Description:* {description}\n"
                        f"*Posted At:* {time_posted}\n"
                        f"*Link:* {url_ad}"
                    )

                    if photo_urls:
                        media_group = [
                            {"type": "photo", "media": url}
                            for url in photo_urls
                        ]
                        media_group[0]["caption"] = message
                        media_group[0]["parse_mode"] = "Markdown"
                        send_telegram_media_group(media_group)
                    else:
                        send_telegram_message(message)

                    notified_ids.add(ad_id)
                    save_notified_ids(notified_ids)

            page += 1
            time.sleep(1)

        except Exception as e:
            print(f"Error checking {city_name}: {e}")
            break


def main():
    notified_ids = load_notified_ids()
    for city_name, loc_id in CITIES.items():
        check_city_ads(city_name, loc_id, notified_ids)


if __name__ == "__main__":
    main()
    
