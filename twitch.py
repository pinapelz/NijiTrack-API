import requests
from bs4 import BeautifulSoup
import time


youtube_to_twitch_map = {
    "UC1cExET9xoWSO9iSnRsW_1Q": "michiru_shisui",
    "UC3K7pmiHsNSx1y0tdx2bbCw": "tenma",
    "UCB7sSUNwh_dXE7ZL3DsGDpw": "utatanenasa",
    "UCg7sW-h1PUowdiR5K4HlBew": "asheliarinkou",
    "UCJ46YTYBQVXsfsp8-HryoUA": "pippa",
    "UCN5bD1YYapThOeadG7YkBOA": "iorihakushika",
    "UC0w_dvkIwnXzMak6gfeioRQ": "emberamane",
    "UC98iRMvRqUxRD6GP4NtRskw": "dizzydokuro",
    "UCkb-r702uhx4-6Lrmetp-Ow": "jellyhoshiumi",
    "UCx_zwZuGIS4jxO07kFk8G6Q": "kanekolumi",
    "UC3aEtHpGzCFvoSn_wRWzgZQ": "EepySleepy",
    "UCG5vZgELi3on_pksaLrIoxw": "marimari_en",
    "UCrGTSXWMiAWoPlowSuMVZ4Q": "clioaite",
    "UC-hMwvRuMsQrfgu0DPKLV2A": "remilianephys",
    "UCJ4O6PWA47f6XbCgrLQNqEQ": "himemiyarie",
    "UCnJNNk45O1QYS2oMRYFKSyw": "amanogawashiina",
    "UCVo_KgPNsDKxHwzib7uarCw": "komachipanko",
    "UCejbicoRnQjCOdAPAv5JPwg": "muumuyu",
    "UCoAQsc-DQ0MjfTp059otQAw": "RunieRuse",
    "UC-tBLCGTheczDn5mYNoNWTQ": "eimiisami",
    "UCXDytlJU6RL8D68VrPZGyIA": "HikanariHina",
    "UCGXwv2zYOxeWiNNyPiLCBCQ": "kokoromomemory",
    "UCnNLZWjl4GvVF4s8zBT9_kA": "ayaseyuu_",
    "UCRlZaszk84YXjRtdPCxqjvw": "kaminariclara",
    "UCtWH0tVAcUcSm4v96H5cAqQ": "grampico"
}

def get_followers_total(channel_name):
    url = f"https://twitchtracker.com/api/channels/summary/{channel_name}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return int(data.get("followers_total")) if "followers_total" in data else None
    else:
        return None


def get_total_follower_count_scrape(username: str) -> int:
    url = f"https://twitchtracker.com/{username}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    html = response.text

    soup = BeautifulSoup(html, 'html.parser')
    for li in soup.find_all("li", class_="list-group-item"):
        label = li.find("div", style=lambda val: val and "font-size:12px" in val)
        if label and label.text.strip().lower() == "followers":
            number_span = li.find("span", class_="to-number")
            if number_span and number_span.text:
                try:
                    print("[TWITCH_SCRAPE] Forced cooldown 5 seconds")
                    time.sleep(5)
                    return int(number_span.text.replace(",", "").strip())
                except ValueError:
                    continue
    follower_blocks = soup.find_all(string=lambda text: text and "Followers" in text)
    for text in follower_blocks:
        parent = text.find_parent()
        if parent:
            number = parent.find_next("span", class_="to-number")
            if number and number.text.replace(",", "").strip().isdigit():
                print("[TWITCH_SCRAPE] Forced cooldown 5 seconds")
                time.sleep(5)
                return int(number.text.replace(",", "").strip())
    return None
