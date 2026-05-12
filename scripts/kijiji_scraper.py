import requests
import json
import time
import random
import re
from datetime import datetime

# ============================================
# BEAVER.WATCH — Kijiji Stress Index Scraper
# Method: Title parsing (Gemini-optimized)
# Light · Stable · Stealthy
# Runs daily via GitHub Actions (new IP each time)
# ============================================

CITIES = {
    "montreal": {"id": "1700281", "name": "Montréal"},
    "toronto":  {"id": "1700272", "name": "Toronto"},
    "vancouver":{"id": "1700254", "name": "Vancouver"},
}

CATEGORIES = {
    "outils": {
        "label_fr": "Outils & Équipement",
        "label_en": "Tools & Equipment",
        "signal":   "Entrepreneurs liquidating",
        "emoji":    "🔧",
        "weight":   0.35
    },
    "electronique": {
        "label_fr": "Consoles & Électronique",
        "label_en": "Electronics & Gaming",
        "signal":   "Households selling assets",
        "emoji":    "🎮",
        "weight":   0.25
    },
    "transfert-bail": {
        "label_fr": "Transfert de Bail",
        "label_en": "Lease Transfers",
        "signal":   "People fleeing housing costs",
        "emoji":    "🏠",
        "weight":   0.25
    },
    "bijoux-montres": {
        "label_fr": "Bijoux & Montres",
        "label_en": "Jewelry & Watches",
        "signal":   "Families selling valuables",
        "emoji":    "💍",
        "weight":   0.15
    },
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

def get_count(keyword, city_id):
    """
    GEMINI METHOD: Parse <title> tag only.

    Kijiji title format:
    "2 840 annonces - outils - Montréal | Kijiji"
    "2,840 Ads - tools - Toronto | Kijiji"

    Why this works:
    - Only downloads the first ~4KB of HTML (title is in <head>)
    - No DOM parsing = much lighter footprint
    - Title format rarely changes = more stable
    - Looks exactly like a browser request
    """
    url = f"https://www.kijiji.ca/b-{city_id}/{keyword}/k0l{city_id}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.kijiji.ca/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}")
            return None

        # Extract ONLY the <title> — no full DOM parse
        title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.IGNORECASE | re.DOTALL)
        if not title_match:
            print("no title found")
            return None

        title = title_match.group(1).strip()
        print(f'title: "{title[:60]}"', end=" → ")

        # Handle zero results
        if any(x in title.lower() for x in ["aucune", "no ads", "0 annonce", "0 ad"]):
            print("0")
            return 0

        # Extract the first number from title
        # Handles: "2 840", "2,840", "2.840"
        numbers = re.findall(r'\d[\d\s,\.]*\d|\d', title)
        for raw in numbers:
            cleaned = re.sub(r'[\s,\.]', '', raw)
            if cleaned.isdigit() and int(cleaned) > 0:
                result = int(cleaned)
                print(result)
                return result

        print("parse failed")
        return None

    except requests.Timeout:
        print("timeout")
        return None
    except Exception as e:
        print(f"error: {e}")
        return None


def calculate_score(current, baseline):
    """Score 0–1 based on % change from baseline."""
    if baseline is None or baseline == 0 or current is None:
        return None
    change = ((current - baseline) / baseline) * 100
    if change <= 0:
        return max(0.05, round(0.15 + (change / 200), 2))
    elif change <= 5:
        return round(0.15 + (change / 5) * 0.20, 2)
    elif change <= 15:
        return round(0.35 + ((change - 5) / 10) * 0.30, 2)
    elif change <= 30:
        return round(0.65 + ((change - 15) / 15) * 0.25, 2)
    else:
        return min(1.0, round(0.90 + ((change - 30) / 50) * 0.10, 2))


def get_status(score):
    if score is None:
        return {"label_fr": "N/A", "label_en": "N/A", "color": "gray", "emoji": "❓"}
    if score < 0.35:
        return {"label_fr": "Normal", "label_en": "Normal", "color": "green", "emoji": "🟢"}
    if score < 0.65:
        return {"label_fr": "Tension", "label_en": "Tension", "color": "orange", "emoji": "🟠"}
    return {"label_fr": "CRISE", "label_en": "CRISIS", "color": "red", "emoji": "🔴"}


def run():
    print("🦫 BEAVER.WATCH — Kijiji Stress Index")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("🔍 Gemini method: title parsing only")
    print("=" * 52)

    # Load baseline
    try:
        with open('kijiji_baseline.json', 'r') as f:
            baseline = json.load(f)
        print("✅ Baseline loaded\n")
    except FileNotFoundError:
        baseline = {}
        print("⚠️  No baseline — today becomes baseline\n")

    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "cities": {},
        "national_score": None,
        "national_status": None,
    }

    all_city_scores = []

    for city_key, city_info in CITIES.items():
        print(f"\n📍 {city_info['name']}")
        city_result = {
            "name_fr": city_info['name'],
            "name_en": city_info['name'],
            "categories": {},
            "composite_score": None,
            "composite_status": None,
        }
        weighted_scores = []

        for cat_key, cat_info in CATEGORIES.items():
            # Random human-like delay between requests
            delay = random.uniform(6, 14)
            time.sleep(delay)
            print(f"  [{delay:.0f}s] {cat_key}: ", end="", flush=True)

            count = get_count(cat_key, city_info['id'])

            bkey = f"{city_key}_{cat_key}"
            base_count = baseline.get(bkey)

            # First run → set baseline
            if base_count is None and count is not None:
                baseline[bkey] = count
                base_count = count

            score = calculate_score(count, base_count)
            status = get_status(score)
            change_pct = None
            if count is not None and base_count:
                change_pct = round(((count - base_count) / base_count) * 100, 1)

            city_result['categories'][cat_key] = {
                "label_fr":   cat_info['label_fr'],
                "label_en":   cat_info['label_en'],
                "emoji":      cat_info['emoji'],
                "signal":     cat_info['signal'],
                "count":      count,
                "baseline":   base_count,
                "change_pct": change_pct,
                "score":      score,
                "status":     status,
                "weight":     cat_info['weight'],
            }

            if score is not None:
                weighted_scores.append((score, cat_info['weight']))

        # City composite score
        if weighted_scores:
            total_w = sum(w for _, w in weighted_scores)
            composite = round(sum(s * w for s, w in weighted_scores) / total_w, 2)
            city_result['composite_score'] = composite
            city_result['composite_status'] = get_status(composite)
            all_city_scores.append(composite)
            print(f"\n  📊 {city_info['name']}: {composite} {get_status(composite)['emoji']}")

        output['cities'][city_key] = city_result

    # National score
    if all_city_scores:
        national = round(sum(all_city_scores) / len(all_city_scores), 2)
        output['national_score'] = national
        output['national_status'] = get_status(national)
        print(f"\n🍁 NATIONAL: {national} {get_status(national)['emoji']}")

    # Save outputs
    with open('kijiji_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n✅ kijiji_data.json saved")

    with open('kijiji_baseline.json', 'w', encoding='utf-8') as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print("✅ kijiji_baseline.json updated")


if __name__ == "__main__":
    run()
