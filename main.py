import html
import json
import os
import re
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "7327715275"
NOTIFIED_FILE = "notified_ids.json"
SEARCH_QUERY = "s24"

# Matches any variation of S24 FE (case-insensitive, optional spaces/hyphens between S, 24, and FE)
S24_FE_REGEX = re.compile(r"\bs[\s\-_]*24[\s\-_]*fe\b", re.IGNORECASE)

# Exclude any listing specifying 128GB or 8/128
EXCLUDE_128_REGEX = re.compile(
    r"\b128\s*(?:gb)?\b|8[\s/_\-]+128|128[\s/_\-]+8", re.IGNORECASE
)


def matches_s24_fe(text: str) -> bool:
    if not text:
        return False
    if EXCLUDE_128_REGEX.search(text):
        return False
    return bool(S24_FE_REGEX.search(text))


def load_notified_ids() -> set:
    if os.path.exists(NOTIFIED_FILE):
        try:
            with open(NOTIFIED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_notified_ids(ids: set) -> None:
    with open(NOTIFIED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, indent=2)


def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram token missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")


def fetch_olx_ads(query: str) -> list:
    url = "https://www.olx.in/api/relevance/v2/search"
    params = {
        "query": query,
        "facet_limit": 100,
        "lang": "en",
        "size": 50,
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"Error fetching OLX ads: {e}")
        return []


def main():
    notified_ids = load_notified_ids()
    ads = fetch_olx_ads(SEARCH_QUERY)
    new_notified_ids = set(notified_ids)

    for item in ads:
        ad_id = str(item.get("id"))
        if not ad_id or ad_id in notified_ids:
            continue

        title = item.get("title", "")
        description = item.get("description", "")
        full_text = f"{title} {description}"

        if matches_s24_fe(full_text):
            price_display = (
                item.get("price", {}).get("value", {}).get("display")
                or item.get("price", {}).get("display")
                or "N/A"
            )

            locations = item.get("locations_resolved", {})
            location_parts = [
                locations.get("SUBLOCALITY_LEVEL_1_name"),
                locations.get("ADMIN_LEVEL_3_name"),
            ]
            location_name = (
                ", ".join([p for p in location_parts if p]) or "Unknown Location"
            )

            ad_url = f"https://www.olx.in/item/{ad_id}"

            safe_title = html.escape(title)
            safe_price = html.escape(str(price_display))
            safe_location = html.escape(location_name)

            message = (
                f"📱 <b>Samsung S24 FE Listing Detected</b>\n\n"
                f"<b>Title:</b> {safe_title}\n"
                f"<b>Price:</b> {safe_price}\n"
                f"<b>Location:</b> {safe_location}\n"
                f"<b>Link:</b> <a href=\"{ad_url}\">{ad_url}</a>"
            )

            send_telegram_message(message)
            new_notified_ids.add(ad_id)

    if new_notified_ids != notified_ids:
        save_notified_ids(new_notified_ids)


if __name__ == "__main__":
    main()
